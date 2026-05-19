# Linux Packaging

Open Trofeo LCD currently has three Linux distribution paths:

- source/venv launch for development and hardware testing,
- experimental Flatpak for sandbox/runtime testing,
- initial DEB/RPM/portable package skeletons for broader distribution work.

Run the publication validator before building any artifact:

```bash
python3 scripts/check_linux_release.py
```

## Runtime Layout

System packages install the tracked application tree into:

```text
/usr/share/open-trofeo-lcd
```

The executable `/usr/bin/open-trofeo-lcd` is a wrapper from
`packaging/linux/open-trofeo-lcd`. It copies the installed read-only tree into:

```text
~/.local/share/open-trofeo-lcd-workdir
```

The app then runs from that writable user directory. This keeps existing
`.trofeo-*` state files, theme registry, autosaves and backend env files
compatible with the current launcher without writing into `/usr/share`.

## DEB Skeleton

Files live in `packaging/deb/debian`.

Build from the repository root:

```bash
sudo apt install dpkg-dev debhelper dh-python
./scripts/build_deb_package.sh 0.1.0~dev20260519
```

Artifacts are copied to:

```text
dist/deb/
```

For Launchpad/PPA testing, build an unsigned source package:

```bash
./scripts/build_deb_source_package.sh 0.1.0~dev20260519
```

Artifacts are copied to:

```text
dist/deb-source/
```

Sign the generated `.source.changes` and upload it with `dput` to your PPA.

Current status:

- package metadata, desktop entry, icon, metainfo and udev rule are installed,
- the app source tree is installed under `/usr/share/open-trofeo-lcd`,
- post-install scripts reload udev rules and refresh desktop/icon caches,
- dependency names target current Ubuntu package names,
- TRCC remains optional because `trcc-linux` is not currently available as a
  normal Ubuntu package; the DEB defaults to the native PyUSB display backend.

## RPM Skeleton

Files live in `packaging/rpm`.

Build from the repository root:

```bash
./scripts/build_rpm_package.sh 0.1.0 0.dev1
```

Artifacts are copied to:

```text
dist/rpm/
```

Current status:

- Fedora-like spec file with source tree install, wrapper, desktop entry, icon,
  metainfo and udev rule,
- package source version marker for wrapper refresh,
- dependency names are a baseline and still need Fedora/openSUSE verification.

## Before Publishing

- Test install, launch, backend startup and uninstall in a clean VM.
- Confirm exact PySide6, OpenCV, PyUSB, Pillow and TRCC package names per distro.
- Confirm USB access with `99-trofeo-lcd.rules` and user group policy.
- Confirm host helpers: `playerctl`, `ffmpeg` and `cava`.
- Decide whether DEB/RPM should depend on system packages only or create a
  managed Python venv at install time.
