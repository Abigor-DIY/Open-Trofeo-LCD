# Third-Party Licenses

Open Trofeo LCD project code is licensed under the MIT License. Runtime and
packaging dependencies keep their own licenses.

Important bundled/runtime dependencies include:

- PySide6 / Shiboken6: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only.
- Pillow: MIT-CMU style license.
- OpenCV Python Headless: Apache-2.0.
- PyUSB: BSD-style license.
- trcc-linux and its transitive dependencies: their upstream package licenses.

Before publishing a stable binary package, generate a complete dependency
license report from the exact Flatpak build environment and ship it with the
release artifacts.
