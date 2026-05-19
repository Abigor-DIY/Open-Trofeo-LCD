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

- Status: w toku.
- 2026-05-19:
  - rootowy `open-trofeo-lcd.desktop` nie zawiera juz lokalnych sciezek `/home/...`,
  - Flatpak manifest wyklucza lokalne katalogi robocze i duze capture/cache z paczki,
  - dodano `scripts/check_linux_release.py` do walidacji motywow, screenow, metainfo, desktop entry i manifestu,
  - dodano `scripts/build_portable_release.sh` do tworzenia portable `tar.gz` z aktualnego commita,
  - dokumentacja opisuje walidacje Linux release i portable tarball.
- 2026-05-19:
  - dodano wspolny wrapper systemowy `packaging/linux/open-trofeo-lcd`, ktory kopiuje `/usr/share/open-trofeo-lcd` do zapisywalnego workdir uzytkownika,
  - dodano szkielet DEB w `packaging/deb/debian`,
  - dodano szkielet RPM w `packaging/rpm/open-trofeo-lcd.spec`,
  - dodano `scripts/build_deb_package.sh` i `scripts/build_rpm_package.sh`,
  - dodano `docs/linux-packaging.md` z opisem runtime layoutu i ryzyk przed publikacja.
- Uporzadkowac strukturę:
  - `open-trofeo-lcd.desktop`
  - ikona aplikacji
  - katalog `packaging/`
- Przygotowac pakiety:
  - `tar.gz` portable
  - `deb`
  - `rpm`
  - opcjonalnie `AppImage`
- Zdecydowac model runtime:
  - systemowy Python + zaleznosci
  - albo bundling z PyInstaller / Nuitka

## Etap 5 - Uzytecznosc projektanta

- Status: zakonczony. Canvas obsluguje zaznaczanie, przesuwanie, skalowanie z uchwytami naroznymi i bocznymi, crop dla obrazow, snap, undo/redo, kompaktowy inspector/Weather, grupowe presety pozycji, szybkie akcje warstw, bounds grupy oraz edycje przezroczystosci dla obrazow, paneli i widgetow.
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

- Status: w toku.
- 2026-05-18:
  - launcher lokalny tworzy `.trofeo-backend.env` z przykładu, jeżeli go brakuje,
  - `main.py` uruchamia backend z tymi samymi parametrami co service script,
  - dodano `--status` / `--check-runtime` do szybkiej diagnostyki zależności i aktywnego backendu,
  - `scripts/run_trofeo_gui.sh` przepuszcza tryby diagnostyczne i backend-only do launchera,
  - dodano `scripts/trofeo_status.sh` jako szybki status bez startowania GUI/backendu.
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

- Status: zakonczony.
- 2026-05-18:
  - dodano wspolny, deterministyczny snapshot danych dla podgladow GUI/dokumentacji,
  - galeria i okna podgladu renderuja motywy `theme-doc` jako pelna kompozycje z widgetami/statami,
  - `Composite preview` w Animation Studio jest domyslnie wlaczony i nie odpytuje live zrodel danych.
- 2026-05-18:
  - dodano kolejke/debounce generowania miniaturek klatek,
  - kolejne odswiezenia timeline nie uruchamiaja rownoleglych workerow dla tych samych obrazow,
  - cache miniaturek ma limit, zeby dlugie animacje nie rozpychaly pamieci GUI.
- 2026-05-18:
  - payload miniaturek aktualizuje tylko ikony listy i thumbnail map timeline,
  - unikamy pelnej przebudowy `QListWidget` po kazdej paczce miniaturek.
- 2026-05-18:
  - dodano postep importu/eksportu animacji w statusie zadan,
  - dodano anulowanie importu/eksportu, w tym przerywanie ffmpeg przy imporcie wideo,
  - Etap 7 domkniety: kontroler animacji, podglady, hold/repeat, workery, narzedzia montazowe i ergonomia timeline sa wdrozone.
- Zrobione: wydzielic kontroler sekwencji animacji z `trofeo_gui.py` do modulu animacji:
  - normalizacja `effects.animation`
  - wybor aktualnej klatki
  - usuwanie, przesuwanie i powtarzanie klatek
  - bezpieczne uzupelnianie `frame_durations_ms`
- Zrobione: rozdzielic podglad na dwa tryby:
  - `Frame preview` dla surowej klatki z dysku
  - `Composite preview` dla finalnego renderu motywu z overlayami
- Zrobione: dodac `hold / repeat` bez kopiowania plikow:
  - wydluzanie czasu klatki przez `duration_ms`
  - osobna akcja fizycznego duplikowania assetu tylko gdy uzytkownik tego chce
- Zrobione: przeniesc ciezsze operacje poza glowny watek GUI:
  - import klatek
  - ekstrakcja `.zt`
  - eksport ZIP
  - generowanie miniaturek
- Zrobione: dodac narzedzia montazowe:
  - reverse
  - ping-pong
  - normalize durations
  - retime selection
  - loop range in/out
- Zrobione: dodac komfort pracy:
  - zoom timeline
  - onion skin
  - skroty transportu
  - informacja o koszcie animacji dla USB/LCD

## Backlog funkcji

- Zegary swiatowe jako gotowy widget: czas dla wybranych miast na swiecie, np. 3 konfigurowalne zegary w jednym komponencie.
- Statystyki gier/FPS jako gotowy widget: FPS, frametime/frames i dane z linuksowych nakladek, gdy uruchomiona jest gra.
- Orientacja pionowa wyswietlacza: profile layoutu, podglad i renderer dla obrotu 90/270 stopni.
- Hostowanie motywow w sieci: zdalny katalog motywow, pobieranie/import paczek oraz aktualizacje motywow z kontrola wersji.
