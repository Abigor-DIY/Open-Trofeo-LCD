# Open Trofeo LCD - Etapy Prac

## Etap 1 - Porzadki UI i stabilizacja

- Poprawic branding: `Open Trofeo LCD` jako nazwa aplikacji, `Thermalright` jako producent.
- Naprawic gorna belke: aktywne kontrolki, mniejsza wysokosc, poprawne popupy.
- Przeprojektowac logi: pelna wysokosc, trwale zaznaczenie, sensowne kopiowanie.
- Zmienic `Menedzer motywow` na `Galeria motywow`.
- Zwiekszyc przestrzen dla kafelkow motywow.

## Etap 2 - Stabilizacja projektanta motywow

- Naprawic wszystkie sygnaly formularza designera, szczegolnie dla statystyk.
- Dodac test reczny dla pol: label, source, format, label color, value color, font flags.
- Dodac ochrone przed cichym ignorowaniem zmian po wyborze koloru z pickera.
- Dodac pasek statusu `dirty/saved` dla aktualnego motywu.
- Naprawic reakcje motywow `Now Playing` dla roznych playerow:
  - playery web based (`Chromium`, `Chrome`, `Brave`, `Firefox`)
  - playery desktopowe (`VLC`, `mpv`, `Spotify`, inne przez `playerctl`)
  - zachowac fallback, gdy player nie wystawia kompletnych metadanych lub okladki
  - rozdzielic szybka sciezke `title/state/cover` od ciezszych elementow jak `video frame`
- Odtworzyc i zabezpieczyc poprawne zachowanie motywow animowanych w bibliotece.

## Etap 3 - Pakiet startowych motywow

- Przygotowac 5 motywow bazowych o roznych ukladach i zestawach statystyk.
- Do kazdego motywu dostarczyc:
  - plik JSON motywu,
  - miniaturke,
  - background assets,
  - opcjonalne overlay assets.
- Dodac gotowe sety zegarow analogowych do szybkiego wstawiania w projektancie.
- Dodac gotowe komponenty statystyk typu:
  - gauge / radial gauge
  - progress bar
  - mini wykres liniowy
  - mini wykres slupkowy
- Dodac wskaznik glosnosci jako gotowy komponent / widget motywu.

## Etap 4 - Przygotowanie publikacji Linux

- Uporzadkowac strukturę:
  - `open-trofeo-lcd.desktop`
  - ikona aplikacji
  - katalog `packaging/`
- Przygotowac pakiety:
  - `deb`
  - `rpm`
  - `tar.gz` portable
  - opcjonalnie `AppImage`
- Zdecydowac model runtime:
  - systemowy Python + zaleznosci
  - albo bundling z PyInstaller / Nuitka

## Etap 5 - Uzytecznosc projektanta

- Status: w trakcie. Canvas obsluguje zaznaczanie, przesuwanie, skalowanie z uchwytami naroznymi i bocznymi, crop dla obrazow, snap, undo/redo oraz edycje przezroczystosci dla obrazow, paneli i widgetow.
- Umozliwic przesuwanie elementow kursorem myszy bezposrednio na canvasie.
- Umozliwic skalowanie elementow kursorem myszy z uchwytami resize.
- Dodac male menu narzedzi w edytorze:
  - zaznaczanie
  - przesuwanie
  - skalowanie
  - wycinanie / crop
- Dodac regulacje przezroczystosci dla elementow typu:
  - panel
  - obraz
  - overlay
- Dodac wyrazniejsze wskazanie aktualnego narzedzia i trybu pracy.

## Etap 6 - Wydanie

- CI build dla artefaktow Linux.
- Testy na Ubuntu / Debian, Fedora i Arch.
- Checklista wydania:
  - GUI
  - backend
  - theme designer
  - import TTCR
  - service scripts
  - desktop entry
  - uninstall / upgrade path

## Etap 7 - Animation Studio

- Wydzielic kontroler sekwencji animacji z `trofeo_gui.py` do modulu animacji:
  - normalizacja `effects.animation`
  - wybor aktualnej klatki
  - usuwanie, przesuwanie i powtarzanie klatek
  - bezpieczne uzupelnianie `frame_durations_ms`
- Rozdzielic podglad na dwa tryby:
  - `Frame preview` dla surowej klatki z dysku
  - `Composite preview` dla finalnego renderu motywu z overlayami
- Dodac `hold / repeat` bez kopiowania plikow:
  - wydluzanie czasu klatki przez `duration_ms`
  - osobna akcja fizycznego duplikowania assetu tylko gdy uzytkownik tego chce
- Przeniesc ciezsze operacje poza glowny watek GUI:
  - import klatek
  - ekstrakcja `.zt`
  - eksport ZIP
  - generowanie miniaturek
- Dodac narzedzia montazowe:
  - reverse
  - ping-pong
  - normalize durations
  - retime selection
  - loop range in/out
- Dodac komfort pracy:
  - zoom timeline
  - onion skin
  - skroty transportu
  - informacja o koszcie animacji dla USB/LCD
