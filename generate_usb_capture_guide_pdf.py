#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import textwrap


TITLE = "Open-Trofeo-LCD: instrukcja przechwycenia USB trace pod Windows"

SECTIONS = [
    (
        "Cel",
        [
            "Celem jest zlapac trace USB podczas uzycia oficjalnego programu Thermalright/TRCC, aby odtworzyc prawdziwy protokol urzadzenia.",
            "Bez tego LCD najpewniej ignoruje nasze dane, bo samo bulk write nie wystarcza do wyswietlenia obrazu.",
        ],
    ),
    (
        "Co zainstalowac",
        [
            "1. Wireshark",
            "2. USBPcap",
            "3. Po instalacji zrestartowac Windows, jesli instalator tego wymaga.",
        ],
    ),
    (
        "Wazne przed startem",
        [
            "Najlepiej uzyc portu USB 2.0 albo huba USB 2.0.",
            "USBPcap ma znane ograniczenia przy czesci root hubow USB 3.0.",
            "Jesli masz wybor, podlacz LCD przez USB 2.0. To zwieksza szanse na poprawny trace.",
        ],
    ),
    (
        "Procedura capture krok po kroku",
        [
            "1. Odlacz ekran Trofeo od USB.",
            "2. Uruchom USBPcapCMD.exe jako Administrator.",
            "3. Na liscie root hubow znajdz ten, pod ktory bedzie podpiete urzadzenie.",
            "4. Zacznij capture na tym hubie.",
            "5. Dopiero teraz podlacz Trofeo do USB.",
            "6. Uruchom oficjalny program Thermalright/TRCC.",
            "7. W aplikacji wykonaj jedna prosta akcje: ustaw statyczny obraz testowy.",
            "8. Potem zmien obraz na drugi, bardzo rozny, np. czerwony na zielony.",
            "9. Po kazdej zmianie odczekaj kilka sekund.",
            "10. Zatrzymaj capture.",
            "11. Zapisz plik jako PCAPNG.",
        ],
    ),
    (
        "Jak zrobic dobry material do analizy",
        [
            "Najlepiej nagrac osobne sesje, np.:",
            "01_connect_and_send_red.pcapng",
            "02_send_green.pcapng",
            "03_restart_app_and_send_test_image.pcapng",
            "Im mniej zbednych klikniec w oficjalnym programie, tym latwiejsza analiza.",
            "Najbardziej wartosciowy trace zawiera tylko: start programu, wykrycie urzadzenia, upload jednego obrazu, upload drugiego obrazu.",
        ],
    ),
    (
        "Co potem sprawdzic w Wireshark",
        [
            "1. Otworzyc plik PCAPNG w Wireshark.",
            "2. Znalezc urzadzenie po VID:PID 0416:5408.",
            "3. Zanotowac device address nadany przez hosta.",
            "4. Uzyc filtra display filter, np.:",
            "usb.device_address == X",
            "lub bardziej zawazajaco:",
            "usb.device_address == X && (usb.endpoint_address == 0x09 || usb.endpoint_address == 0x81)",
        ],
    ),
    (
        "Czego szukac w trace",
        [
            "1. Pierwszych control transfer po wykryciu urzadzenia.",
            "2. Pierwszych bulk OUT na endpoint 0x09.",
            "3. Odpowiedzi bulk IN na endpoint 0x81.",
            "4. Powtarzalnych naglowkow pakietow.",
            "5. Rozmiarow blokow danych: czy ida po 512 bajtow i czy pierwszy pakiet ma inny format.",
            "6. Roznic miedzy wyslaniem czerwonego i zielonego obrazu.",
            "Jesli kilka pierwszych bajtow pozostaje stalych, a reszta danych sie zmienia, to zwykle oznacza naglowek plus payload obrazu.",
        ],
    ),
    (
        "Uwagi praktyczne",
        [
            "Jesli w capture nic nie widac, przepnij urzadzenie na inny port albo przez USB 2.0 hub.",
            "USBPcap lapie URB-y, a nie pelny sygnal z drutu. Mimo to do odtworzenia hostowego protokolu zwykle to wystarcza.",
        ],
    ),
    (
        "Co przekazac dalej",
        [
            "1. Sam plik PCAPNG.",
            "2. Krotka notatke, ktory trace odpowiada ktorej akcji.",
            "3. Informacje, jaki obraz byl wysylany.",
            "4. Informacje, czy urzadzenie bylo przepinane miedzy probami.",
        ],
    ),
]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_lines() -> list[str]:
    lines: list[str] = [TITLE, ""]
    for heading, paragraphs in SECTIONS:
        lines.append(heading.upper())
        for paragraph in paragraphs:
            wrapped = textwrap.wrap(paragraph, width=88) or [""]
            lines.extend(wrapped)
        lines.append("")
    return lines


def paginate(lines: list[str], lines_per_page: int = 44) -> list[list[str]]:
    pages: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        current.append(line)
        if len(current) >= lines_per_page:
            pages.append(current)
            current = []
    if current:
        pages.append(current)
    return pages


def make_page_stream(lines: list[str], page_number: int, page_count: int) -> bytes:
    commands = ["BT", "/F1 12 Tf", "14 TL", "72 780 Td"]
    for idx, line in enumerate(lines):
        text = pdf_escape(line)
        if idx == 0:
            commands.append(f"({text}) Tj")
        else:
            commands.append("T*")
            commands.append(f"({text}) Tj")
    footer = f"Strona {page_number}/{page_count}"
    commands.extend(["ET", "BT", "/F1 10 Tf", "72 36 Td", f"({pdf_escape(footer)}) Tj", "ET"])
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    return stream


def build_pdf(output_path: Path) -> None:
    lines = build_lines()
    pages = paginate(lines)

    objects: list[bytes] = []

    def add_object(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    font_obj = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_obj_ids: list[int] = []
    content_obj_ids: list[int] = []

    pages_placeholder = add_object(b"<< /Type /Pages /Kids [] /Count 0 >>")

    for index, page_lines in enumerate(pages, start=1):
        stream = make_page_stream(page_lines, index, len(pages))
        content = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        content_obj_id = add_object(content)
        content_obj_ids.append(content_obj_id)

        page = (
            b"<< /Type /Page /Parent "
            + f"{pages_placeholder} 0 R".encode("ascii")
            + b" /MediaBox [0 0 595 842]"
            + b" /Resources << /Font << /F1 "
            + f"{font_obj} 0 R".encode("ascii")
            + b" >> >> /Contents "
            + f"{content_obj_id} 0 R".encode("ascii")
            + b" >>"
        )
        page_obj_ids.append(add_object(page))

    kids = " ".join(f"{obj_id} 0 R" for obj_id in page_obj_ids).encode("ascii")
    pages_obj = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_obj_ids)).encode("ascii") + b" >>"
    objects[pages_placeholder - 1] = pages_obj

    catalog_obj = add_object(b"<< /Type /Catalog /Pages " + f"{pages_placeholder} 0 R".encode("ascii") + b" >>")

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = [0]
    for obj_id, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    trailer = (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root "
        + f"{catalog_obj} 0 R".encode("ascii")
        + b" >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    pdf.extend(trailer)
    output_path.write_bytes(pdf)


def main() -> None:
    output_path = Path("trofeo_usb_capture_guide.pdf")
    build_pdf(output_path)
    print(output_path.resolve())


if __name__ == "__main__":
    main()
