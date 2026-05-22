# Thermalright Trofeo LCD — Pełna dokumentacja protokołu USB
# Reverse-engineering z USB capture (Windows TRCC → Wireshark/USBPcap)
# Stan na: 21.04.2026

## 1. IDENTYFIKACJA URZĄDZENIA

- VID:PID: 0416:5408 (Winbond Electronics Corp.)
- USB Class: Vendor Specific (0xFF), SubClass 0x00, Protocol 0x00
- bcdUSB: 0x0210
- bMaxPacketSize0: 64
- Konfiguracja: 1 interfejs, 2 endpointy
- EP OUT: 0x09 (Bulk, wMaxPacketSize=512)
- EP IN:  0x81 (Bulk, wMaxPacketSize=512)
- Zasilanie: NOT SELF-POWERED, REMOTE-WAKEUP
- Rozdzielczość wyświetlacza: 1920×462 pikseli
- Format obrazu: JPEG baseline, 4:2:0, ~85 quality, DPI 96×96

## 2. SEKWENCJA PROTOKOŁU

```
1. Standardowa enumeracja USB:
   GET_DESCRIPTOR DEVICE
   GET_DESCRIPTOR CONFIGURATION
   SET_CONFIGURATION 1

2. INIT (jednorazowo, WYMAGANE):
   → Bulk OUT EP9: 2048 bajtów, cmd=0x02
   ← Bulk IN  EP1:  512 bajtów, cmd=0x03 (device info)

3. Pętla ramek JPEG:
   → N × Bulk OUT EP9: 4096 bajtów, cmd=0x01 (chunki JPEG)
   → 1 × Bulk OUT EP9: 2048 bajtów, cmd=0x01 (ostatni chunk)
   ← 1 × Bulk IN  EP1:  512 bajtów, cmd=0x03 (frame ACK)
   (powtarzaj ~6.3 FPS)
```

Nie ma ŻADNYCH vendor control transferów (bmRequestType=0x40/0xC0).
Nie ma żadnych dodatkowych komend między ramkami.
Zmiana obrazu/animacja = po prostu wysyłanie kolejnych JPEG-ów.

## 3. KOMENDA INIT (cmd=0x02)

### Wysyłka (Bulk OUT EP9, 2048 bajtów):
```
Offset  Wartość   Opis
[0]     0x02      Komenda: INIT/QUERY
[1]     0xFF      Marker
[2..7]  0x00      Zera
[8]     0x01      Stała
[9..2047] 0x00    Zera (padding)
```

Hex pierwszych 16 bajtów:
`02 ff 00 00 00 00 00 00 01 00 00 00 00 00 00 00`

### Odpowiedź (Bulk IN EP1, 512 bajtów):
```
Offset  Wartość         Opis
[0]     0x03            Komenda: RESPONSE
[1]     0xFF            Marker
[2..7]  0x00            Zera
[8]     0x01            Status OK
[9..15] 0x00            Zera
[16..19] 0x1cac2c86     Device ID / firmware version
[20]    0x02            Nieznane (typ urządzenia?)
[21]    0x00            -
[22]    0x04            Nieznane (ilość buforów?)
[23]    0x00            -
[24..27] 0x00000780     Szerokość wyświetlacza LE32 = 1920
[28..31] 0x00000257     Wysokość bufora LE32 = 599
[32]    0x32            50 (JPEG quality? lub FPS?)
[33..39] 0x00           -
[40]    0x02            Nieznane
[41..43] 0x00           -
[44]    0x89            137 — nieznane
[45..511] 0x00          Padding
```

UWAGA: Wysokość bufora (599) ≠ wysokość JPEG (462). TRCC wysyła JPEG 1920×462.

## 4. RAMKA JPEG (cmd=0x01)

### Nagłówek chunka (16 bajtów, na początku każdego pakietu USB):

```
Offset  Rozmiar  Opis
[0]     1        Komenda: 0x01 (dane obrazu)
[1]     1        Marker: 0xFF
[2..5]  4        Rozmiar JPEG w bajtach (uint32 LE)
[6]     1        Stała: 0xF0
[7]     1        Stała: 0x01
[8]     1        Stała: 0x01
[9]     1        Zmienna — koreluje z rozmiarem JPEG (możliwy checksum/hash)
[10]    1        Tryb: 0x02 (normalny) lub 0x01 (mniejszy obraz)
[11]    1        Sekwencja w ramce: 0x00, 0x08, 0x10, 0x18, ... (krok 8)
[12]    1        Indeks bufora: cyklicznie 0, 1, 2 (triple buffering)
[13..15] 3       Zera (padding)
```

### Przykłady nagłówków z capture:

Pierwszy chunk ramki (seq=0x00):
`01 ff 88 ba 04 00 f0 01 01 71 02 00 00 00 00 00`
→ JPEG size = 0x0004BA88 = 309896 bytes, buffer=0

