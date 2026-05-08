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
- `1 x thumbnail` pod galerie w `900 x 360 PNG`
- Jesli motyw ma sekcje now playing:
  - `cover placeholder` kwadrat `512 x 512 PNG`

## Proponowane 5 motywow startowych

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
