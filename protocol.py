#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Optional

from PIL import Image, ImageDraw

from transport import TrofeoTransport, TransportError


class ProtocolError(Exception):
    pass


@dataclass
class ScreenSpec:
    width: int = 1920
    height: int = 480
    bytes_per_pixel: int = 3  # RGB888 placeholder


@dataclass
class PacketTrace:
    direction: str
    payload: bytes


class TrofeoProtocol:
    """
    Warstwa protokołu.

    Na ten moment:
    - mamy działający transport USB,
    - nie mamy jeszcze pełnej, potwierdzonej specyfikacji komend dla tego modelu,
    - więc ta klasa daje bezpieczny szkielet pod dalszy reverse engineering.

    Tutaj później wstawisz:
    - handshake/init
    - upload ramek
    - ewentualne sterowanie jasnością
    - inne komendy producenta
    """

    def __init__(self, transport: TrofeoTransport, screen: Optional[ScreenSpec] = None) -> None:
        self.transport = transport
        self.screen = screen or ScreenSpec()
        self.trace: List[PacketTrace] = []

    def open(self):
        return self.transport.open()

    def close(self) -> None:
        self.transport.close()

    def clear_trace(self) -> None:
        self.trace.clear()

    def _trace_out(self, payload: bytes) -> None:
        self.trace.append(PacketTrace(direction="OUT", payload=payload))

    def _trace_in(self, payload: bytes) -> None:
        self.trace.append(PacketTrace(direction="IN", payload=payload))

    def send_raw(self, payload: bytes, read_size: int = 512, read_timeout_ms: int = 200) -> bytes:
        self._trace_out(payload)
        response = self.transport.transact(
            payload,
            read_size=read_size,
            read_timeout_ms=read_timeout_ms,
            settle_ms=20,
        )
        if response:
            self._trace_in(response)
        return response

    def try_basic_probes(self) -> list[tuple[bytes, bytes]]:
        """
        Zachowujemy to jako narzędzie diagnostyczne.
        Nie jest to implementacja prawdziwego protokołu.
        """
        probes = [
            b"\x00",
            b"\x55\xaa",
        ]

        results: list[tuple[bytes, bytes]] = []

        for payload in probes:
            try:
                response = self.send_raw(payload)
            except TransportError:
                response = b""
            results.append((payload, response))

        return results

    def chunk_bytes(self, data: bytes, chunk_size: int = 512) -> Iterable[bytes]:
        if chunk_size <= 0:
            raise ValueError("chunk_size musi być > 0")

        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def image_to_rgb_bytes(self, image: Image.Image) -> bytes:
        """
        Placeholder renderer:
        - skaluje do rozdzielczości ekranu,
        - konwertuje do RGB,
        - zwraca surowe RGB888.
        """
        img = image.convert("RGB")
        img = img.resize((self.screen.width, self.screen.height))
        return img.tobytes()

    def load_image_file_as_frame(self, path: str) -> bytes:
        with Image.open(path) as img:
            return self.image_to_rgb_bytes(img)

    def sample_cpu_load_percent(self, interval_seconds: float = 0.2) -> float:
        if interval_seconds < 0:
            raise ValueError("interval_seconds musi być >= 0")

        def read_cpu_times() -> tuple[int, int]:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                first = f.readline().strip()

            parts = first.split()
            if len(parts) < 5 or parts[0] != "cpu":
                raise ProtocolError("Nie udało się odczytać /proc/stat")

            values = [int(value) for value in parts[1:]]
            idle = values[3]
            total = sum(values)
            return idle, total

        idle1, total1 = read_cpu_times()
        if interval_seconds > 0:
            import time
            time.sleep(interval_seconds)
        idle2, total2 = read_cpu_times()

        delta_idle = idle2 - idle1
        delta_total = total2 - total1
        if delta_total <= 0:
            return 0.0

        usage = 100.0 * (1.0 - (delta_idle / delta_total))
        return max(0.0, min(100.0, usage))

    def render_cpu_load_image(self, cpu_percent: float) -> Image.Image:
        width = self.screen.width
        height = self.screen.height
        img = Image.new("RGB", (width, height), (10, 16, 24))
        draw = ImageDraw.Draw(img)

        cpu_percent = max(0.0, min(100.0, cpu_percent))
        margin = 48
        bar_top = 170
        bar_height = 140
        bar_width = width - (margin * 2)
        fill_width = int(bar_width * (cpu_percent / 100.0))

        # Tło i prosty pasek obciążenia, bez zależności od fontów systemowych.
        draw.rectangle((0, 0, width, height), fill=(12, 18, 28))
        draw.rectangle((margin, 72, width - margin, 132), fill=(24, 34, 46))
        draw.rectangle((margin, bar_top, width - margin, bar_top + bar_height), fill=(24, 34, 46))

        if fill_width > 0:
            bar_color = (56, 189, 248) if cpu_percent < 80.0 else (248, 113, 113)
            draw.rectangle(
                (margin, bar_top, margin + fill_width, bar_top + bar_height),
                fill=bar_color,
            )

        stripe_width = 24
        stripe_gap = 12
        for offset in range(margin, margin + fill_width, stripe_width + stripe_gap):
            draw.rectangle(
                (offset, bar_top, min(offset + stripe_width, margin + fill_width), bar_top + bar_height),
                fill=(255, 255, 255),
            )

        draw.text((margin, 84), "CPU LOAD", fill=(220, 228, 236))
        draw.text((margin, 340), f"{cpu_percent:05.1f}%", fill=(220, 228, 236))
        draw.text((margin, 396), f"{width}x{height} RGB placeholder frame", fill=(140, 154, 171))

        return img

    def build_cpu_load_frame(self, cpu_percent: float) -> bytes:
        image = self.render_cpu_load_image(cpu_percent)
        return self.image_to_rgb_bytes(image)

    def build_frame_upload_packets(self, frame_bytes: bytes, chunk_payload_size: int = 512) -> list[bytes]:
        """
        Placeholder.

        To NIE jest jeszcze prawdziwy format pakietów tego urządzenia.
        Na razie zwraca tylko surowe chunki, żeby mieć gotowe API.
        Gdy rozpoznasz protokół, to właśnie tutaj wstawisz:
        - nagłówki
        - numerację chunków
        - długości
        - checksumy/CRC
        - komendę start/stop uploadu
        """
        return list(self.chunk_bytes(frame_bytes, chunk_payload_size))

    def upload_frame_placeholder(
        self,
        frame_bytes: bytes,
        limit_chunks: Optional[int] = None,
        read_timeout_ms: int = 50,
    ) -> None:
        """
        NIE używaj tego jeszcze do pełnej wysyłki obrazu produkcyjnie.
        To tylko szkielet do testów po rozpoznaniu protokołu.
        """
        packets = self.build_frame_upload_packets(frame_bytes)

        if limit_chunks is not None:
            packets = packets[:limit_chunks]

        for idx, packet in enumerate(packets, start=1):
            self._trace_out(packet)
            response = self.transport.transact(
                packet,
                read_size=512,
                read_timeout_ms=read_timeout_ms,
                settle_ms=1,
            )
            if response:
                self._trace_in(response)
            print(f"[UPLOAD] chunk {idx}/{len(packets)} len={len(packet)}")

    def dump_trace(self) -> str:
        lines = []
        for i, item in enumerate(self.trace, start=1):
            hex_data = item.payload.hex(" ")
            lines.append(f"{i:04d} {item.direction}: {hex_data}")
        return "\n".join(lines)

    def save_trace(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.dump_trace())
            f.write("\n")
