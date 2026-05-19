# Debian Package Skeleton

This directory contains the first DEB packaging scaffold for Open Trofeo LCD.
It is intended for local test packages, not a distribution-quality upload yet.

Build from the repository root:

```bash
./scripts/build_deb_package.sh 0.1.0~dev1
```

The package installs the application source tree under
`/usr/share/open-trofeo-lcd` and launches it through `/usr/bin/open-trofeo-lcd`.
The launcher copies the read-only installed tree into
`~/.local/share/open-trofeo-lcd-workdir` so the existing backend/theme state
files remain writable.

Before publishing a DEB, verify distro package names for PySide6, OpenCV,
Pillow, PyUSB, `playerctl`, `ffmpeg`, `cava` and the TRCC dependency.