Kolejny chunk (seq=0x08):
`01 ff 88 ba 04 00 f0 01 01 71 02 08 00 00 00 00`

Kolejny chunk (seq=0x10):
`01 ff 88 ba 04 00 f0 01 01 71 02 10 00 00 00 00`

### Struktura transferu jednej ramki:

Dla JPEG ~310KB:
- 76 pakietów × 4096B (nagłówek 16B + dane 4080B = 76 × 4080 = 310,080B danych)
- 1 pakiet × 2048B (nagłówek 16B + reszta danych + padding zerami)
- Razem: 77 bulk OUT transfers
- Po ostatnim: 1 bulk IN (512B) = ACK

### Frame ACK (Bulk IN EP1, 512 bajtów):
```
[0]     0x03    Response
[1]     0xFF    Marker
[2..7]  0x00    Zera
[8]     0x01    Status OK
[9..511] 0x00   Zera
```

INIT response ma dodatkowe dane [16..44], zwykły frame ACK ma [16..511] = same zera.

## 5. BAJT [9] — ANALIZA

Bajt [9] zmienia się razem z rozmiarem JPEG. Obserwacje:

| JPEG size  | Bajt [9] |
|------------|----------|
| 309896     | 0x71     |
| 309688     | 0x71     |
| 310078     | 0x72     |
| 224386     | 0xC5     |
| 340935     | 0xB0     |
| 340630     | 0xAF     |
| 341027     | 0xB0     |
| 364756     | 0xE0     |
| 355955     | 0xCE     |
| 353669     | 0xCA     |
| 350449     | 0xC3     |
| 344826     | 0xB8     |
| 337728     | 0xA9     |

Nie jest to prosty offset rozmiaru. Może być CRC8, lookup table, lub checksum.
Przetestowane formuły, ŻADNA nie pasuje do danych:
- (size >> 12) & 0xFF — nie pasuje
- XOR bajtów rozmiaru — nie pasuje
- suma bajtów rozmiaru — nie pasuje
- ilość chunków — nie pasuje
- żadna prosta formuła liniowa/shift/modulo

Strategia testowania:
1. Najpierw spróbuj [9]=0x00 — urządzenie może go ignorować
2. Jeśli nie działa, skopiuj wartość z reference frame (0x71 dla 309896B JPEG)
3. Jeśli nadal nie działa, wyślij reference_frame_trcc.jpg bajt-w-bajt z oryginalnym nagłówkiem z capture
4. Ostatecznie: przechwycić więcej par (size, b9) i szukać lookup table w firmware

## 6. TRIPLE BUFFERING — BAJT [12]

TRCC wysyła ramki z cyklicznym indeksem bufora w bajcie [12]:
Frame 0: [12]=0x02
Frame 1: [12]=0x00
Frame 2: [12]=0x01
Frame 3: [12]=0x02
Frame 4: [12]=0x00
...

Cykl: 2, 0, 1, 2, 0, 1, ... (lub inaczej: startuje od 2, potem 0, 1, 2, 0, 1, ...)

Może to być nieistotne (urządzenie może ignorować ten bajt) lub krytyczne
(urządzenie może wymagać poprawnego indeksu bufora do wyświetlenia ramki).

## 7. PARAMETRY JPEG Z REFERENCE FRAME

Z analizy JPEG wysyłanego przez TRCC:
- JFIF 1.01, DPI 96×96
- Baseline, precision 8
- 1920×462, 3 komponenty (YCbCr)
- Subsampling: Y=2×2, Cb=1×1, Cr=1×1 (4:2:0)
- 2 tablice kwantyzacji (odpowiada quality ~85)
- Typowy rozmiar: 300-370 KB

Pillow generuje kompatybilny JPEG przez:
```python
image.save(buf, format='JPEG', quality=85, subsampling='4:2:0')
```

## 8. CO DZIAŁA NA LINUXIE (stan testów)

1. ✅ Linux widzi urządzenie 0416:5408
2. ✅ pyusb przejmuje interfejs (claim_interface)
3. ✅ Bulk OUT EP9 działa (wysyłka pełnej ramki, 77 pakietów)
4. ✅ Bulk IN EP1 działa (odczyt ACK, poprawny wzorzec 03 ff 00...)
5. ✅ Reset/recovery urządzenia
6. ✅ Raw JPEG passthrough (bajt-w-bajt plik z TRCC)
7. ✅ Format JPEG reference i generowany są strukturalnie zgodne
8. ❌ LCD zostaje na logo producenta — nie przełącza na przesłany obraz

## 9. CO BYŁO BRAKUJĄCEGO

Komenda INIT (cmd=0x02) — musi być wysłana raz po podłączeniu/enumeracji,
PRZED jakimikolwiek danymi JPEG. Bez niej urządzenie ignoruje bulk data.

