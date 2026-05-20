#!/usr/bin/env python3
"""
Thermalright Trofeo LCD Driver for Linux
=========================================
Reverse-engineered from USB capture of TRCC (Thermalright Control Center).

Device: Winbond 0416:5408
Protocol: JPEG images sent via USB bulk transfers
Resolution: 1920x462
Endpoints: EP9 OUT (bulk, 512B), EP1 IN (bulk, 512B)

Usage:
    # Send a single image:
    python3 trofeo_lcd.py image.jpg

    # Send images in a loop (monitoring mode):
    python3 trofeo_lcd.py --loop --interval 1.0 image.jpg

    # Generate and send a test pattern:
    python3 trofeo_lcd.py --test

    # System monitoring display:
    python3 trofeo_lcd.py --monitor
"""

import sys
import time
import struct
import argparse
import io
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

try:
    import usb.core
    import usb.util
except ImportError:
    print("BŁĄD: Brak modułu pyusb. Zainstaluj: pip install pyusb")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("BŁĄD: Brak modułu Pillow. Zainstaluj: pip install Pillow")
    sys.exit(1)

from stats_sources import StatsProvider
from theme_renderer import render_theme_document
from theme_schema import ThemeDocument, load_theme_document


# Device constants
VID = 0x0416
PID = 0x5408
EP_OUT = 0x09  # Bulk OUT endpoint
EP_IN = 0x81   # Bulk IN endpoint
INTERFACE = 0

# Display constants
LCD_WIDTH = 1920
LCD_HEIGHT = 462

# Protocol constants
CHUNK_SIZE = 4096         # Standard chunk size
LAST_CHUNK_SIZE = 2048    # Last chunk in frame
HEADER_SIZE = 16          # Protocol header per chunk
DATA_PER_CHUNK = CHUNK_SIZE - HEADER_SIZE  # 4080 bytes
DATA_PER_LAST = LAST_CHUNK_SIZE - HEADER_SIZE  # 2032 bytes
JPEG_QUALITY = 85         # JPEG compression quality
JPEG_SUBSAMPLING = "4:2:0"
JPEG_PROGRESSIVE = False
JPEG_RESTART_MARKER_ROWS = 0
MONITOR_NOISE_ALPHA = 0.409

USB_TIMEOUT = 5000        # ms
ACK_READ_SIZE = 512
DEFAULT_ACK_EVERY_PACKET = True
RECOVERY_DELAY = 1.0
USB_RESET_DELAY = 2.0
CONNECT_RETRIES = 5
CONNECT_RETRY_DELAY = 0.5
WINDOWS_CAPTURE_INTER_PACKET_DELAY = 0.0005
WINDOWS_CAPTURE_ACK_TIMEOUT_MS = 120
INIT_PACKET_SIZE = 2048
INIT_RESPONSE_SIZE = 512
INIT_RETRIES = 3
INIT_RETRY_DELAY = 0.3
TRCC_COMPAT_JPEG_SIZE = 309679
TRCC_COMPAT_HEADER_B9 = 0x71
TRCC_COMPAT_TRANSFER_SIZE = (78 * DATA_PER_CHUNK) + DATA_PER_LAST
TRCC_HEADER_B9_SIZE_MAP = (
    (309400, 0x70),
    (309479, 0x70),
    (309679, 0x71),
    (309688, 0x71),
    (309896, 0x71),
    (310012, 0x72),
    (310045, 0x72),
)

FINAL_PACKET_MODE_AUTO = "auto"
FINAL_PACKET_MODE_PAD_2048 = "pad-2048"
FINAL_PACKET_MODE_PAD_4096 = "pad-4096"
HEADER_SIZE_MODE_JPEG = "jpeg-size"
HEADER_SIZE_MODE_CHUNK = "chunk-size"
HEADER_SIZE_MODE_REMAINING = "remaining"
COMMIT_MODE_BASIC = "basic"
COMMIT_MODE_SCAN = "scan"
BUFFER_INDEX_MODE_ZERO = "zero"
BUFFER_INDEX_MODE_CYCLE3 = "cycle3"

# Live Windows capture from 2026-05-16: first steady animation frames map
# declared JPEG size to header byte[9] very closely as round(size / 512) - 491.
# Later partial/delta frames have wider scatter, so this remains a heuristic.
CAPTURE_B9_SIZE_DIVISOR = 512.0
CAPTURE_B9_SIZE_OFFSET = -491.0


@dataclass
class PacketPlan:
    payload_len: int
    total_size: int
    seq_num: int


@dataclass
class AckSummary:
    command: int
    marker: int
    status_byte: int
    raw: bytes


