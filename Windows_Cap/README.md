# Trofeo LCD USB Lab

Minimalny zestaw narzedzi do rozpoznania komunikacji USB z Trofeo LCD na Windows 11
i odtworzenia jej na Linuksie bez pracy w GUI Wiresharka.

Zobacz tez aktualne wnioski protokolu dla wersji linuksowej:
[docs/linux-protocol-notes.md](docs/linux-protocol-notes.md).

## 1. Znajdz VID/PID na Windows

W PowerShell:

```powershell
.\tools\list_usb_windows.ps1
```

Szukaj wpisu zwiazanego z Trofeo LCD. Interesuja nas wartosci `VID_xxxx` i
`PID_yyyy`.

W tej maszynie wykryty kandydat to:

```text
USBDISPLAY VID=0416 PID=5408 Service=WINUSB
```

## 2. Zlap krotka sesje przez USBPcap

Najlzejsza sciezka to uzyc `USBPcapCMD.exe`, bez odpalania Wiresharka. Przyklad:

```powershell
.\tools\usbpcap_capture.ps1 -Device \\.\USBPcap1 -Out captures\trofeo-init.pcapng
```

Uruchom aplikacje Trofeo, wykonaj jedna mala akcje, zatrzymaj capture przez
`Ctrl+C`.

## 3. Wyciagnij transfery do JSONL

```powershell
python .\tools\usbpcap_extract.py captures\trofeo-init.pcapng --vid 0416 --pid 5408 -o captures\trofeo-init.jsonl
```

Filtr VID/PID dziala tylko wtedy, gdy USBPcap zapisal deskryptory w przechwyceniu.
Jesli wynik jest pusty, uruchom bez `--vid/--pid`, a potem wybierz po
`bus`, `device`, `endpoint`:

```powershell
python .\tools\usbpcap_extract.py captures\trofeo-init.pcapng -o captures\all-usb.jsonl
```

Podsumowanie endpointow:

```powershell
python .\tools\usb_trace_summary.py captures\trofeo-init.jsonl
```

## 4. Probe/replay na Linuksie

Zainstaluj zaleznosc:

```bash
python3 -m pip install pyusb
```

Lista urzadzen:

```bash
python3 tools/usb_probe.py
```

Replay transferow OUT:

```bash
sudo python3 tools/usb_replay.py captures/trofeo-init.jsonl --vid 0416 --pid 5408
```

Na poczatku replayuj bardzo krotkie capture'y: start programu, init, jeden ekran.
Gdy zobaczymy powtarzalny format ramek, kolejny krok to zamiana replaya na maly
sterownik/protokol.
