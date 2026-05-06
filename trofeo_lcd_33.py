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

try:
    import usb.core
    import usb.util
except ImportError:
    print("BŁĄD: Brak modułu pyusb. Zainstaluj: pip install pyusb")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("BŁĄD: Brak modułu Pillow. Zainstaluj: pip install Pillow")
    sys.exit(1)


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

USB_TIMEOUT = 5000        # ms


class TrofeoLCD:
    """Driver for Thermalright Trofeo LCD display."""

    def __init__(self):
        self.dev = None
        self.frame_counter = 0

    def connect(self):
        """Find and connect to the Trofeo LCD device."""
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            print(f"BŁĄD: Nie znaleziono urządzenia Trofeo LCD ({VID:04x}:{PID:04x})")
            print("Sprawdź:")
            print("  1. Czy LCD jest podłączony przez USB")
            print("  2. Czy masz uprawnienia (uruchom z sudo lub dodaj regułę udev)")
            print("  3. lsusb | grep 0416")
            return False

        # Detach kernel driver if attached
        try:
            if self.dev.is_kernel_driver_active(INTERFACE):
                self.dev.detach_kernel_driver(INTERFACE)
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
        except usb.core.USBError as e:
            print(f"BŁĄD: Nie można przejąć interfejsu: {e}")
            return False

        # Send INIT command — required before any JPEG data
        if not self._init_device():
            print("BŁĄD: Init urządzenia nie powiodło się")
            return False

        print(f"Połączono z Trofeo LCD ({LCD_WIDTH}x{LCD_HEIGHT})")
        return True

    def _init_device(self):
        """
        Send the INIT command (cmd=0x02) and read device info response.

        This is the critical step that was missing — TRCC sends this
        once after USB enumeration, before any JPEG data.

        INIT OUT (2048 bytes):
          [0] = 0x02 (init/query command)
          [1] = 0xFF (marker)
          [2..7] = 0x00
          [8] = 0x01
          [9..2047] = 0x00

        INIT RESPONSE (512 bytes):
          [0] = 0x03 (response)
          [1] = 0xFF (marker)
          [8] = 0x01 (status OK)
          [16..19] = device ID / firmware version
          [20] = 0x02
          [22] = 0x04
          [24..27] = display width (LE32) = 1920
          [28..31] = display height (LE32) = 599 (internal buffer)
          [32] = 0x32 (50 = JPEG quality?)
          [44] = 0x89 (137)
        """
        # Build INIT packet
        init_packet = bytearray(2048)
        init_packet[0] = 0x02  # cmd: INIT
        init_packet[1] = 0xFF  # marker
        init_packet[8] = 0x01

        try:
            self.dev.write(EP_OUT, bytes(init_packet), USB_TIMEOUT)
        except usb.core.USBError as e:
            print(f"BŁĄD: Nie można wysłać INIT: {e}")
            return False

        # Read INIT response
        try:
            response = self.dev.read(EP_IN, 512, USB_TIMEOUT)
            if len(response) >= 16 and response[0] == 0x03 and response[8] == 0x01:
                # Parse device info
                if len(response) >= 32:
                    width = struct.unpack_from('<I', response, 24)[0]
                    height = struct.unpack_from('<I', response, 28)[0]
                    print(f"  Device info: bufor {width}x{height}")
                return True
            else:
                print(f"OSTRZEŻENIE: Nieoczekiwana odpowiedź INIT: cmd=0x{response[0]:02x} status=0x{response[8]:02x}")
                return True  # Try anyway
        except usb.core.USBTimeoutError:
            print("OSTRZEŻENIE: Timeout odczytu INIT response (kontynuuję)")
            return True  # May still work
        except usb.core.USBError as e:
            print(f"BŁĄD: Odczyt INIT response: {e}")
            return False

    def disconnect(self):
        """Release the USB device."""
        if self.dev:
            try:
                usb.util.release_interface(self.dev, INTERFACE)
            except Exception:
                pass
            try:
                usb.util.dispose_resources(self.dev)
            except Exception:
                pass
            self.dev = None

    def _build_header(self, jpeg_size, seq_num):
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
        frame_lo = self.frame_counter & 0xFF
        header = bytearray(16)
        header[0] = 0x01
        header[1] = 0xFF
        # Bytes 2-5: observed to contain values related to data
        struct.pack_into('<I', header, 2, jpeg_size & 0xFFFFFFFF)
        header[6] = 0x00
        header[7] = 0xF0
        header[8] = 0x01
        header[9] = 0x01
        header[10] = frame_lo
        header[11] = seq_num
        # 12-15 stay zero
        return bytes(header)

    def send_jpeg(self, jpeg_data):
        """
        Send a JPEG image to the LCD.

        Protocol:
        1. Split JPEG into chunks with 16-byte headers
        2. Send each chunk as 4096-byte bulk OUT transfer
        3. Last chunk is 2048 bytes
        4. Read 512-byte ACK from EP1 IN
        """
        if not self.dev:
            raise RuntimeError("Nie połączono z urządzeniem")

        jpeg_size = len(jpeg_data)
        offset = 0
        seq = 0

        while offset < jpeg_size:
            remaining = jpeg_size - offset

            # Determine chunk data size
            if remaining <= DATA_PER_LAST:
                # Last chunk
                chunk_data = jpeg_data[offset:offset + remaining]
                total_size = LAST_CHUNK_SIZE
            else:
                chunk_data = jpeg_data[offset:offset + DATA_PER_CHUNK]
                total_size = CHUNK_SIZE

            # Build packet: header + data + padding
            header = self._build_header(jpeg_size, seq)
            packet = bytearray(total_size)
            packet[:HEADER_SIZE] = header
            packet[HEADER_SIZE:HEADER_SIZE + len(chunk_data)] = chunk_data

            # Send via bulk OUT
            try:
                self.dev.write(EP_OUT, bytes(packet), USB_TIMEOUT)
            except usb.core.USBError as e:
                print(f"BŁĄD zapisu USB: {e}")
                return False

            offset += len(chunk_data)
            seq = (seq + 8) & 0xFF

        # Read ACK from device
        try:
            ack = self.dev.read(EP_IN, 512, USB_TIMEOUT)
        except usb.core.USBTimeoutError:
            pass  # ACK timeout is non-fatal
        except usb.core.USBError:
            pass

        self.frame_counter += 1
        return True

    def send_image(self, image):
        """
        Send a PIL Image to the LCD (auto-resize and convert to JPEG).
        """
        # Resize to LCD resolution
        if image.size != (LCD_WIDTH, LCD_HEIGHT):
            image = image.resize((LCD_WIDTH, LCD_HEIGHT), Image.LANCZOS)

        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Encode as JPEG
        buf = io.BytesIO()
        image.save(buf, format='JPEG', quality=JPEG_QUALITY, subsampling='4:2:0')
        jpeg_data = buf.getvalue()

        return self.send_jpeg(jpeg_data)

    def send_file(self, filepath):
        """Send an image file to the LCD."""
        try:
            img = Image.open(filepath)
            return self.send_image(img)
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


