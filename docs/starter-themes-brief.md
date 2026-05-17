# Starter Themes Brief

## Wspolne wymagania techniczne

- Docelowa rozdzielczosc canvasu: `1920 x 462`
- Bezpieczny format tla: `PNG`, `sRGB`, 8-bit
- Dopuszczalny format tla fotograficznego: `JPG`, jakosc wysoka
- Overlay z przezroczystoscia: `PNG`
- Elementy ikon / panele: `PNG` z alfa
- Jesli planujesz animacje:
  - sekwencja klatek `1920 x 462`
  - format `PNG` albo `JPG`
  - nazewnictwo `theme_name_frame_0001.png`

## Co dostarczyc do kazdego motywu

- `1 x background` w `1920 x 462`
- `1 x overlay` opcjonalny w `1920 x 462 PNG`
- `1 x preview` pod galerie i metainfo w `docs/screenshots/*.png`
- Jesli motyw ma sekcje now playing:
  - `cover placeholder` kwadrat `512 x 512 PNG`

## Miniatury i podglady

- Podglady generuje `python3 scripts/render_theme_previews.py`.
- Domyslny render ma szerokosc `1920 px` i zachowuje proporcje canvasu.
- Generator renderuje te same elementy, ktore widac na LCD: tla, panele, staty, widzety, widgety pogody, now playing, EQ, zegary i gauge.
- Po zmianie layoutu motywu uruchom generator i sprawdz `docs/screenshots/`.

## Pakiet dystrybucyjny: 6 motywow

Te motywy zostaja w paczce startowej:

- `Heritage Duality` (`themes/heritage_duality.json`)
- `Linux Matrix Blue` (`themes/linux_matrix_blue.json`)
- `Linux Matrix Green` (`themes/linux_matrix_green.json`)
- `New Theme` (`themes/new_theme_minimal.json`)
- `Theme` (`themes/theme_ttcr_import_4.json`)
- `Verdant Bloom` (`themes/PerunStatic.json`)

## Gotowe komponenty w Theme Designer

Szybkie dodawanie i menu komponentow powinny udostepniac:

- podstawowe: tekst, stat, obraz, panel
- wizualizacje statystyk: progress, sparkline
- audio: now playing, now playing hero, now playing mini, volume, graphic EQ
- pogoda: current, forecast, compact
- zegary analogowe: classic, modern, nordic
- gauge: system, nordic, cyber, thermal

## Proponowane profile motywow startowych

### 1. Control Center

- Charakter: techniczny dashboard
- Staty:
  - CPU usage
  - CPU core average
  - CPU temperature
  - RAM percent
  - Disk percent
  - Uptime

### 2. Now Playing Wide

- Charakter: multimedialny hero layout
- Staty:
  - media title
  - media artist
  - media state
  - CPU usage
  - RAM percent

### 3. Minimal Telemetry

- Charakter: czysty, oszczedny, duze liczby
- Staty:
  - time
  - date
  - CPU usage
  - load average
  - temperature

### 4. Network Ops

- Charakter: monitoring hosta i sieci
- Staty:
  - hostname
  - ip local
  - net download
  - net upload
  - disk used / total
  - uptime

### 5. Performance Lab

- Charakter: testowy / benchmarkingowy
- Staty:
  - CPU freq
  - CPU core max
  - GPU load
  - GPU temp
  - VRAM percent
  - load average

## Uwagi projektowe

- Trzymaj tekst w centralnym pasie wysokosci, nie przy samej gornej i dolnej krawedzi.
- Dla czytelnosci unikaj twardego tekstu bez panelu podkladu na jasnym tle.
- Jesli tlo jest bardzo szczegolowe, dostarcz tez ciemny overlay maskujacy.
