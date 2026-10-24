# Starter Themes Brief

## Wspolne wymagania techniczne

- Docelowa rozdzielczosc canvasu: `1920 x 462`
- Bezpieczny format tla: `PNG` lub `JPG`, `sRGB`, 8-bit
- Dopuszczalny format tla fotograficznego: `JPG`, jakosc wysoka
- Overlay z przezroczystoscia: `PNG`
- Elementy ikon / panele: `PNG` z alfa
- Sekwencje animacji w odswiezonych motywach:
  - sekwencja klatek `1920 x 462`
  - format `PNG` albo `JPG`
  - 8 klatek po 250 ms, petla 4 FPS
  - backend TRCC zachowuje czas klatki z motywu; limit transferu USB nie przyspiesza animacji
  - pliki w `themes/<nazwa>_assets/2026-10-10/frames/`

## Co dostarczyc do kazdego motywu

- `1 x background` w `1920 x 462` lub pierwsza klatka animacji
- `1 x overlay` opcjonalny w `1920 x 462 PNG`
- `1 x preview` pod galerie i metainfo w `docs/screenshots/*.png`
- Jesli motyw ma sekcje now playing:
  - `cover placeholder` kwadrat `512 x 512 PNG`

## Miniatury i podglady

- Podglady generuje `python3 scripts/render_theme_previews.py`.
- Domyslny render ma szerokosc `1920 px` i zachowuje proporcje canvasu.
- Generator renderuje te same elementy, ktore widac na LCD: tla, panele, staty, widzety, widgety pogody, now playing, EQ, zegary i gauge.
- Generator kompensuje `canvas.rotation`, wiec miniatury sa zapisane w orientacji widocznej w GUI.
- Po zmianie layoutu motywu uruchom generator i sprawdz `docs/screenshots/`.

## Pakiet dystrybucyjny: 10 motywow

Te motywy zostaja w paczce startowej:

- `Amber Hi-Fi` (`themes/amber_hi_fi.json`)
- `Crimson Telemetry` (`themes/crimson_telemetry.json`)
- `Kernel Console` (`themes/kernel_console.json`)
- `Neon Frame Arena` (`themes/linux_matrix_green.json`)
- `Nordic Forecast` (`themes/nordic_forecast.json`)
- `Obsidian Pulse` (`themes/obsidian_pulse.json`)
- `Penguin Circuit` (`themes/penguin_circuit.json`)
- `Verdant Bloom` (`themes/verdant_bloom.json`)
- `Orbital Relay` (`themes/orbital_relay.json`)
- `Valhalla Command` (`themes/valhalla_command.json`)

Sześć odświeżonych istniejących motywów i dwa nowe linuksowe generuje
`python3 scripts/generate_refreshed_themes.py`. `Orbital Relay` i
`Valhalla Command` pozostają bez zmian w tej rundzie.

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