def create_monitor_image():
    """Generate a simple system monitoring image."""
    img = Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT), (20, 20, 30))
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
    mem_info = "N/A"
    hostname = "unknown"

    try:
        hostname = os.uname().nodename
    except Exception:
        pass

    # CPU temperature
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            cpu_temp = f"{int(f.read().strip()) / 1000:.0f}°C"
    except Exception:
        pass

    # CPU usage (from /proc/stat)
    try:
        with open('/proc/stat') as f:
            line = f.readline()
            parts = line.split()
            idle = int(parts[4])
            total = sum(int(x) for x in parts[1:])
            # Simple snapshot-based percentage
            cpu_usage = f"{100 - (idle * 100 / total):.0f}%"
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
    y = 20
    draw.text((40, y), f"⬡ {hostname}", fill=(0, 200, 255), font=font_big)
    draw.text((LCD_WIDTH - 300, y), time.strftime("%H:%M:%S"), fill=(200, 200, 200), font=font_big)

    y = 90
    # CPU section
    draw.text((40, y), "CPU", fill=(255, 100, 100), font=font_med)
    draw.text((40, y + 40), f"Temp: {cpu_temp}", fill=(220, 220, 220), font=font_sm)
    draw.text((40, y + 70), f"Usage: {cpu_usage}", fill=(220, 220, 220), font=font_sm)

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

    return img


def main():
    parser = argparse.ArgumentParser(
        description='Thermalright Trofeo LCD Driver for Linux'
    )
    parser.add_argument('image', nargs='?', help='Image file to send')
    parser.add_argument('--test', action='store_true', help='Send test pattern')
    parser.add_argument('--monitor', action='store_true', help='System monitoring mode')
    parser.add_argument('--loop', action='store_true', help='Loop continuously')
    parser.add_argument('--interval', type=float, default=1.0, help='Update interval in seconds (default: 1.0)')
    parser.add_argument('--quality', type=int, default=85, help='JPEG quality 1-100 (default: 85)')
    args = parser.parse_args()

    if not args.image and not args.test and not args.monitor:
        parser.print_help()
        sys.exit(1)

    global JPEG_QUALITY
    JPEG_QUALITY = args.quality

    lcd = TrofeoLCD()
    if not lcd.connect():
        sys.exit(1)

    try:
        if args.test:
            print("Wysyłam wzór testowy...")
            img = create_test_pattern()
            if lcd.send_image(img):
                print("OK")
            else:
                print("BŁĄD wysyłania")

        elif args.monitor:
            print("Tryb monitorowania systemu (Ctrl+C aby zakończyć)...")
            while True:
                img = create_monitor_image()
                lcd.send_image(img)
                time.sleep(args.interval)

        elif args.image:
            if args.loop:
                print(f"Wysyłam {args.image} w pętli co {args.interval}s (Ctrl+C aby zakończyć)...")
                while True:
                    lcd.send_file(args.image)
                    time.sleep(args.interval)
            else:
                print(f"Wysyłam {args.image}...")
                if lcd.send_file(args.image):
                    print("OK")
                else:
                    print("BŁĄD wysyłania")

    except KeyboardInterrupt:
        print("\nZatrzymano.")
    finally:
        lcd.disconnect()


if __name__ == '__main__':
    main()
