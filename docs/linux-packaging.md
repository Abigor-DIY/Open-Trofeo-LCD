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

The Ubuntu development PPA is
[`ppa:abigor82/open-trofeo-lcd`](https://launchpad.net/~abigor82/+archive/ubuntu/open-trofeo-lcd).
The `0.1.0~dev20261025+ubuntu5` update targets **resolute**, matching the existing
PPA series. It includes automatic AMDGPU readings, a Celsius/Fahrenheit weather
setting, corrected theme animation timing and migration of the bundled Linux
themes into existing libraries. Quit and reopen the app after upgrading.

On Ubuntu resolute:

```bash
sudo add-apt-repository ppa:abigor82/open-trofeo-lcd
sudo apt update
sudo apt install open-trofeo-lcd
```

The matching GitHub release provides a standalone `.deb`, signed source-package
files and SHA-256 checksums. AppStream screenshot URLs are pinned to that release
tag so Discover can fetch the same previews that shipped with the package.

### Display rotation and missing FPS

From `0.1.0~dev20261025+ubuntu5`, Configuration groups settings into General,
Gaming, Integrations, Automation and Tools. Apply, Save Settings and Cancel
remain visible at the bottom of the window while each section scrolls
independently. Cards stack when the window becomes narrower. LCD rotation is
under **Configuration → General → LCD Preferences**; you can apply a pending
selection from any section.

For smooth rotated animations with legacy TRCC, use
`0.1.0~dev20261025+ubuntu4` or later. Older builds could reuse a stale JPEG
when a new rotated image received the same Python object id as a released frame.
The worker now retains its last submitted surface until the replacement exists;
memory stays bounded to one frame. A regression test sends 1000 changing frames
through the actual legacy TRCC encoding cache and checks their contents.

Use `0.1.0~dev20261025+ubuntu3` or later with TRCC 9.4.7: this fixes the
`QtRenderer object has no attribute rotate` crash when selecting 180°.
The bridge supports the legacy `apply_rotation` and current `rotate` renderer
APIs. Rotation is tested with both actual renderers, alongside the frame-send
and configuration tests.

From `0.1.0~dev20261025+ubuntu2`, use **Configuration → LCD Preferences →
Screen rotation** to choose **Standard (0°)** or **Flipped (180°)**, then click
**Apply**. This is a global setting for the physical LCD, independent of each
theme's canvas rotation. It applies to static images, live overlays and animations
on the next frame, without restarting the USB connection. **Cancel** restores
the last applied selection.

The backend saves this preference in `.trofeo-display.json` inside its workdir
(`~/.local/share/open-trofeo-lcd-workdir/` for the system package). It survives
restarts and package upgrades. Leave it at 0° unless the physical display needs
flipping; portrait 90°/270° output is not supported by this horizontal LCD option.

Version `0.1.0~dev20261025+ubuntu1` compensates for the rotation current TRCC
adds to frames already rotated by the Open Trofeo canvas. It preserves the
rendered frame instead of requiring edits to every bundled theme or changing
TRCC's saved orientation. The worker logs the profile's wire angle and the
compensation used. Physical output still needs confirmation on each device.

For missing FPS, use the [support report](gaming-fps-probe.md#fps-and-display-support-report)
while the game is presenting frames. It identifies missing manifests/libraries,
whether the game loaded the probe, and whether its namespace can see the socket.

### TRCC display startup

If applying a theme reports `No module named 'trcc.cli'`, upgrade to
`0.1.0~dev20261024+ubuntu2` or later, quit the app completely from its tray menu,
and reopen it. TRCC 9.11 replaced the legacy API used by older Open Trofeo
workers. The updated workers support both the legacy TRCC 9.4 API and the
current command-based API for static, overlay and animated output. They log
the selected TRCC API/version at startup. A pip/pipx launcher also uses the
Python interpreter recorded in its shebang, preserving that environment's
installed modules.

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
./scripts/build_deb_source_package.sh 0.1.0~dev20260519 noble
```

Artifacts are copied to:

```text
dist/deb-source/
```

Sign the generated `.source.changes` and upload it with `dput` to your PPA.
The optional second argument selects the Ubuntu series, for example `resolute`
on newer Ubuntu development systems.

Current status:

- package metadata, desktop entry, icon, metainfo and udev rule are installed,
- the app source tree is installed under `/usr/share/open-trofeo-lcd`,
- user systemd templates are included, and packaged backend services start
  through `/usr/bin/open-trofeo-lcd --backend-service-run` so the writable
  workdir is refreshed after package upgrades,
- the DEB also installs a global user service unit at
  `/usr/lib/systemd/user/trofeo-backend.service` and enables it globally, so
  new user sessions can start the backend service without running an extra
  installer command,
- post-install scripts reload udev rules and refresh desktop/icon caches,
- dependency names target current Ubuntu package names,
- TRCC remains optional because `trcc-linux` is not currently available as a
  normal Ubuntu package; the DEB defaults to the native PyUSB display backend.

Ubuntu Software, KDE Discover and other AppStream-aware package managers use
`packaging/flatpak/io.github.abigordiy.open-trofeo-lcd.metainfo.xml` for the app
summary, icon and screenshots. Keep `docs/screenshots/*.png` current before a
PPA upload, because the metainfo points package managers to those GitHub-hosted
images. Those URLs must resolve publicly from the exact branch or tag used in
the metainfo; otherwise Discover can list the package without useful previews,
or hide the app in some filtered views until the cache is refreshed.

Useful local checks after installing from a PPA:

```bash
appstreamcli search Trofeo
appstreamcli dump io.github.abigordiy.open-trofeo-lcd
desktop-file-validate /usr/share/applications/io.github.abigordiy.open-trofeo-lcd.desktop
appstreamcli validate --no-net /usr/share/metainfo/io.github.abigordiy.open-trofeo-lcd.metainfo.xml
```

If KDE Discover still does not refresh the entry after an upgrade, remove stale
user launchers and caches, then rebuild the KDE service cache:

```bash
scripts/cleanup_linux_test_installs.sh
scripts/cleanup_linux_test_installs.sh --apply
```

## USB Recovery After Deep Sleep

Some systems leave the Trofeo LCD in a half-awake USB state after deep suspend.
The app may still open, but applying a theme can fail, the LCD can keep an old
frame/date, or logs can show `USBTimeoutError`, `resolution (0,0)` or
`Remote end closed connection without response`.

Use the packaged recovery from the app:

```text
Configuration -> Quick Actions -> LCD USB Recovery (sudo)
```

That action opens a terminal because the reset needs root privileges. It stops
`trofeo-backend.service`, runs the packaged script in safe mode and starts the
service again:

```bash
sudo /usr/share/open-trofeo-lcd/scripts/trofeo_usb_power_cycle.sh --mode safe
```

From a source checkout, run the local script instead:

```bash
sudo scripts/trofeo_usb_power_cycle.sh --mode safe
```

Safe mode uses `USBDEVFS_RESET` only. It is intentionally conservative because
some boards can leave the display black if the port is fully power-cycled. If
safe mode does not recover a half-awake LCD, try stronger modes from a terminal:

```bash
sudo /usr/share/open-trofeo-lcd/scripts/trofeo_usb_power_cycle.sh --mode power
sudo /usr/share/open-trofeo-lcd/scripts/trofeo_usb_power_cycle.sh --mode full
```

`power` also unbinds/binds the USB device and toggles authorization. `full` can
reset the parent hub when the Trofeo LCD is the only child on that hub. Treat
`full` as the last software attempt before reboot or full power-off.

A normal reboot usually clears the condition because the USB device is
enumerated again. If the PC keeps USB powered while off/suspended, a full
power-off for a few seconds is more reliable than a warm reboot. Physical replug
should be treated as the last fallback, especially for LCDs mounted inside a PC
case.

## Audio EQ and Music Stutter

Real-time EQ uses host `cava`. To avoid touching the audio stack unnecessarily,
the backend starts CAVA lazily: only when the active theme contains an EQ visual
or when EQ settings are applied from Configuration. The automatic CAVA input
order prefers native PipeWire, then PulseAudio compatibility, then ALSA. The
default CAVA framerate is 30 FPS, and the CAVA subprocess runs at a lower CPU
priority (`nice 8`) so audio playback has priority. If music still stutters on a
specific PipeWire/PulseAudio setup, lower the framerate, force a specific input,
or disable EQ before starting the backend:

```bash
OPEN_TROFEO_CAVA_FRAMERATE=20 scripts/run_trofeo_gui.sh
OPEN_TROFEO_CAVA_INPUT=pulse scripts/run_trofeo_gui.sh
OPEN_TROFEO_CAVA_NICE=12 scripts/run_trofeo_gui.sh
OPEN_TROFEO_AUDIO_EQ=0 scripts/run_trofeo_gui.sh
```

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

Gaming distro targets:

- Fedora Workstation is the baseline RPM target.
- Bazzite Linux and Nobara Linux are priority validation targets because they
  are common gaming-focused Fedora derivatives.
- The RPM path should document both native Steam and Steam Flatpak. Flatpak
  Steam needs the Open Trofeo FPS socket override; native Steam should work
  without it.
- Release notes should position Open Trofeo LCD as an external LCD stats
  add-on for Steam Machine / SteamOS-like PCs: game FPS and frametime telemetry
  on the Trofeo display without adding an overlay to the game screen.

## Before Publishing

- Test install, launch, backend startup and uninstall in a clean VM.
- Confirm exact PySide6, OpenCV, PyUSB, Pillow and TRCC package names per distro.
- Confirm USB access with `99-trofeo-lcd.rules` and user group policy.
- Confirm host helpers: `playerctl`, `ffmpeg`, `cava` and optional `mangohud`;
  see `docs/gaming-fps.md` for the runtime logging setup.
- Decide whether DEB/RPM should depend on system packages only or create a
  managed Python venv at install time.
