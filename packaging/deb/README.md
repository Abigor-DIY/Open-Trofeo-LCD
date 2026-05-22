# Debian Package Skeleton

This directory contains the first DEB packaging scaffold for Open Trofeo LCD.
It is intended for local test packages, not a distribution-quality upload yet.

Build a local binary package from the repository root:

```bash
sudo apt install dpkg-dev debhelper dh-python
./scripts/build_deb_package.sh 0.1.0~dev20260519
```

Build an unsigned source package for Launchpad/PPA testing:

```bash
./scripts/build_deb_source_package.sh 0.1.0~dev20260519 noble
```

The source artifacts are written to `dist/deb-source/`. For a real PPA upload,
sign the generated `.source.changes` file and upload it with `dput`. The
optional second argument selects the Ubuntu series, for example `resolute`.

The package installs the application source tree under
`/usr/share/open-trofeo-lcd` and launches it through `/usr/bin/open-trofeo-lcd`.
The launcher copies the read-only installed tree into
`~/.local/share/open-trofeo-lcd-workdir` so the existing backend/theme state
files remain writable.

Before publishing a DEB, verify distro package names for PySide6, OpenCV,
Pillow, PyUSB, `playerctl`, `ffmpeg`, `cava` and optional volume helpers on the
target Ubuntu release. `trcc-linux` is not currently a normal Ubuntu package,
so this DEB uses the native PyUSB display backend by default.