class TrofeoLCD:
    """Driver for Thermalright Trofeo LCD display."""

    def __init__(self):
        self.dev = None
        self.frame_counter = 0
        self._reattach_kernel = False
        self._initialized = False
        self.init_enabled = True
        self.init_every_frame = False
        self.init_strict = False
        self.header_b9 = None
        self.header_byte10 = 0x02
        self.buffer_index_mode = BUFFER_INDEX_MODE_ZERO
        self.buffer_index_override = None

    @staticmethod
    def _is_resource_busy(err: Exception) -> bool:
        text = str(err).lower()
        return "errno 16" in text or "resource busy" in text

    @staticmethod
    def estimate_header_b9(jpeg_size: int) -> int:
        """
        Estimate header byte [9] from capture-derived size/b9 pairs.
        The 2026-05-16 Windows trace shows a strong initial mapping:
        b9 ~= round(jpeg_size / 512) - 491, with uint8 wrap-around.
        """
        nearest_size, nearest_b9 = min(
            TRCC_HEADER_B9_SIZE_MAP,
            key=lambda item: abs(item[0] - jpeg_size),
        )
        if abs(nearest_size - jpeg_size) <= 4096:
            return nearest_b9 & 0xFF
        return int(round((jpeg_size / CAPTURE_B9_SIZE_DIVISOR) + CAPTURE_B9_SIZE_OFFSET)) & 0xFF

    @staticmethod
    def pad_jpeg_payload(jpeg_data: bytes, pad_to_size: int | None) -> bytes:
        """
        Optional compatibility pad: extend JPEG payload with trailing zeros
        to match expected transfer envelope size observed in captures.
        """
        if pad_to_size is None:
            return jpeg_data
        if pad_to_size <= 0:
            return jpeg_data
        if len(jpeg_data) >= pad_to_size:
            return jpeg_data
        return jpeg_data + (b"\x00" * (pad_to_size - len(jpeg_data)))

    def _build_init_packet(self) -> bytes:
        """
        Build 2048-byte INIT query packet (cmd=0x02).
        """
        packet = bytearray(INIT_PACKET_SIZE)
        packet[0] = 0x02
        packet[1] = 0xFF
        packet[8] = 0x01
        return bytes(packet)

    def _init_device(self, packet_debug=False, timeout_ms=USB_TIMEOUT) -> bool:
        """
        Send INIT query once before frame upload.
        """
        if not self.dev:
            return False

        init_packet = self._build_init_packet()
        last_error = None
        response = None
        for attempt in range(1, INIT_RETRIES + 1):
            try:
                if packet_debug:
                    print(
                        f"  init out (attempt {attempt}/{INIT_RETRIES}):"
                        f" len={len(init_packet)} hdr={init_packet[:16].hex(' ')}"
                    )
                self.dev.write(EP_OUT, init_packet, USB_TIMEOUT)
            except usb.core.USBError as e:
                last_error = e
                if attempt < INIT_RETRIES:
                    self.recover_endpoints(delay=INIT_RETRY_DELAY)
                    continue
                print(f"BŁĄD INIT write: {e}")
                return False

            try:
                response = bytes(self.dev.read(EP_IN, INIT_RESPONSE_SIZE, timeout_ms))
                break
            except usb.core.USBTimeoutError as e:
                last_error = e
                if attempt < INIT_RETRIES:
                    self.recover_endpoints(delay=INIT_RETRY_DELAY)
                    continue
                print("BŁĄD INIT: timeout na odpowiedzi urządzenia")
                return False
            except usb.core.USBError as e:
                last_error = e
                if attempt < INIT_RETRIES:
                    self.recover_endpoints(delay=INIT_RETRY_DELAY)
                    continue
                print(f"BŁĄD INIT read: {e}")
                return False

        if response is None:
            if last_error is not None:
                print(f"BŁĄD INIT: {last_error}")
            return False

        self._initialized = True
        if packet_debug:
            # Heurystyczna inspekcja odpowiedzi INIT pod kątem znanych wartości.
            interesting = []
            for i in range(0, len(response) - 1):
                value = response[i] | (response[i + 1] << 8)
                if value in (1920, 462, 599):
                    interesting.append((i, value))
            print(f"  init in : len={len(response)} raw={response[:32].hex(' ')}...")
            if interesting:
                pairs = ", ".join(f"off={off}:v={val}" for off, val in interesting[:12])
                print(f"  init in : candidates {pairs}")
        return True

    def send_commit_packet(self, jpeg_size, packet_debug=False, commit_mode=COMMIT_MODE_BASIC):
        """
        Experimental post-frame commit packets.
        These are speculative and only used for live protocol testing.
        """
        candidates = []

        commit_a = bytearray(16)
        commit_a[0] = 0x02
        commit_a[1] = 0xFF
        struct.pack_into('<I', commit_a, 2, jpeg_size & 0xFFFFFFFF)
        commit_a[7] = 0xF0
        commit_a[8] = 0x01
        commit_a[9] = 0x01
        commit_a[10] = self.frame_counter & 0xFF
        candidates.append(bytes(commit_a))

        commit_b = bytearray(16)
        commit_b[0] = 0x03
        commit_b[1] = 0xFF
        commit_b[7] = 0xF0
        commit_b[8] = 0x01
        commit_b[9] = 0x01
        commit_b[10] = self.frame_counter & 0xFF
        candidates.append(bytes(commit_b))

        if commit_mode == COMMIT_MODE_SCAN:
            commit_c = bytearray(16)
            commit_c[0] = 0x02
            commit_c[1] = 0xFF
            commit_c[7] = 0xF0
            commit_c[8] = 0x01
            commit_c[9] = 0x01
            commit_c[10] = self.frame_counter & 0xFF
            candidates.append(bytes(commit_c))

            commit_d = bytearray(16)
            commit_d[0] = 0x01
            commit_d[1] = 0xFF
            struct.pack_into('<I', commit_d, 2, jpeg_size & 0xFFFFFFFF)
            commit_d[7] = 0xF0
            commit_d[8] = 0x01
            commit_d[9] = 0x02
            commit_d[10] = self.frame_counter & 0xFF
            candidates.append(bytes(commit_d))

            commit_e = bytearray(16)
            commit_e[0] = 0x04
            commit_e[1] = 0xFF
            struct.pack_into('<I', commit_e, 2, jpeg_size & 0xFFFFFFFF)
            commit_e[7] = 0xF0
            commit_e[8] = 0x01
            commit_e[9] = 0x01
            commit_e[10] = self.frame_counter & 0xFF
            candidates.append(bytes(commit_e))

        for idx, payload in enumerate(candidates, start=1):
            try:
                if packet_debug:
                    print(f"  commit {idx}: {payload.hex(' ')}")
                self.dev.write(EP_OUT, payload, USB_TIMEOUT)
                try:
                    ack = bytes(self.dev.read(EP_IN, ACK_READ_SIZE, 200))
                    if packet_debug:
                        print(f"    commit ack {idx}: {ack.hex(' ')}")
                except usb.core.USBTimeoutError:
                    if packet_debug:
                        print(f"    commit ack {idx}: <timeout>")
            except usb.core.USBError as e:
                if packet_debug:
                    print(f"    commit {idx} failed: {e}")

    def connect(self, retries=CONNECT_RETRIES, retry_delay=CONNECT_RETRY_DELAY):
        """Find and connect to the Trofeo LCD device."""
        retries = max(1, int(retries))
        retry_delay = max(0.0, float(retry_delay))
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                self.dev = usb.core.find(idVendor=VID, idProduct=PID)
            except usb.core.NoBackendError:
                print("BŁĄD: pyusb nie znalazł backendu libusb.")
                print("Na Ubuntu/Kubuntu doinstaluj pakiet libusb, np.: sudo apt install libusb-1.0-0")
                return False

            if self.dev is None:
                last_error = RuntimeError(f"Nie znaleziono urządzenia Trofeo LCD ({VID:04x}:{PID:04x})")
                if attempt < retries:
                    time.sleep(retry_delay)
                    continue
                print(f"BŁĄD: {last_error}")
                print("Sprawdź:")
                print("  1. Czy LCD jest podłączony przez USB")
                print("  2. Czy masz uprawnienia (uruchom z sudo lub dodaj regułę udev)")
                print("  3. lsusb | grep 0416")
                return False

            # Detach kernel driver if attached
            try:
                if self.dev.is_kernel_driver_active(INTERFACE):
                    self.dev.detach_kernel_driver(INTERFACE)
                    self._reattach_kernel = True
                    print("Odłączono sterownik kernela")
            except (usb.core.USBError, NotImplementedError):
                pass

            # Set configuration and claim interface
            try:
                self.dev.set_configuration()
            except usb.core.USBError:
                pass  # May already be configured

            try:
                usb.util.claim_interface(self.dev, INTERFACE)
                print(f"Połączono z Trofeo LCD ({LCD_WIDTH}x{LCD_HEIGHT})")
                self._initialized = False
                return True
            except usb.core.USBError as e:
                last_error = e
                if self._is_resource_busy(e):
                    # Best-effort recovery for stale libusb/WinUSB ownership after
                    # interrupted runs. Some units need a device reset before the
                    # interface becomes claimable again.
                    try:
                        usb.util.release_interface(self.dev, INTERFACE)
                    except Exception:
                        pass
                    try:
                        self.dev.reset()
                    except Exception:
                        pass
                try:
                    usb.util.dispose_resources(self.dev)
                except Exception:
                    pass
                self.dev = None
                if attempt < retries:
                    time.sleep(max(retry_delay, 1.0 if self._is_resource_busy(e) else retry_delay))
                    continue
                if self._is_resource_busy(e):
                    print(
                        "BŁĄD: Interfejs USB zajęty (Errno 16 Resource busy). "
                        "Zamknij inne procesy: replay_from_pcap.py / trofeo_lcd.py"
                    )
                else:
                    print(f"BŁĄD: Nie można przejąć interfejsu: {e}")
                return False

        print(f"BŁĄD połączenia: {last_error}")
        return False

    def recover_endpoints(self, delay=RECOVERY_DELAY):
        """
        Best-effort recovery after protocol errors.
        """
        if not self.dev:
            return

        for endpoint in (EP_OUT, EP_IN):
            try:
                usb.util.clear_halt(self.dev, endpoint)
            except Exception:
                pass

        if delay > 0:
            time.sleep(delay)

    def drain_in(self, timeout_ms=50, max_reads=32):
        """
        Drain pending packets from EP IN to stabilize session state.
        """
        if not self.dev:
            return 0

        drained = 0
        for _ in range(max_reads):
            try:
                _ = bytes(self.dev.read(EP_IN, ACK_READ_SIZE, timeout_ms))
                drained += 1
            except usb.core.USBTimeoutError:
                break
            except Exception:
                break
        return drained

    def reset_device(self, delay=USB_RESET_DELAY):
        """
        Hard reset the USB device through libusb.
        """
        if not self.dev:
            return False

        reattach_kernel = self._reattach_kernel
        try:
            self.dev.reset()
        except usb.core.USBError as e:
            print(f"BŁĄD resetu USB: {e}")
            return False

        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

        self.dev = None
        self._reattach_kernel = reattach_kernel
        self._initialized = False

        if delay > 0:
            time.sleep(delay)

        return self.connect()

    def disconnect(self):
        """Release the USB device."""
        if self.dev:
            try:
                usb.util.release_interface(self.dev, INTERFACE)
            except Exception:
                pass
            try:
                if self._reattach_kernel:
                    self.dev.attach_kernel_driver(INTERFACE)
            except Exception:
                pass
            try:
                usb.util.dispose_resources(self.dev)
            except Exception:
                pass
            self.dev = None
            self._reattach_kernel = False
            self._initialized = False

    def encode_image_to_jpeg(self, image):
        """
        Resize/convert an image and encode it using the current JPEG settings.
        """
        if image.size != (LCD_WIDTH, LCD_HEIGHT):
            image = image.resize((LCD_WIDTH, LCD_HEIGHT), Image.LANCZOS)

        if image.mode != 'RGB':
            image = image.convert('RGB')

        buf = io.BytesIO()
        save_kwargs = {
            'format': 'JPEG',
            'quality': JPEG_QUALITY,
            'subsampling': JPEG_SUBSAMPLING,
            'progressive': JPEG_PROGRESSIVE,
            'optimize': False,
            'dpi': (96, 96),
        }
        if JPEG_RESTART_MARKER_ROWS and JPEG_RESTART_MARKER_ROWS > 0:
            save_kwargs['restart_marker_rows'] = int(JPEG_RESTART_MARKER_ROWS)
        image.save(buf, **save_kwargs)
        return image, buf.getvalue()

    @staticmethod
    def summarize_ack(ack: bytes) -> AckSummary | None:
        if len(ack) < 9:
            return None
        return AckSummary(
            command=ack[0],
            marker=ack[1],
            status_byte=ack[8],
            raw=ack,
        )

    def _build_header(self, jpeg_size, seq_num, seq_unwrapped=None):
        """
        Build 16-byte protocol header for a chunk.

        Format (from USB capture analysis):
          [0]    = 0x01 (command: send image)
          [1]    = 0xFF (marker)
          [2-5]  = JPEG total size or frame metadata (LE uint32)
          [6]    = 0x00
          [7]    = 0xF0
          [8]    = 0x01
          [9]    = 0x01
          [10]   = frame counter (low byte)
          [11]   = sequence number within frame (increments by 8)
          [12-15]= 0x00 padding
        """
        header = bytearray(16)
        header[0] = 0x01
        header[1] = 0xFF
        # Bytes 2-5: observed to contain values related to data
        struct.pack_into('<I', header, 2, jpeg_size & 0xFFFFFFFF)
        # Current capture profile (dzis.pcapng): byte6..8 = f0 01 01
        header[6] = 0xF0
        header[7] = 0x01
        header[8] = 0x01
        b9_value = self.header_b9 if self.header_b9 is not None else self.estimate_header_b9(jpeg_size)
        header[9] = b9_value & 0xFF
        header[10] = self.header_byte10 & 0xFF
        header[11] = seq_num
        if self.buffer_index_override is not None:
            header[12] = self.buffer_index_override & 0xFF
        elif seq_unwrapped is not None:
            # Observed in capture: byte[12] is effectively the high byte
            # of the sequence counter before low-byte wrap.
            header[12] = (seq_unwrapped >> 8) & 0xFF
        elif self.buffer_index_mode == BUFFER_INDEX_MODE_CYCLE3:
            header[12] = self.frame_counter % 3
        else:
            header[12] = 0x00
        # 13-15 stay zero
        return bytes(header)

    def build_header(
        self,
        jpeg_size,
        seq_num,
        seq_unwrapped,
        chunk_payload_len,
        chunk_total_size,
        header_size_mode=HEADER_SIZE_MODE_JPEG,
        header_size_override=None,
        frame_counter_override=None,
        is_final_packet=False,
    ):
        """
        Build header with configurable uncertain fields for live testing.
        """
        header = bytearray(self._build_header(jpeg_size, seq_num, seq_unwrapped=seq_unwrapped))

        if header_size_override is not None:
            value = header_size_override
        else:
            if header_size_mode == HEADER_SIZE_MODE_JPEG:
                value = jpeg_size
            elif header_size_mode == HEADER_SIZE_MODE_CHUNK:
                value = chunk_total_size
            elif header_size_mode == HEADER_SIZE_MODE_REMAINING:
                value = chunk_payload_len
            else:
                raise ValueError(f"Nieznany tryb header size field: {header_size_mode}")

        struct.pack_into('<I', header, 2, value & 0xFFFFFFFF)

        # When bytes [2..5] are overridden to the real JPEG size, byte [9]
        # must track that same effective value instead of the padded transfer size.
        if self.header_b9 is None:
            header[9] = self.estimate_header_b9(value) & 0xFF

        # Captures show a different byte[6..8] signature for the trailing 2048B packet:
        #   [6] = low byte of JPEG size, [7] = 0x00, [8] = 0x01
        if is_final_packet and chunk_total_size == LAST_CHUNK_SIZE:
            header[6] = value & 0xFF
            header[7] = 0x00
            header[8] = 0x01

        if frame_counter_override is not None:
            header[10] = frame_counter_override & 0xFF

        return bytes(header)

    def build_packet_plans(self, jpeg_size, final_packet_mode=FINAL_PACKET_MODE_AUTO):
        """
        Build the chunking plan for a JPEG frame.

        `auto` sends full 4096-byte packets for all complete 4080-byte payloads and a
        final short packet sized exactly to the remaining JPEG data + 16-byte header.
        Padding modes keep the historical fixed-size behavior for comparison on hardware.
        """
        if jpeg_size <= 0:
            raise ValueError("JPEG musi mieć dodatni rozmiar")

        if final_packet_mode not in {
            FINAL_PACKET_MODE_AUTO,
            FINAL_PACKET_MODE_PAD_2048,
            FINAL_PACKET_MODE_PAD_4096,
        }:
            raise ValueError(f"Nieznany tryb final packet: {final_packet_mode}")

        plans = []
        offset = 0
        seq = 0

        while offset < jpeg_size:
            remaining = jpeg_size - offset

            if final_packet_mode == FINAL_PACKET_MODE_PAD_2048 and remaining > DATA_PER_LAST:
                if remaining > DATA_PER_CHUNK + DATA_PER_LAST:
                    payload_len = DATA_PER_CHUNK
                else:
                    # Leave exactly one 2048-byte final packet worth of data.
                    payload_len = remaining - DATA_PER_LAST
                total_size = CHUNK_SIZE
            elif remaining > DATA_PER_CHUNK:
                payload_len = DATA_PER_CHUNK
                total_size = CHUNK_SIZE
            else:
                payload_len = remaining
                if final_packet_mode == FINAL_PACKET_MODE_AUTO:
                    total_size = HEADER_SIZE + payload_len
                elif final_packet_mode == FINAL_PACKET_MODE_PAD_2048:
                    total_size = LAST_CHUNK_SIZE
                else:
                    total_size = CHUNK_SIZE

            plans.append(PacketPlan(payload_len=payload_len, total_size=total_size, seq_num=seq))
            offset += payload_len
            seq = (seq + 8) & 0xFF

        return plans

    def apply_sequence_mode(self, plans, seq_step=8, constant_seq=None):
        """
        Apply a test sequence pattern to an existing packet plan.
        """
        updated = []
        seq = 0
        for plan in plans:
            if constant_seq is not None:
                seq_num = constant_seq & 0xFF
            else:
                seq_num = seq & 0xFF
                seq = (seq + seq_step) & 0xFF
            updated.append(PacketPlan(plan.payload_len, plan.total_size, seq_num))
        return updated

    def send_jpeg(
        self,
        jpeg_data,
        final_packet_mode=FINAL_PACKET_MODE_AUTO,
        header_size_mode=HEADER_SIZE_MODE_JPEG,
        header_size_override=None,
        frame_counter_override=None,
        packet_debug=False,
        ack_every_packet=DEFAULT_ACK_EVERY_PACKET,
        inter_packet_delay=0.0,
        seq_step=8,
        constant_seq=None,
        drain_in_after_packet=False,
        send_commit=False,
        commit_mode=COMMIT_MODE_BASIC,
        limit_packets=None,
        extra_read_after_packet=None,
        ack_timeout_ms=USB_TIMEOUT,
        ack_on_seq0_only=False,
        packet_templates=None,
    ):
        """
        Send a JPEG image to the LCD.

        Protocol:
        1. Split JPEG into chunks with 16-byte headers
        2. Send each chunk as bulk OUT transfer
        3. Final packet mode is configurable because the last-packet behavior is still
           one of the few uncertain protocol details
        4. Read 512-byte ACK from EP1 IN
        """
        if not self.dev:
            raise RuntimeError("Nie połączono z urządzeniem")

        if self.init_enabled and (self.init_every_frame or not self._initialized):
            init_ok = self._init_device(packet_debug=packet_debug, timeout_ms=ack_timeout_ms)
            if not init_ok:
                if self.init_strict:
                    return False
                # If INIT failed, clear potential endpoint halt before first JPEG packet.
                self.recover_endpoints(delay=0.05)
                self.drain_in(timeout_ms=20, max_reads=8)
                if packet_debug:
                    print("  init fallback: kontynuuję bez INIT (best-effort)")

        jpeg_size = len(jpeg_data)
        offset = 0

        if packet_templates:
            packet_entries = []
            for template in packet_templates:
                total_size = len(template)
                seq_num = template[11] if len(template) > 11 else 0
                subchunks = []
                payload_len = 0
                for sub_offset in range(0, total_size, 512):
                    if sub_offset + HEADER_SIZE > total_size:
                        break
                    if template[sub_offset] != 0x01 or template[sub_offset + 1] != 0xFF:
                        continue
                    sub_payload_len = int.from_bytes(template[sub_offset + 6:sub_offset + 8], "little")
                    if sub_payload_len <= 0 or sub_payload_len > (512 - HEADER_SIZE):
                        continue
                    payload_len += sub_payload_len
                    subchunks.append((sub_offset, sub_payload_len))

                packet_entries.append(
                    {
                        "payload_len": payload_len,
                        "total_size": total_size,
                        "seq_num": seq_num,
                        "header": bytes(template[:HEADER_SIZE]),
                        "template": bytes(template),
                        "subchunks": subchunks,
                    }
                )
        else:
            packet_plans = self.build_packet_plans(jpeg_size, final_packet_mode=final_packet_mode)
            packet_plans = self.apply_sequence_mode(packet_plans, seq_step=seq_step, constant_seq=constant_seq)
            packet_entries = []
            for index, plan in enumerate(packet_plans, start=1):
                header = self.build_header(
                    jpeg_size=jpeg_size,
                    seq_num=plan.seq_num,
                    seq_unwrapped=(index - 1) * seq_step if constant_seq is None else None,
                    chunk_payload_len=plan.payload_len,
                    chunk_total_size=plan.total_size,
                    header_size_mode=header_size_mode,
                    header_size_override=header_size_override,
                    frame_counter_override=frame_counter_override,
                    is_final_packet=(index == len(packet_plans)),
                )
                packet_entries.append(
                    {
                        "payload_len": plan.payload_len,
                        "total_size": plan.total_size,
                        "seq_num": plan.seq_num,
                        "header": header,
                        "template": None,
                        "subchunks": None,
                    }
                )

        if limit_packets is not None:
            packet_entries = packet_entries[:limit_packets]

        total_payload_capacity = sum(entry["payload_len"] for entry in packet_entries)
        if total_payload_capacity < jpeg_size:
            raise ValueError(
                f"Szablon pakietow ma za malo miejsca: {total_payload_capacity} < {jpeg_size}"
            )

        for index, entry in enumerate(packet_entries, start=1):
            payload_len = entry["payload_len"]
            total_size = entry["total_size"]
            seq_num = entry["seq_num"]
            header = entry["header"]

            if entry["template"] is not None:
                packet = bytearray(entry["template"])
                packet_payload_written = 0
                for sub_offset, sub_payload_len in entry["subchunks"]:
                    sub_data = jpeg_data[offset:offset + sub_payload_len]
                    payload_start = sub_offset + HEADER_SIZE
                    payload_end = payload_start + sub_payload_len
                    packet[payload_start:payload_end] = b"\x00" * sub_payload_len
                    packet[payload_start:payload_start + len(sub_data)] = sub_data
                    offset += len(sub_data)
                    packet_payload_written += len(sub_data)
                chunk_data = jpeg_data[offset - packet_payload_written:offset]
            else:
                chunk_data = jpeg_data[offset:offset + payload_len]
                packet = bytearray(total_size)
                packet[:HEADER_SIZE] = header
                packet[HEADER_SIZE:HEADER_SIZE + len(chunk_data)] = chunk_data
                offset += len(chunk_data)

            if packet_debug:
                print(
                    f"  packet {index}/{len(packet_entries)}:"
                    f" payload={payload_len} total={total_size}"
                    f" seq=0x{seq_num:02x} hdr={header.hex(' ')}"
                )

            # Send via bulk OUT
            try:
                self.dev.write(EP_OUT, bytes(packet), USB_TIMEOUT)
            except usb.core.USBError as e:
                print(
                    f"BŁĄD zapisu USB przy pakiecie {index}/{len(packet_entries)} "
                    f"(payload={payload_len}, total={total_size}, seq=0x{seq_num:02x}): {e}"
                )
                return False

            should_read_ack = ack_every_packet and (not ack_on_seq0_only or seq_num == 0)
            if should_read_ack:
                try:
                    ack = bytes(self.dev.read(EP_IN, ACK_READ_SIZE, ack_timeout_ms))
                    if packet_debug:
                        ack_summary = self.summarize_ack(ack)
                        if ack_summary is None:
                            print(f"    ack packet {index}: {ack.hex(' ')}")
                        else:
                            print(
                                f"    ack packet {index}:"
                                f" cmd=0x{ack_summary.command:02x}"
                                f" marker=0x{ack_summary.marker:02x}"
                                f" status=0x{ack_summary.status_byte:02x}"
                                f" raw={ack[:16].hex(' ')}..."
                            )
                except usb.core.USBTimeoutError:
                    if packet_debug:
                        print(f"    ack packet {index}: <timeout>")
                except usb.core.USBError as e:
                    print(f"BŁĄD odczytu ACK po pakiecie {index}: {e}")
                    return False

                if drain_in_after_packet:
                    drain_count = 0
                    while True:
                        try:
                            extra = bytes(self.dev.read(EP_IN, ACK_READ_SIZE, 50))
                        except usb.core.USBTimeoutError:
                            break
                        except usb.core.USBError as e:
                            print(f"BŁĄD dodatkowego odczytu IN po pakiecie {index}: {e}")
                            return False
                        drain_count += 1
                        if packet_debug:
                            print(f"    ack-extra packet {index}.{drain_count}: {extra.hex(' ')}")

                if extra_read_after_packet is not None and index == extra_read_after_packet:
                    try:
                        extra = bytes(self.dev.read(EP_IN, ACK_READ_SIZE, 200))
                        if packet_debug:
                            ack_summary = self.summarize_ack(extra)
                            if ack_summary is None:
                                print(f"    sync-read after packet {index}: {extra.hex(' ')}")
                            else:
                                print(
                                    f"    sync-read after packet {index}:"
                                    f" cmd=0x{ack_summary.command:02x}"
                                    f" marker=0x{ack_summary.marker:02x}"
                                    f" status=0x{ack_summary.status_byte:02x}"
                                    f" raw={extra[:16].hex(' ')}..."
                                )
                    except usb.core.USBTimeoutError:
                        if packet_debug:
                            print(f"    sync-read after packet {index}: <timeout>")
                    except usb.core.USBError as e:
                        print(f"BŁĄD dodatkowego sync-read po pakiecie {index}: {e}")
                        return False

            if inter_packet_delay > 0:
                time.sleep(inter_packet_delay)

        # Read ACK from device
        if not ack_every_packet:
            try:
                ack = bytes(self.dev.read(EP_IN, ACK_READ_SIZE, ack_timeout_ms))
                if packet_debug:
                    print(f"  final ack: {ack.hex(' ')}")
            except usb.core.USBTimeoutError:
                if packet_debug:
                    print("  final ack: <timeout>")
            except usb.core.USBError as e:
                print(f"BŁĄD odczytu final ACK: {e}")
                return False

        if send_commit:
            self.send_commit_packet(jpeg_size, packet_debug=packet_debug, commit_mode=commit_mode)

        self.frame_counter += 1
        return True

    def send_image(
        self,
        image,
        final_packet_mode=FINAL_PACKET_MODE_AUTO,
        header_size_mode=HEADER_SIZE_MODE_JPEG,
        header_size_override=None,
        frame_counter_override=None,
        packet_debug=False,
        ack_every_packet=DEFAULT_ACK_EVERY_PACKET,
        inter_packet_delay=0.0,
        seq_step=8,
        constant_seq=None,
        drain_in_after_packet=False,
        send_commit=False,
        commit_mode=COMMIT_MODE_BASIC,
        limit_packets=None,
        extra_read_after_packet=None,
        ack_timeout_ms=USB_TIMEOUT,
        ack_on_seq0_only=False,
        jpeg_pad_to_size=None,
        packet_templates=None,
    ):
        """
        Send a PIL Image to the LCD (auto-resize and convert to JPEG).
        """
        _, jpeg_data = self.encode_image_to_jpeg(image)
        jpeg_data = self.pad_jpeg_payload(jpeg_data, jpeg_pad_to_size)

        return self.send_jpeg(
            jpeg_data,
            final_packet_mode=final_packet_mode,
            header_size_mode=header_size_mode,
            header_size_override=header_size_override,
            frame_counter_override=frame_counter_override,
            packet_debug=packet_debug,
            ack_every_packet=ack_every_packet,
            inter_packet_delay=inter_packet_delay,
            seq_step=seq_step,
            constant_seq=constant_seq,
            drain_in_after_packet=drain_in_after_packet,
            send_commit=send_commit,
            commit_mode=commit_mode,
            limit_packets=limit_packets,
            extra_read_after_packet=extra_read_after_packet,
            ack_timeout_ms=ack_timeout_ms,
            ack_on_seq0_only=ack_on_seq0_only,
            packet_templates=packet_templates,
        )

    def send_file(
        self,
        filepath,
        final_packet_mode=FINAL_PACKET_MODE_AUTO,
        header_size_mode=HEADER_SIZE_MODE_JPEG,
        header_size_override=None,
        frame_counter_override=None,
        packet_debug=False,
        ack_every_packet=DEFAULT_ACK_EVERY_PACKET,
        inter_packet_delay=0.0,
        seq_step=8,
        constant_seq=None,
        drain_in_after_packet=False,
        send_commit=False,
        commit_mode=COMMIT_MODE_BASIC,
        limit_packets=None,
        extra_read_after_packet=None,
        raw_jpeg_passthrough=False,
        ack_timeout_ms=USB_TIMEOUT,
        ack_on_seq0_only=False,
        jpeg_pad_to_size=None,
        packet_templates=None,
    ):
        """Send an image file to the LCD."""
        try:
            path_lower = filepath.lower()
            if raw_jpeg_passthrough and (path_lower.endswith(".jpg") or path_lower.endswith(".jpeg")):
                with open(filepath, "rb") as f:
                    jpeg_data = f.read()
                jpeg_data = self.pad_jpeg_payload(jpeg_data, jpeg_pad_to_size)
                return self.send_jpeg(
                    jpeg_data,
                    final_packet_mode=final_packet_mode,
                    header_size_mode=header_size_mode,
                    header_size_override=header_size_override,
                    frame_counter_override=frame_counter_override,
                    packet_debug=packet_debug,
                    ack_every_packet=ack_every_packet,
                    inter_packet_delay=inter_packet_delay,
                    seq_step=seq_step,
                    constant_seq=constant_seq,
                    drain_in_after_packet=drain_in_after_packet,
                    send_commit=send_commit,
                    commit_mode=commit_mode,
                    limit_packets=limit_packets,
                    extra_read_after_packet=extra_read_after_packet,
                    ack_timeout_ms=ack_timeout_ms,
                    ack_on_seq0_only=ack_on_seq0_only,
                    packet_templates=packet_templates,
                )

            img = Image.open(filepath)
            return self.send_image(
                img,
                final_packet_mode=final_packet_mode,
                header_size_mode=header_size_mode,
                header_size_override=header_size_override,
                frame_counter_override=frame_counter_override,
                packet_debug=packet_debug,
                ack_every_packet=ack_every_packet,
                inter_packet_delay=inter_packet_delay,
                seq_step=seq_step,
                constant_seq=constant_seq,
                drain_in_after_packet=drain_in_after_packet,
                send_commit=send_commit,
                commit_mode=commit_mode,
                limit_packets=limit_packets,
                extra_read_after_packet=extra_read_after_packet,
                ack_timeout_ms=ack_timeout_ms,
                ack_on_seq0_only=ack_on_seq0_only,
                jpeg_pad_to_size=jpeg_pad_to_size,
                packet_templates=packet_templates,
            )
        except Exception as e:
            print(f"BŁĄD: Nie można otworzyć {filepath}: {e}")
            return False


