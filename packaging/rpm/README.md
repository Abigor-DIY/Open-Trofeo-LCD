# RPM Package Skeleton

This directory contains the first RPM packaging scaffold for Open Trofeo LCD.
It is intended for local Fedora/openSUSE-style test packages, not a final
distribution submission.

Build from the repository root:

```bash
./scripts/build_rpm_package.sh 0.1.0 0.dev1
```

The package installs the application source tree under
`/usr/share/open-trofeo-lcd` and launches it through `/usr/bin/open-trofeo-lcd`.
The launcher copies the read-only installed tree into
`~/.local/share/open-trofeo-lcd-workdir` so theme/backend state remains
writable.

Before publishing an RPM, verify package dependency names for the target distro,
especially PySide6, OpenCV, Pillow, PyUSB, `playerctl`, `ffmpeg`, `cava` and
TRCC.
