#!/usr/bin/env python3
"""
Replay Trofeo USB OUT payloads directly from a USBPcap pcapng capture.

Usage:
  python3 replay_from_pcap.py --pcap dzis.pcapng --frame 0 --send-init
"""

from __future__ import annotations

import argparse
import struct
import time
from pathlib import Path

import usb.core
import usb.util


VID = 0x0416
PID = 0x5408
EP_OUT = 0x09
EP_IN = 0x81
INTERFACE = 0
USB_TIMEOUT = 5000


def _is_resource_busy(err: Exception) -> bool:
    text = str(err).lower()
    return "errno 16" in text or "resource busy" in text


def iter_epb_packets(pcapng_bytes: bytes):
    off = 0
    endian = "<"
    n = len(pcapng_bytes)
    while off + 12 <= n:
        btype = struct.unpack_from(endian + "I", pcapng_bytes, off)[0]
        blen = struct.unpack_from(endian + "I", pcapng_bytes, off + 4)[0]
        if blen < 12 or off + blen > n:
            break
        body = pcapng_bytes[off + 8 : off + blen - 4]
        if btype == 0x0A0D0D0A and len(body) >= 4:
            bom = body[:4]
            endian = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
        elif btype == 0x00000006 and len(body) >= 20:
            _, _, _, cap_len, _ = struct.unpack_from(endian + "IIIII", body, 0)
            pkt = body[20 : 20 + cap_len]
            yield pkt
        off += blen


