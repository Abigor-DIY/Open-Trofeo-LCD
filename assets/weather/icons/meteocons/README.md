# Meteocons Weather Icons

Bundled subset of Meteocons SVG/PNG icons for Open Trofeo LCD weather widgets.

- Source: https://github.com/basmilius/meteocons
- Package: `@meteocons/svg`
- Style: `fill`
- License: MIT, see `LICENSE`

Only the weather states needed by the first Open-Meteo integration are bundled
to keep the Flatpak and source package small. Add more icons from the same
package if future widgets need severe-weather or air-quality variants.

The original downloaded SVG subset is kept in `fill/`. Runtime widgets use
matching `png/` files because the current Pillow renderer does not rasterize SVG
without extra dependencies.

`frames/` contains generated PNG frame caches derived from the bundled
Meteocons PNG assets. They are generated with:

```bash
python3 scripts/generate_weather_icon_frames.py --clean
```

The frame cache is intentionally small and committed so the backend can animate
weather icons without rasterizing SVG/Lottie at runtime.