def create_test_pattern():
    """Generate a colorful test pattern."""
    img = Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Color bars
    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (0, 255, 255), (255, 0, 255),
        (255, 128, 0), (128, 0, 255),
    ]
    bar_width = LCD_WIDTH // len(colors)
    for i, color in enumerate(colors):
        x = i * bar_width
        draw.rectangle([x, 0, x + bar_width, LCD_HEIGHT], fill=color)

    # Text overlay
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except (IOError, OSError):
        font = ImageFont.load_default()

    text = "Trofeo LCD - Linux Driver Test"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (LCD_WIDTH - tw) // 2
    ty = (LCD_HEIGHT - th) // 2
    # Shadow
    draw.text((tx + 2, ty + 2), text, fill=(0, 0, 0), font=font)
    draw.text((tx, ty), text, fill=(255, 255, 255), font=font)

    return img


_CPU_SNAPSHOT = None
_CPU_CORE_SNAPSHOT = None
_MONITOR_THEME_BG = None
_MONITOR_TEXTURE_BG = None
_MONITOR_PACKET_TEMPLATE = None
_MONITOR_FITTED_ALPHA = MONITOR_NOISE_ALPHA
_MONITOR_THEME_DOCUMENT = None
_MONITOR_STATS_PROVIDER = None


def _parse_proc_stat():
    total = None
    cores = []

    with open('/proc/stat', 'r', encoding='utf-8') as f:
        for line in f:
            if not line.startswith('cpu'):
                break
            parts = line.split()
            if len(parts) < 5:
                continue
            label = parts[0]
            values = [int(x) for x in parts[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            busy = sum(values) - idle
            pair = (busy, idle)
            if label == 'cpu':
                total = pair
            elif label.startswith('cpu') and label[3:].isdigit():
                cores.append(pair)

    return total, cores


def read_cpu_usage_percent():
    """
    Return non-blocking CPU usage sample based on /proc/stat deltas.
    The first call returns "N/A" because no baseline exists yet.
    """
    global _CPU_SNAPSHOT
    current_total, _ = _parse_proc_stat()
    if current_total is None:
        return "N/A"

    prev = _CPU_SNAPSHOT
    _CPU_SNAPSHOT = current_total
    if prev is None:
        return "N/A"

    busy_delta = current_total[0] - prev[0]
    idle_delta = current_total[1] - prev[1]
    total_delta = busy_delta + idle_delta
    if total_delta <= 0:
        return "N/A"
    return f"{(busy_delta * 100.0 / total_delta):.0f}%"


def read_cpu_core_summary():
    """
    Return per-core usage summary as (avg_percent, max_percent, core_count) or None.
    Non-blocking: first call typically returns None.
    """
    global _CPU_CORE_SNAPSHOT
    _, current_cores = _parse_proc_stat()
    if not current_cores:
        return None

    prev = _CPU_CORE_SNAPSHOT
    _CPU_CORE_SNAPSHOT = current_cores
    if prev is None or len(prev) != len(current_cores):
        return None

    usages = []
    for old_pair, new_pair in zip(prev, current_cores):
        busy_delta = new_pair[0] - old_pair[0]
        idle_delta = new_pair[1] - old_pair[1]
        total_delta = busy_delta + idle_delta
        if total_delta > 0:
            usages.append(busy_delta * 100.0 / total_delta)

    if not usages:
        return None

    avg_usage = sum(usages) / len(usages)
    max_usage = max(usages)
    return avg_usage, max_usage, len(usages)


def read_load_average():
    """Return Linux load average string '1m/5m/15m'."""
    try:
        with open('/proc/loadavg', 'r', encoding='utf-8') as f:
            parts = f.read().split()
        if len(parts) >= 3:
            return f"{parts[0]}/{parts[1]}/{parts[2]}"
    except Exception:
        pass
    return "N/A"


def read_cpu_freq_ghz():
    """Return average current CPU frequency in GHz from /proc/cpuinfo."""
    try:
        freqs = []
        with open('/proc/cpuinfo', 'r', encoding='utf-8') as f:
            for line in f:
                if line.lower().startswith('cpu mhz'):
                    value = float(line.split(':', 1)[1].strip())
                    freqs.append(value)
        if freqs:
            avg_mhz = sum(freqs) / len(freqs)
            return f"{avg_mhz / 1000.0:.2f} GHz"
    except Exception:
        pass
    return "N/A"


def read_cpu_temperature():
    """
    Return best-effort CPU package temperature.
    Tries thermal zones and hwmon sensors, filtering to sane values.
    """
    candidates = []

    try:
        for zone in os.listdir('/sys/class/thermal'):
            if not zone.startswith('thermal_zone'):
                continue
            base = f'/sys/class/thermal/{zone}'
            temp_path = f'{base}/temp'
            type_path = f'{base}/type'
            if not os.path.exists(temp_path):
                continue
            try:
                with open(temp_path, 'r', encoding='utf-8') as f:
                    raw = int(f.read().strip())
                c = raw / 1000.0 if raw > 1000 else float(raw)
                if not (10.0 <= c <= 120.0):
                    continue
                label = ''
                if os.path.exists(type_path):
                    with open(type_path, 'r', encoding='utf-8') as f:
                        label = f.read().strip().lower()
                score = 0
                if any(x in label for x in ('cpu', 'x86_pkg_temp', 'package', 'tctl', 'tdie')):
                    score = 2
                elif label:
                    score = 1
                candidates.append((score, c))
            except Exception:
                continue
    except Exception:
        pass

    try:
        for hw in os.listdir('/sys/class/hwmon'):
            base = f'/sys/class/hwmon/{hw}'
            for entry in os.listdir(base):
                if not entry.startswith('temp') or not entry.endswith('_input'):
                    continue
                temp_path = f'{base}/{entry}'
                label_path = f'{base}/{entry[:-6]}_label'
                try:
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        raw = int(f.read().strip())
                    c = raw / 1000.0 if raw > 1000 else float(raw)
                    if not (10.0 <= c <= 120.0):
                        continue
                    label = ''
                    if os.path.exists(label_path):
                        with open(label_path, 'r', encoding='utf-8') as f:
                            label = f.read().strip().lower()
                    score = 0
                    if any(x in label for x in ('cpu', 'package', 'tctl', 'tdie')):
                        score = 3
                    elif label:
                        score = 1
                    candidates.append((score, c))
                except Exception:
                    continue
    except Exception:
        pass

    if not candidates:
        return "N/A"

    best = sorted(candidates, key=lambda x: (x[0], x[1]), reverse=True)[0][1]
    return f"{best:.0f}°C"


def _get_monitor_background(alpha=MONITOR_NOISE_ALPHA):
    """
    Build and cache a darker, cleaner monitor background without reusing the
    visible Windows/TRCC image as a texture source.
    """
    global _MONITOR_THEME_BG
    global _MONITOR_TEXTURE_BG

    if _MONITOR_THEME_BG is None:
        theme = Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT), (9, 14, 22))
        draw = ImageDraw.Draw(theme)

        # Subtle vertical gradient.
        for y in range(LCD_HEIGHT):
            t = y / max(1, LCD_HEIGHT - 1)
            r = int(8 + 8 * t)
            g = int(14 + 18 * t)
            b = int(22 + 26 * t)
            draw.line((0, y, LCD_WIDTH, y), fill=(r, g, b))

        # Calm bands instead of TV-style noise.
        for x in range(0, LCD_WIDTH, 120):
            draw.rectangle((x, 0, min(LCD_WIDTH, x + 2), LCD_HEIGHT), fill=(18, 28, 40))
        for y in range(24, LCD_HEIGHT, 48):
            draw.line((24, y, LCD_WIDTH - 24, y), fill=(20, 34, 48), width=1)

        # Soft dashboard glow regions.
        draw.rounded_rectangle((16, 12, LCD_WIDTH - 16, 74), radius=18, fill=(14, 22, 34))
        draw.rounded_rectangle((18, 80, 474, 296), radius=20, fill=(12, 20, 32))
        draw.rounded_rectangle((476, 80, 938, 196), radius=20, fill=(12, 20, 32))
        draw.rounded_rectangle((972, 80, 1320, 196), radius=20, fill=(12, 20, 32))
        draw.rounded_rectangle((18, LCD_HEIGHT - 64, 626, LCD_HEIGHT - 8), radius=14, fill=(12, 20, 32))

        _MONITOR_THEME_BG = theme

    if _MONITOR_TEXTURE_BG is None:
        texture = Image.effect_noise((LCD_WIDTH, LCD_HEIGHT), 22).convert('L')
        texture = texture.filter(ImageFilter.GaussianBlur(radius=1.2))
        texture_rgb = Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT))
        px_in = texture.load()
        px_out = texture_rgb.load()
        for y in range(LCD_HEIGHT):
            for x in range(LCD_WIDTH):
                v = px_in[x, y]
                px_out[x, y] = (10 + v // 10, 16 + v // 9, 24 + v // 8)
        _MONITOR_TEXTURE_BG = texture_rgb

    return Image.blend(_MONITOR_THEME_BG, _MONITOR_TEXTURE_BG, alpha)


def _get_monitor_packet_template():
    """
    Load the first known-good frame packet layout from dzis.pcapng.
    Headers from this capture are reused verbatim in monitor mode.
    """
    global _MONITOR_PACKET_TEMPLATE

    if _MONITOR_PACKET_TEMPLATE is not None:
        return _MONITOR_PACKET_TEMPLATE

    pcap_path = Path(__file__).resolve().with_name("dzis.pcapng")
    if not pcap_path.exists():
        _MONITOR_PACKET_TEMPLATE = []
        return _MONITOR_PACKET_TEMPLATE

    try:
        from replay_from_pcap import parse_usbpcap_bulk_payloads, extract_init_and_frames

        sig = parse_usbpcap_bulk_payloads(pcap_path)
        _, frames = extract_init_and_frames(sig)
        if frames:
            _MONITOR_PACKET_TEMPLATE = [bytes(pkt) for pkt in frames[0]]
        else:
            _MONITOR_PACKET_TEMPLATE = []
    except Exception:
        _MONITOR_PACKET_TEMPLATE = []

    return _MONITOR_PACKET_TEMPLATE


def _get_monitor_theme_document() -> ThemeDocument:
    global _MONITOR_THEME_DOCUMENT

    if _MONITOR_THEME_DOCUMENT is not None:
        return _MONITOR_THEME_DOCUMENT

    theme_path = Path(__file__).resolve().parent / "themes" / "obsidian_pulse.json"
    _MONITOR_THEME_DOCUMENT = load_theme_document(theme_path)
    return _MONITOR_THEME_DOCUMENT


def _get_monitor_stats_provider() -> StatsProvider:
    global _MONITOR_STATS_PROVIDER

    if _MONITOR_STATS_PROVIDER is None:
        _MONITOR_STATS_PROVIDER = StatsProvider()
    return _MONITOR_STATS_PROVIDER


def render_monitor_theme_image(background_alpha: float = MONITOR_NOISE_ALPHA) -> Image.Image:
    theme = _get_monitor_theme_document()
    theme_data = deepcopy(theme.data)
    theme_data["background"]["texture_alpha"] = float(background_alpha)
    return render_theme_document(
        ThemeDocument(theme_data),
        base_dir=Path(__file__).resolve().parent,
        stats_provider=_get_monitor_stats_provider(),
    )


def create_monitor_image(background_alpha=MONITOR_NOISE_ALPHA):
    """Generate a simple system monitoring image."""
    img = _get_monitor_background(background_alpha).copy()
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except (IOError, OSError):
        font_big = font_med = font_sm = ImageFont.load_default()

    # Read system info
    cpu_temp = "N/A"
    cpu_usage = "N/A"
    cpu_cores = "N/A"
    cpu_freq = "N/A"
    load_avg = "N/A"
    mem_info = "N/A"
    hostname = "unknown"

    try:
        hostname = os.uname().nodename
    except Exception:
        pass

    try:
        cpu_temp = read_cpu_temperature()
        cpu_usage = read_cpu_usage_percent()
        core_summary = read_cpu_core_summary()
        if core_summary is not None:
            avg_usage, max_usage, core_count = core_summary
            cpu_cores = f"{core_count}c avg {avg_usage:.0f}% max {max_usage:.0f}%"
        cpu_freq = read_cpu_freq_ghz()
        load_avg = read_load_average()
    except Exception:
        pass

    # Memory
    try:
        with open('/proc/meminfo') as f:
            lines = f.readlines()
            total = int(lines[0].split()[1]) // 1024
            avail = int(lines[2].split()[1]) // 1024
            used = total - avail
            mem_info = f"{used}/{total} MB ({used*100//total}%)"
    except Exception:
        pass

    # Draw layout
    draw.rounded_rectangle((20, 16, 1885, 70), radius=14, fill=(0, 0, 0))
    draw.rounded_rectangle((20, 82, 470, 290), radius=18, fill=(0, 0, 0))
    draw.rounded_rectangle((480, 82, 930, 190), radius=18, fill=(0, 0, 0))
    draw.rounded_rectangle((980, 82, 1310, 190), radius=18, fill=(0, 0, 0))
    draw.rounded_rectangle((20, LCD_HEIGHT - 58, 620, LCD_HEIGHT - 12), radius=12, fill=(0, 0, 0))

    y = 20
    draw.text((40, y), f"⬡ {hostname}", fill=(0, 200, 255), font=font_big)
    draw.text((LCD_WIDTH - 300, y), time.strftime("%H:%M:%S"), fill=(200, 200, 200), font=font_big)

    y = 90
    # CPU section
    draw.text((40, y), "CPU", fill=(255, 100, 100), font=font_med)
    draw.text((40, y + 36), f"Usage: {cpu_usage}", fill=(220, 220, 220), font=font_sm)
    draw.text((40, y + 64), f"Cores: {cpu_cores}", fill=(220, 220, 220), font=font_sm)
    draw.text((40, y + 92), f"Freq: {cpu_freq}", fill=(220, 220, 220), font=font_sm)
    draw.text((40, y + 120), f"Temp: {cpu_temp}", fill=(220, 220, 220), font=font_sm)
    draw.text((40, y + 148), f"Load: {load_avg}", fill=(220, 220, 220), font=font_sm)

    # Memory section
    draw.text((500, y), "MEMORY", fill=(100, 255, 100), font=font_med)
    draw.text((500, y + 40), mem_info, fill=(220, 220, 220), font=font_sm)

    # Uptime
    try:
        with open('/proc/uptime') as f:
            uptime_sec = float(f.read().split()[0])
            hours = int(uptime_sec // 3600)
            mins = int((uptime_sec % 3600) // 60)
            draw.text((1000, y), "UPTIME", fill=(255, 200, 100), font=font_med)
            draw.text((1000, y + 40), f"{hours}h {mins}m", fill=(220, 220, 220), font=font_sm)
    except Exception:
        pass

    # Footer
    draw.text((40, LCD_HEIGHT - 40), "Trofeo LCD • Linux Open Driver",
              fill=(100, 100, 120), font=font_sm)

    return img.transpose(Image.ROTATE_180)


def main():
    parser = argparse.ArgumentParser(
        description='Thermalright Trofeo LCD Driver for Linux'
    )
    parser.add_argument('image', nargs='?', help='Image file to send')
    parser.add_argument('--test', action='store_true', help='Send test pattern')
    parser.add_argument('--monitor', action='store_true', help='System monitoring mode')
    parser.add_argument('--loop', action='store_true', help='Loop continuously')
    parser.add_argument('--interval', type=float, default=1.0, help='Update interval in seconds (default: 1.0)')
    parser.add_argument(
        '--skip-unchanged',
        action='store_true',
        help='In --loop file mode, do not resend unchanged image data except for keepalive sends',
    )
    parser.add_argument(
        '--keepalive-interval',
        type=float,
        default=0.5,
        help='Maximum seconds between unchanged --loop keepalive sends when --skip-unchanged is active',
    )
    parser.add_argument('--max-frames', type=int, default=0, help='Stop after N frames in --monitor/--loop modes (0 = infinite)')
    parser.add_argument('--repeat', type=int, default=1, help='Repeat the same frame N times (default: 1)')
    parser.add_argument('--frame-delay', type=float, default=0.0, help='Delay between repeated frames in seconds')
    parser.add_argument(
        '--frame-retries',
        type=int,
        default=0,
        help='Retry count per frame after send failure (default: 0)',
    )
    parser.add_argument(
        '--trcc-compatible',
        action='store_true',
        help='Apply stable profile based on working TRCC replay (timing/ACK/final packet)',
    )
    parser.add_argument(
        '--windows-capture-profile',
        action='store_true',
        help='Apply the 2026-05-16 Windows capture transport profile: 4096B packets, buf=0, ~0.5ms packet cadence, ACK at frame end',
    )
    parser.add_argument('--connect-retries', type=int, default=CONNECT_RETRIES, help='USB connect retries')
    parser.add_argument(
        '--connect-retry-delay',
        type=float,
        default=CONNECT_RETRY_DELAY,
        help='Delay between connect retries in seconds',
    )
    parser.add_argument(
        '--reconnect-on-fail',
        action='store_true',
        help='Disconnect/connect device before retrying a failed frame',
    )
    parser.add_argument(
        '--reconnect-delay',
        type=float,
        default=0.5,
        help='Delay in seconds before reconnect attempt after send failure',
    )
    parser.add_argument('--quality', type=int, default=85, help='JPEG quality 1-100 (default: 85)')
    parser.add_argument(
        '--subsampling',
        choices=['4:4:4', '4:2:2', '4:2:0'],
        default='4:2:0',
        help='JPEG chroma subsampling for protocol testing',
    )
    parser.add_argument(
        '--progressive',
        action='store_true',
        help='Use progressive JPEG instead of baseline for testing',
    )
    parser.add_argument(
        '--jpeg-restart-marker-rows',
        type=int,
        default=0,
        help='Insert JPEG restart markers every N MCU rows (0 = disabled)',
    )
    parser.add_argument(
        '--final-packet-mode',
        choices=[FINAL_PACKET_MODE_AUTO, FINAL_PACKET_MODE_PAD_2048, FINAL_PACKET_MODE_PAD_4096],
        default=FINAL_PACKET_MODE_AUTO,
        help='Last packet strategy: auto is default, padding modes help compare protocol variants',
    )
    parser.add_argument(
        '--header-size-mode',
        choices=[HEADER_SIZE_MODE_JPEG, HEADER_SIZE_MODE_CHUNK, HEADER_SIZE_MODE_REMAINING],
        default=HEADER_SIZE_MODE_JPEG,
        help='Interpretation of header bytes 2-5 for testing uncertain protocol fields',
    )
    parser.add_argument(
        '--header-size-override',
        type=lambda x: int(x, 0),
        default=None,
        help='Force header bytes 2-5 to a uint32 value (e.g. 0x78d8), overrides --header-size-mode',
    )
    parser.add_argument(
        '--frame-counter',
        type=int,
        default=None,
        help='Override header byte 10 for testing, e.g. 0',
    )
    parser.add_argument(
        '--skip-init',
        action='store_true',
        help='Skip cmd=0x02 INIT query before JPEG upload',
    )
    parser.add_argument(
        '--init-every-frame',
        action='store_true',
        help='Send cmd=0x02 INIT query before every frame (diagnostics)',
    )
    parser.add_argument(
        '--init-strict',
        action='store_true',
        help='Fail hard if INIT does not succeed (default: best-effort fallback)',
    )
    parser.add_argument(
        '--buffer-index-mode',
        choices=[BUFFER_INDEX_MODE_ZERO, BUFFER_INDEX_MODE_CYCLE3],
        default=BUFFER_INDEX_MODE_ZERO,
        help='Header byte [12] strategy: zero or cycle3 (0,1,2)',
    )
    parser.add_argument(
        '--buffer-index-override',
        type=int,
        default=None,
        help='Force header byte [12] for all packets',
    )
    parser.add_argument(
        '--header-b9',
        type=lambda x: int(x, 0),
        default=None,
        help='Set header byte [9]; if omitted, use auto estimate from JPEG size',
    )
    parser.add_argument(
        '--header-byte10',
        type=lambda x: int(x, 0),
        default=0x02,
        help='Set header byte [10] (default: 0x02)',
    )
    parser.add_argument(
        '--jpeg-pad-to-size',
        type=int,
        default=None,
        help='Pad encoded JPEG payload with zeros to this size before chunking (compat mode)',
    )
    parser.add_argument(
        '--ack-every-packet',
        dest='ack_every_packet',
        action='store_true',
        default=DEFAULT_ACK_EVERY_PACKET,
        help='Read EP IN after every OUT packet; this is the default',
    )
    parser.add_argument(
        '--ack-at-end-only',
        dest='ack_every_packet',
        action='store_false',
        help='Experimental legacy mode: read EP IN only once after the whole frame',
    )
    parser.add_argument(
        '--ack-timeout-ms',
        type=int,
        default=USB_TIMEOUT,
        help='Timeout for EP IN ACK reads in milliseconds (default: 5000)',
    )
    parser.add_argument(
        '--ack-on-seq0-only',
        action='store_true',
        help='Read ACK only when sequence byte is 0x00 (observed every 32 packets)',
    )
    parser.add_argument(
        '--inter-packet-delay',
        type=float,
        default=0.0,
        help='Sleep between OUT packets in seconds, e.g. 0.01',
    )
    parser.add_argument(
        '--seq-step',
        type=int,
        default=8,
        help='Sequence increment per packet, default 8; try 1 for protocol testing',
    )
    parser.add_argument(
        '--constant-seq',
        type=int,
        default=None,
        help='Force the same sequence byte for every packet, e.g. 0',
    )
    parser.add_argument(
        '--drain-in-after-packet',
        action='store_true',
        help='After each ACK, keep reading EP IN with a short timeout until it goes quiet',
    )
    parser.add_argument(
        '--send-commit',
        action='store_true',
        help='Send experimental short commit packets after the full frame upload',
    )
    parser.add_argument(
        '--commit-mode',
        choices=[COMMIT_MODE_BASIC, COMMIT_MODE_SCAN],
        default=COMMIT_MODE_BASIC,
        help='Commit packet set to use when --send-commit is enabled',
    )
    parser.add_argument(
        '--limit-packets',
        type=int,
        default=None,
        help='Send only the first N packets of the frame for diagnostics',
    )
    parser.add_argument(
        '--extra-read-after-packet',
        type=int,
        default=None,
        help='Perform one additional EP IN read after packet N',
    )
    parser.add_argument(
        '--recover-before-send',
        action='store_true',
        help='Best-effort clear halt on endpoints before starting a frame',
    )
    parser.add_argument(
        '--drain-in-before-send',
        action='store_true',
        help='Drain pending IN packets before sending frame data',
    )
    parser.add_argument(
        '--usb-reset-before-send',
        action='store_true',
        help='Hard reset the USB device before sending a frame',
    )
    parser.add_argument(
        '--usb-reset-on-fail',
        action='store_true',
        help='Hard reset and reconnect the USB device before retrying a failed frame',
    )
    parser.add_argument(
        '--save-jpeg',
        help='Save the generated JPEG payload to a file for comparison/debugging',
    )
    parser.add_argument(
        '--raw-jpeg-passthrough',
        action='store_true',
        help='If the input file is .jpg/.jpeg, send its raw bytes without Pillow re-encoding',
    )
    parser.add_argument('--packet-debug', action='store_true', help='Print JPEG packet plan before sending')
    args = parser.parse_args()

    if not args.image and not args.test and not args.monitor:
        parser.print_help()
        sys.exit(1)

    args.repeat = max(1, args.repeat)
    args.max_frames = max(0, args.max_frames)
    args.frame_delay = max(0.0, args.frame_delay)
    args.keepalive_interval = max(0.05, args.keepalive_interval)
    args.frame_retries = max(0, args.frame_retries)
    args.connect_retries = max(1, args.connect_retries)
    args.connect_retry_delay = max(0.0, args.connect_retry_delay)
    args.reconnect_delay = max(0.0, args.reconnect_delay)
    if args.jpeg_pad_to_size is not None and args.jpeg_pad_to_size <= 0:
        args.jpeg_pad_to_size = None
    if args.jpeg_restart_marker_rows < 0:
        args.jpeg_restart_marker_rows = 0

    if args.windows_capture_profile:
        args.trcc_compatible = True

    if args.trcc_compatible:
        args.final_packet_mode = FINAL_PACKET_MODE_PAD_4096
        args.buffer_index_mode = BUFFER_INDEX_MODE_ZERO
        args.ack_every_packet = False
        args.ack_on_seq0_only = False
        if args.inter_packet_delay <= 0:
            args.inter_packet_delay = WINDOWS_CAPTURE_INTER_PACKET_DELAY
        if args.ack_timeout_ms == USB_TIMEOUT:
            args.ack_timeout_ms = WINDOWS_CAPTURE_ACK_TIMEOUT_MS
        if args.frame_delay <= 0:
            args.frame_delay = 0.02
        if args.frame_retries == 0:
            args.frame_retries = 1
        args.reconnect_on_fail = True
        args.usb_reset_on_fail = True
        args.init_strict = False
        if args.loop:
            args.skip_unchanged = True

    # Monitor mode is long-running and should prefer the most stable transport profile
    # even when --trcc-compatible is not explicitly set.
    if args.monitor and not args.trcc_compatible:
        if args.final_packet_mode == FINAL_PACKET_MODE_AUTO:
            args.final_packet_mode = FINAL_PACKET_MODE_PAD_2048
        # For monitor mode we keep INIT enabled (once per connection),
        # because some devices accept only a few packets after reconnect without it.
        # Stabilize uncertain header fields against observed working captures.
        # Keep override-friendly behavior if user explicitly set them.
        args.header_byte10 = 0x02
        if args.header_size_override is None:
            args.header_size_override = TRCC_COMPAT_JPEG_SIZE
        if args.jpeg_pad_to_size is None:
            args.jpeg_pad_to_size = TRCC_COMPAT_TRANSFER_SIZE
        args.ack_every_packet = True
        # For LY/TRCC-compatible monitor transport, the only field-proven profile
        # has been reading ACK on the outer seq=0 packets only (1/33/65...).
        # Reading after every 4096B write tends to introduce spurious timeouts
        # without improving reliability.
        args.ack_on_seq0_only = True
        if args.inter_packet_delay <= 0:
            args.inter_packet_delay = 0.01
        if args.ack_timeout_ms == USB_TIMEOUT:
            args.ack_timeout_ms = 500
        if args.interval == 1.0:
            args.interval = 0.2
        if args.repeat == 1:
            args.repeat = 3
        if args.frame_delay == 0.0:
            args.frame_delay = 0.05
        if not args.recover_before_send:
            args.recover_before_send = True
        if not args.drain_in_before_send:
            args.drain_in_before_send = True
        if args.frame_retries == 0:
            args.frame_retries = 2
        args.reconnect_on_fail = True

    image_packet_template = []
    if args.trcc_compatible and args.image and not args.monitor:
        image_packet_template = _get_monitor_packet_template()
        if args.header_size_override is None:
            args.header_size_override = TRCC_COMPAT_JPEG_SIZE
        # For templated LY packets, pad only to the payload capacity encoded in
        # the captured frame layout, not to the outer USB transfer size.
        if args.jpeg_pad_to_size is None:
            args.jpeg_pad_to_size = TRCC_COMPAT_JPEG_SIZE
        if not args.recover_before_send:
            args.recover_before_send = True
        if not args.drain_in_before_send:
            args.drain_in_before_send = True
        args.skip_init = False

    global JPEG_QUALITY
    global JPEG_SUBSAMPLING
    global JPEG_PROGRESSIVE
    global JPEG_RESTART_MARKER_ROWS
    JPEG_QUALITY = args.quality
    JPEG_SUBSAMPLING = args.subsampling
    JPEG_PROGRESSIVE = args.progressive
    JPEG_RESTART_MARKER_ROWS = args.jpeg_restart_marker_rows

    lcd = TrofeoLCD()
    if not lcd.connect(retries=args.connect_retries, retry_delay=args.connect_retry_delay):
        sys.exit(1)
    def configure_lcd():
        lcd.init_enabled = not args.skip_init
        lcd.init_every_frame = args.init_every_frame
        lcd.init_strict = args.init_strict
        lcd.header_b9 = None if args.header_b9 is None else (args.header_b9 & 0xFF)
        lcd.header_byte10 = args.header_byte10 & 0xFF
        lcd.buffer_index_mode = args.buffer_index_mode
        lcd.buffer_index_override = args.buffer_index_override

    configure_lcd()
    def pre_send_ops():
        if args.usb_reset_before_send:
            lcd.reset_device()
            configure_lcd()
        if args.recover_before_send:
            # In live loop/monitor mode we still want endpoint recovery, but the
            # default 1s guard delay per frame destroys refresh cadence.
            recover_delay = 0.0 if (args.loop or args.monitor) else RECOVERY_DELAY
            lcd.recover_endpoints(delay=recover_delay)
        if args.drain_in_before_send:
            drain_timeout_ms = 5 if (args.loop or args.monitor) else 50
            drained = lcd.drain_in(timeout_ms=drain_timeout_ms)
            if args.packet_debug:
                print(f"  in-drain: {drained} packets")

    def reconnect_device():
        lcd.disconnect()
        if args.reconnect_delay > 0:
            time.sleep(args.reconnect_delay)
        ok = lcd.connect(retries=args.connect_retries, retry_delay=args.connect_retry_delay)
        if ok:
            configure_lcd()
        return ok

    def send_with_retries(send_fn, label):
        attempts = 1 + args.frame_retries
        for attempt in range(1, attempts + 1):
            pre_send_ops()
            if send_fn():
                return True
            if attempt >= attempts:
                return False
            print(f"BŁĄD wysyłania ({label}), ponawiam {attempt}/{attempts - 1}...")
            if args.usb_reset_on_fail:
                print("Resetuję USB przed ponowieniem...")
                if not lcd.reset_device():
                    print("BŁĄD resetu USB przed ponowieniem")
                    if not reconnect_device():
                        print("BŁĄD reconnect po nieudanym resecie")
                        return False
            elif args.reconnect_on_fail:
                if not reconnect_device():
                    print("BŁĄD reconnect po nieudanej wysyłce")
                    return False
            else:
                lcd.recover_endpoints()
                if args.drain_in_before_send:
                    lcd.drain_in()
        return False

    def build_loop_file_sender(filepath):
        cache = {
            "sig": None,
            "jpeg_data": None,
            "reloaded": False,
            "reload_ms": 0.0,
            "last_send_at": 0.0,
        }
        path_lower = filepath.lower()

        def _refresh_cache():
            started = time.perf_counter()
            stat = os.stat(filepath)
            sig = (stat.st_mtime_ns, stat.st_size)
            if cache["sig"] == sig and cache["jpeg_data"] is not None:
                cache["reloaded"] = False
                cache["reload_ms"] = 0.0
                return

            if args.raw_jpeg_passthrough and (path_lower.endswith(".jpg") or path_lower.endswith(".jpeg")):
                with open(filepath, "rb") as handle:
                    jpeg_data = handle.read()
            else:
                with Image.open(filepath) as img:
                    img.load()
                    _, jpeg_data = lcd.encode_image_to_jpeg(img)

            cache["jpeg_data"] = lcd.pad_jpeg_payload(jpeg_data, args.jpeg_pad_to_size)
            cache["sig"] = sig
            cache["reloaded"] = True
            cache["reload_ms"] = (time.perf_counter() - started) * 1000.0

        def _send():
            _refresh_cache()
            now = time.monotonic()
            if (
                args.skip_unchanged
                and not cache["reloaded"]
                and cache["last_send_at"] > 0.0
                and now - cache["last_send_at"] < args.keepalive_interval
            ):
                return True
            send_started = time.perf_counter()
            ok = lcd.send_jpeg(
                cache["jpeg_data"],
                final_packet_mode=args.final_packet_mode,
                header_size_mode=args.header_size_mode,
                header_size_override=args.header_size_override,
                frame_counter_override=args.frame_counter,
                packet_debug=args.packet_debug,
                ack_every_packet=args.ack_every_packet,
                inter_packet_delay=args.inter_packet_delay,
                seq_step=args.seq_step,
                constant_seq=args.constant_seq,
                drain_in_after_packet=args.drain_in_after_packet,
                send_commit=args.send_commit,
                commit_mode=args.commit_mode,
                limit_packets=args.limit_packets,
                extra_read_after_packet=args.extra_read_after_packet,
                ack_timeout_ms=args.ack_timeout_ms,
                ack_on_seq0_only=args.ack_on_seq0_only,
                packet_templates=image_packet_template if image_packet_template else None,
            )
            send_ms = (time.perf_counter() - send_started) * 1000.0
            if ok:
                cache["last_send_at"] = time.monotonic()
            if cache["reloaded"] or send_ms >= 120.0 or cache["reload_ms"] >= 120.0:
                reload_note = f" reload_ms={int(round(cache['reload_ms']))}" if cache["reloaded"] else ""
                print(
                    f"[loop-send] file={os.path.basename(filepath)} send_ms={int(round(send_ms))}{reload_note}",
                    flush=True,
                )
            return ok

        return _send

    try:
        if args.test:
            print("Wysyłam wzór testowy...")
            img = create_test_pattern()
            rendered_img, jpeg_data = lcd.encode_image_to_jpeg(img)
            if args.save_jpeg:
                with open(args.save_jpeg, 'wb') as f:
                    f.write(jpeg_data)
                print(f"Zapisano JPEG do: {args.save_jpeg}")
            if args.packet_debug:
                plans = lcd.build_packet_plans(len(jpeg_data), args.final_packet_mode)
                plans = lcd.apply_sequence_mode(plans, seq_step=args.seq_step, constant_seq=args.constant_seq)
                if args.limit_packets is not None:
                    plans = plans[:args.limit_packets]
                for index, plan in enumerate(plans, start=1):
                    print(f"  packet {index}: payload={plan.payload_len} total={plan.total_size} seq=0x{plan.seq_num:02x}")
            for run_idx in range(args.repeat):
                if args.repeat > 1:
                    print(f"FRAME {run_idx + 1}/{args.repeat}")
                if not send_with_retries(
                    lambda: lcd.send_image(
                        rendered_img,
                        final_packet_mode=args.final_packet_mode,
                        header_size_mode=args.header_size_mode,
                        header_size_override=args.header_size_override,
                        frame_counter_override=args.frame_counter,
                        packet_debug=args.packet_debug,
                        ack_every_packet=args.ack_every_packet,
                        inter_packet_delay=args.inter_packet_delay,
                        seq_step=args.seq_step,
                        constant_seq=args.constant_seq,
                        drain_in_after_packet=args.drain_in_after_packet,
                        send_commit=args.send_commit,
                        commit_mode=args.commit_mode,
                        limit_packets=args.limit_packets,
                        extra_read_after_packet=args.extra_read_after_packet,
                        ack_timeout_ms=args.ack_timeout_ms,
                        ack_on_seq0_only=args.ack_on_seq0_only,
                        jpeg_pad_to_size=args.jpeg_pad_to_size,
                    ),
                    label=f"test frame {run_idx + 1}",
                ):
                    print("BŁĄD wysyłania")
                    sys.exit(2)
                if args.frame_delay > 0 and run_idx + 1 < args.repeat:
                    time.sleep(args.frame_delay)
            print("OK")

        elif args.monitor:
            print("Tryb monitorowania systemu (Ctrl+C aby zakończyć)...")
            frames_sent = 0
            packet_template = _get_monitor_packet_template()
            while args.max_frames == 0 or frames_sent < args.max_frames:
                global _MONITOR_FITTED_ALPHA
                target_header_size = TRCC_COMPAT_JPEG_SIZE
                best_img = None
                best_jpeg = None
                best_alpha = _MONITOR_FITTED_ALPHA

                # Fast path: try the last known-good alpha first to minimize
                # startup latency and reduce the time the panel shows stale data.
                probe_img = render_monitor_theme_image(background_alpha=_MONITOR_FITTED_ALPHA)
                _, probe_jpeg = lcd.encode_image_to_jpeg(probe_img)
                if len(probe_jpeg) <= target_header_size:
                    best_img = probe_img
                    best_jpeg = probe_jpeg
                else:
                    low_alpha = 0.30
                    high_alpha = min(0.50, _MONITOR_FITTED_ALPHA)
                    # Fit the rendered frame under the known-good TRCC JPEG size,
                    # then pad to the exact size so the wire format matches capture.
                    for _ in range(8):
                        alpha = (low_alpha + high_alpha) / 2.0
                        probe_img = render_monitor_theme_image(background_alpha=alpha)
                        _, probe_jpeg = lcd.encode_image_to_jpeg(probe_img)
                        if len(probe_jpeg) <= target_header_size:
                            best_img = probe_img
                            best_jpeg = probe_jpeg
                            best_alpha = alpha
                            low_alpha = alpha
                        else:
                            high_alpha = alpha

                if best_img is None or best_jpeg is None:
                    best_img = render_monitor_theme_image(background_alpha=0.35)
                    _, best_jpeg = lcd.encode_image_to_jpeg(best_img)
                    best_alpha = 0.35

                _MONITOR_FITTED_ALPHA = best_alpha

                actual_monitor_jpeg_size = target_header_size
                exact_monitor_jpeg = lcd.pad_jpeg_payload(best_jpeg, target_header_size)
                padded_monitor_jpeg = lcd.pad_jpeg_payload(exact_monitor_jpeg, args.jpeg_pad_to_size)
                if args.packet_debug:
                    print(
                        f"  monitor jpeg size={len(best_jpeg)}"
                        f" fitted-alpha={best_alpha:.4f}"
                        f" header-size={actual_monitor_jpeg_size}"
                        f" padded={len(padded_monitor_jpeg)}"
                        f" template-packets={len(packet_template)}"
                    )
                for run_idx in range(args.repeat):
                    if args.repeat > 1 and args.packet_debug:
                        print(f"  monitor latch {run_idx + 1}/{args.repeat}")
                    if not send_with_retries(
                        lambda: lcd.send_jpeg(
                            exact_monitor_jpeg if packet_template else padded_monitor_jpeg,
                            final_packet_mode=args.final_packet_mode,
                            header_size_mode=args.header_size_mode,
                            header_size_override=actual_monitor_jpeg_size,
                            frame_counter_override=args.frame_counter,
                            packet_debug=args.packet_debug,
                            ack_every_packet=args.ack_every_packet,
                            inter_packet_delay=args.inter_packet_delay,
                            seq_step=args.seq_step,
                            constant_seq=args.constant_seq,
                            drain_in_after_packet=args.drain_in_after_packet,
                            send_commit=args.send_commit,
                            commit_mode=args.commit_mode,
                            limit_packets=args.limit_packets,
                            extra_read_after_packet=args.extra_read_after_packet,
                            ack_timeout_ms=args.ack_timeout_ms,
                            ack_on_seq0_only=args.ack_on_seq0_only,
                            packet_templates=packet_template if packet_template else None,
                        ),
                        label=f"monitor frame {run_idx + 1}",
                    ):
                        print("BŁĄD wysyłania, zatrzymuję monitor.")
                        sys.exit(2)
                    if args.frame_delay > 0 and run_idx + 1 < args.repeat:
                        time.sleep(args.frame_delay)
                frames_sent += 1
                time.sleep(args.interval)
            print(f"OK (monitor frames sent: {frames_sent})")

        elif args.image:
            if args.loop:
                print(f"Wysyłam {args.image} w pętli co {args.interval}s (Ctrl+C aby zakończyć)...")
                frames_sent = 0
                loop_sender = build_loop_file_sender(args.image)
                while args.max_frames == 0 or frames_sent < args.max_frames:
                    if not send_with_retries(
                        loop_sender,
                        label="loop frame",
                    ):
                        print("BŁĄD wysyłania, zatrzymuję pętlę.")
                        sys.exit(2)
                    frames_sent += 1
                    time.sleep(args.interval)
                print(f"OK (loop frames sent: {frames_sent})")
            else:
                print(f"Wysyłam {args.image}...")
                for run_idx in range(args.repeat):
                    if args.repeat > 1:
                        print(f"FRAME {run_idx + 1}/{args.repeat}")
                    if not send_with_retries(
                        lambda: lcd.send_file(
                            args.image,
                            final_packet_mode=args.final_packet_mode,
                            header_size_mode=args.header_size_mode,
                            header_size_override=args.header_size_override,
                            frame_counter_override=args.frame_counter,
                            packet_debug=args.packet_debug,
                            ack_every_packet=args.ack_every_packet,
                            inter_packet_delay=args.inter_packet_delay,
                            seq_step=args.seq_step,
                            constant_seq=args.constant_seq,
                            drain_in_after_packet=args.drain_in_after_packet,
                            send_commit=args.send_commit,
                            commit_mode=args.commit_mode,
                            limit_packets=args.limit_packets,
                            extra_read_after_packet=args.extra_read_after_packet,
                            raw_jpeg_passthrough=args.raw_jpeg_passthrough,
                            ack_timeout_ms=args.ack_timeout_ms,
                            ack_on_seq0_only=args.ack_on_seq0_only,
                            jpeg_pad_to_size=args.jpeg_pad_to_size,
                            packet_templates=image_packet_template if image_packet_template else None,
                        ),
                        label=f"file frame {run_idx + 1}",
                    ):
                        print("BŁĄD wysyłania")
                        sys.exit(2)
                    if args.frame_delay > 0 and run_idx + 1 < args.repeat:
                        time.sleep(args.frame_delay)
                print("OK")

    except KeyboardInterrupt:
        print("\nZatrzymano.")
    finally:
        lcd.disconnect()


if __name__ == '__main__':
    main()
