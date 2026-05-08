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

## Etap 3 - Pakiet startowych motywow

- Przygotowac 5 motywow bazowych o roznych ukladach i zestawach statystyk.
- Do kazdego motywu dostarczyc:
  - plik JSON motywu,
  - miniaturke,
  - background assets,
  - opcjonalne overlay assets.

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

## Etap 5 - Wydanie

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