def iter_pcap_packets(pcap_bytes: bytes):
    if len(pcap_bytes) < 24:
        return

    magic = pcap_bytes[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
        ts_resolution = "us"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
        ts_resolution = "us"
    elif magic == b"\x4d\x3c\xb2\xa1":
        endian = "<"
        ts_resolution = "ns"
    elif magic == b"\xa1\xb2\x3c\x4d":
        endian = ">"
        ts_resolution = "ns"
    else:
        return

    off = 24
    n = len(pcap_bytes)
    while off + 16 <= n:
        ts_sec, ts_frac, cap_len, _ = struct.unpack_from(endian + "IIII", pcap_bytes, off)
        off += 16
        if cap_len < 0 or off + cap_len > n:
            break
        pkt = pcap_bytes[off : off + cap_len]
        off += cap_len
        yield ts_sec, ts_frac, ts_resolution, pkt


def parse_usbpcap_bulk_payloads(pcap_path: Path):
    sig = []
    data = pcap_path.read_bytes()
    if data.startswith(b"\x0a\x0d\x0d\x0a"):
        packets = ((None, None, None, pkt) for pkt in iter_epb_packets(data))
    else:
        packets = iter_pcap_packets(data)
    for _, _, _, pkt in packets:
        if len(pkt) < 27:
            continue
        hdr_len = struct.unpack_from("<H", pkt, 0)[0]
        if hdr_len < 27 or hdr_len > len(pkt):
            continue
        endpoint = pkt[21]
        transfer = pkt[22]
        data_len = struct.unpack_from("<I", pkt, 23)[0]
        if transfer != 3 or data_len == 0:
            continue
        payload = pkt[hdr_len : hdr_len + data_len] if hdr_len + data_len <= len(pkt) else pkt[hdr_len:]
        if not payload:
            continue
        cmd = payload[0]
        if endpoint in (EP_OUT, EP_IN) and cmd in (0x01, 0x02, 0x03):
            sig.append((endpoint, data_len, payload))
    return sig


def extract_init_and_frames(sig):
    init_out = next((p for ep, dlen, p in sig if ep == EP_OUT and dlen == 2048 and p[:2] == b"\x02\xff"), None)
    init_resp_idx = next((i for i, (ep, dlen, p) in enumerate(sig) if ep == EP_IN and dlen == 512 and p[:2] == b"\x03\xff"), -1)

    frames = []
    cur = []
    if init_resp_idx >= 0:
        iterable = sig[init_resp_idx + 1 :]
    else:
        iterable = sig

    for ep, dlen, payload in iterable:
        if ep == EP_IN and dlen == 512 and payload[:2] == b"\x03\xff":
            if cur:
                frames.append(cur)
                cur = []
            continue
        if ep == EP_OUT and payload[:2] == b"\x01\xff":
            cur.append(payload)
    if cur:
        frames.append(cur)

    return init_out, frames


def connect_device(retries=5, retry_delay=0.5):
    last_error = None

    for attempt in range(1, retries + 1):
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            last_error = RuntimeError(f"Nie znaleziono urządzenia {VID:04x}:{PID:04x}")
            time.sleep(retry_delay)
            continue

        try:
            if dev.is_kernel_driver_active(INTERFACE):
                dev.detach_kernel_driver(INTERFACE)
        except Exception:
            pass

        try:
            dev.set_configuration()
        except Exception:
            pass

        try:
            usb.util.claim_interface(dev, INTERFACE)
            return dev
        except usb.core.USBError as e:
            last_error = e
            if _is_resource_busy(e):
                try:
                    usb.util.release_interface(dev, INTERFACE)
                except Exception:
                    pass
                try:
                    dev.reset()
                except Exception:
                    pass
            try:
                usb.util.dispose_resources(dev)
            except Exception:
                pass
            if attempt < retries:
                time.sleep(max(retry_delay, 1.0 if _is_resource_busy(e) else retry_delay))
                continue

    if isinstance(last_error, usb.core.USBError) and _is_resource_busy(last_error):
        raise RuntimeError(
            "Interfejs USB zajęty (Errno 16 Resource busy). "
            "Zamknij inne procesy używające LCD i spróbuj ponownie.\n"
            "Pomocniczo: pkill -f 'replay_from_pcap.py|trofeo_lcd.py'"
        ) from last_error

    if last_error is not None:
        raise RuntimeError(f"Nie udało się połączyć z urządzeniem: {last_error}") from last_error

    raise RuntimeError("Nie udało się połączyć z urządzeniem")


def recover_endpoints(dev):
    for endpoint in (EP_OUT, EP_IN):
        try:
            usb.util.clear_halt(dev, endpoint)
        except Exception:
            pass


def drain_in(dev, timeout_ms=50, max_reads=32):
    count = 0
    for _ in range(max_reads):
        try:
            _ = bytes(dev.read(EP_IN, 512, timeout_ms))
            count += 1
        except usb.core.USBTimeoutError:
            break
        except Exception:
            break
    return count


def main():
    ap = argparse.ArgumentParser(description="Replay frame packets from USBPcap capture")
    ap.add_argument("--pcap", required=True, help="Path to .pcapng")
    ap.add_argument("--frame", type=int, default=0, help="Frame index to replay (default: 0)")
    ap.add_argument("--send-init", action="store_true", help="Send captured INIT packet before frame")
    ap.add_argument("--no-ack-read", action="store_true", help="Do not read IN ACK after replay")
    ap.add_argument("--ack-timeout-ms", type=int, default=5000)
    ap.add_argument("--ack-every-packet", action="store_true", help="Read EP IN after each OUT packet")
    ap.add_argument("--ack-on-seq0-only", action="store_true", help="When --ack-every-packet is set, read only for seq=0x00")
    ap.add_argument("--inter-packet-delay", type=float, default=0.0)
    ap.add_argument("--repeat", type=int, default=1, help="Send selected frame N times (default: 1)")
    ap.add_argument("--loop", action="store_true", help="Send selected frame in an infinite loop (Ctrl+C to stop)")
    ap.add_argument("--frame-delay", type=float, default=0.0, help="Delay between frames in seconds")
    ap.add_argument("--recover-before-send", action="store_true", help="Clear halt on EP OUT/IN before replay")
    ap.add_argument("--drain-in-before-send", action="store_true", help="Drain pending IN data before replay")
    ap.add_argument("--connect-retries", type=int, default=5, help="USB connect retries when interface is busy")
    ap.add_argument("--connect-retry-delay", type=float, default=0.5, help="Delay between connect retries (s)")
    args = ap.parse_args()

    pcap_path = Path(args.pcap)
    sig = parse_usbpcap_bulk_payloads(pcap_path)
    init_out, frames = extract_init_and_frames(sig)
    if not frames:
        raise RuntimeError("Nie znaleziono żadnych ramek cmd=0x01 w capture")
    if args.frame < 0 or args.frame >= len(frames):
        raise RuntimeError(f"Nieprawidłowy frame index {args.frame}, dostępne: 0..{len(frames)-1}")

    frame = frames[args.frame]
    print(f"Capture parsed: init={'yes' if init_out else 'no'}, frames={len(frames)}, selected={args.frame}, packets={len(frame)}")

    dev = connect_device(retries=max(1, args.connect_retries), retry_delay=max(0.0, args.connect_retry_delay))
    print("Połączono z Trofeo LCD")
    try:
        if args.recover_before_send:
            recover_endpoints(dev)
        if args.drain_in_before_send:
            drained = drain_in(dev, timeout_ms=50)
            print(f"IN drain before send: {drained} packets")

        if args.send_init and init_out is not None:
            print(f"INIT OUT: len={len(init_out)} hdr={init_out[:16].hex(' ')}")
            dev.write(EP_OUT, init_out, USB_TIMEOUT)
            try:
                init_ack = bytes(dev.read(EP_IN, 512, args.ack_timeout_ms))
                print(f"INIT ACK: {init_ack[:16].hex(' ')}...")
            except usb.core.USBTimeoutError:
                print("INIT ACK: <timeout>")
        send_forever = args.loop
        if send_forever:
            print("Tryb loop: Ctrl+C aby zakończyć")

        sent_frames = 0
        while send_forever or sent_frames < args.repeat:
            frame_no = sent_frames + 1
            print(f"FRAME {frame_no}:")
            for idx, payload in enumerate(frame, start=1):
                print(f"  packet {idx}/{len(frame)} len={len(payload)} hdr={payload[:16].hex(' ')}")
                dev.write(EP_OUT, payload, USB_TIMEOUT)
                if args.ack_every_packet:
                    seq = payload[11] if len(payload) > 11 else 0
                    should_read = (not args.ack_on_seq0_only) or (seq == 0x00)
                    if should_read:
                        try:
                            ack = bytes(dev.read(EP_IN, 512, args.ack_timeout_ms))
                            print(f"    ack {idx}: {ack[:16].hex(' ')}...")
                        except usb.core.USBTimeoutError:
                            print(f"    ack {idx}: <timeout>")
                if args.inter_packet_delay > 0:
                    time.sleep(args.inter_packet_delay)

            if not args.no_ack_read:
                try:
                    ack = bytes(dev.read(EP_IN, 512, args.ack_timeout_ms))
                    print(f"  FRAME ACK: {ack[:16].hex(' ')}...")
                except usb.core.USBTimeoutError:
                    print("  FRAME ACK: <timeout>")

            sent_frames += 1
            if args.frame_delay > 0:
                time.sleep(args.frame_delay)

        print(f"OK (frames sent: {sent_frames})")
    except KeyboardInterrupt:
        print("\nZatrzymano.")
    finally:
        try:
            usb.util.release_interface(dev, INTERFACE)
        except Exception:
            pass
        try:
            usb.util.dispose_resources(dev)
        except Exception:
            pass


if __name__ == "__main__":
    main()
