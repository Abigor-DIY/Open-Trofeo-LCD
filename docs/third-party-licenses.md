# Third-Party Licenses

Open Trofeo LCD project code is licensed under the GNU General Public License
version 3.0 only (`GPL-3.0-only`). Runtime and packaging dependencies keep their
own licenses.

Important bundled/runtime dependencies include:

- PySide6 / Shiboken6: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only.
- Pillow: MIT-CMU style license.
- OpenCV Python Headless: Apache-2.0.
- PyUSB: BSD-style license.
- CAVA: MIT, used as an optional host runtime helper for real-time audio EQ.
- trcc-linux and its transitive dependencies: their upstream package licenses.
- Meteocons bundled weather SVG/PNG subset and derived PNG frame cache: MIT,
  copyright Bas Milius. See
  `assets/weather/icons/meteocons/LICENSE`.

Before publishing a stable binary package, generate a complete dependency
license report from the exact Flatpak build environment and ship it with the
release artifacts.