Dodana do drivera jako metoda `_init_device()`.

## 10. CO MOŻE JESZCZE BLOKOWAĆ (hipotezy do testowania)

Jeśli po dodaniu INIT nadal nie działa:

1. **Bajt [9]** — urządzenie może walidować ten bajt i odrzucać ramki z błędną wartością
2. **Triple buffering [12]** — urządzenie może wymagać poprawnego cyklu 2,0,1,2,0,1,...
3. **Bajt [10]** — 0x02 vs 0x01 może kontrolować tryb wyświetlania
4. **Rozmiar JPEG** — urządzenie może wymagać rozmiaru w polu [2..5] dokładnie
   odpowiadającego rzeczywistemu rozmiarowi JPEG (driver to robi)
5. **Timing** — urządzenie może wymagać minimalnej przerwy między ramkami
   (TRCC wysyła co ~155ms = 6.3 FPS)
6. **Wielokrotne wysłanie** — TRCC wysyła każdy obraz 3× (triple buffer),
   może urządzenie wymaga min. 3 ramek do przełączenia

## 11. DOSTĘPNE PLIKI

- `reference_frame_trcc.jpg` — JPEG wyciągnięty z capture, dokładnie taki jaki TRCC wysyła (1920×462, 318KB)
- `trofeo_lcd.py` — driver Python z pyusb (z dodanym INIT)
- `99-trofeo-lcd.rules` — reguła udev
- Pliki pcapng z capture (dostępne u użytkownika)

## 12. UDEV RULE

```
SUBSYSTEM=="usb", ATTR{idVendor}=="0416", ATTR{idProduct}=="5408", MODE="0666", TAG+="uaccess"
```

Instalacja:
```bash
sudo cp 99-trofeo-lcd.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## 13. ŚRODOWISKO UŻYTKOWNIKA

- Linux: Kubuntu 26.04 beta, Ryzen 7 7800X3D / RTX 5060 Ti
- Hostname: ValhallaPC, user: abigor
- Trofeo podłączony przez hub USB (Terminus Tech 1a40:0101)
- Na Linuxie urządzenie jest pod innym root hubem niż fizyczny port
- Python 3, pyusb, Pillow zainstalowane

## 14. RAW HEX Z CAPTURE — DO ODTWORZENIA 1:1

### INIT OUT (pełne 2048 bajtów, tylko pierwsze 16 niezerowe):
```
02 ff 00 00 00 00 00 00 01 00 00 00 00 00 00 00
[reszta: 2032 × 0x00]
```

### INIT RESPONSE (512 bajtów, niezerowe bajty):
```
03 ff 00 00 00 00 00 00 01 00 00 00 00 00 00 00
1c ac 2c 86 02 00 04 00 80 07 00 00 57 02 00 00
32 00 00 00 00 00 00 00 02 00 00 00 89 00 00 00
[reszta: 464 × 0x00]
```

### Pierwszy chunk JPEG z capture (nagłówek 16B + początek JPEG):
```
01 ff 88 ba 04 00 f0 01 01 71 02 00 00 00 00 00
ff d8 ff e0 00 10 4a 46 49 46 00 01 01 01 00 60
00 60 00 00 ff db 00 43 ...
```

### Frame ACK (512 bajtów):
```
03 ff 00 00 00 00 00 00 01 00 00 00 00 00 00 00
[reszta: 496 × 0x00]
```

## 15. DRIVER PYTHON — KLUCZOWE FRAGMENTY

### Init:
```python
init_packet = bytearray(2048)
init_packet[0] = 0x02  # cmd: INIT
init_packet[1] = 0xFF  # marker
init_packet[8] = 0x01
dev.write(0x09, bytes(init_packet), 5000)
response = dev.read(0x81, 512, 5000)
# response[0] should be 0x03, response[8] should be 0x01
```

### Wysyłka JPEG:
```python
# Dla każdego chunka 4080 bajtów danych JPEG:
header = bytearray(16)
header[0] = 0x01   # cmd: image
header[1] = 0xFF   # marker
struct.pack_into('<I', header, 2, jpeg_total_size)
header[6] = 0xF0
header[7] = 0x01
header[8] = 0x01
header[9] = 0x00   # TODO: unknown, try 0x00 first
header[10] = 0x02  # mode
header[11] = seq   # 0x00, 0x08, 0x10, ... (krok 8)
header[12] = buf_idx  # 0, 1, 2 cyklicznie między ramkami

packet = header + jpeg_chunk_data  # pad to 4096 or 2048 for last
dev.write(0x09, bytes(packet), 5000)

# Po ostatnim chunku:
ack = dev.read(0x81, 512, 5000)
```

### Endpoints:
```python
EP_OUT = 0x09  # Bulk OUT
EP_IN  = 0x81  # Bulk IN
INTERFACE = 0
VID = 0x0416
PID = 0x5408
```
