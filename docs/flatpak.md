# Experimental Flatpak Packaging

Open Trofeo LCD currently ships an experimental Flatpak manifest for local
testing. The source/venv launcher is still the primary supported path until USB
access and runtime permissions are verified on more systems.

## Install Build Tools

On Ubuntu/Kubuntu/Debian:

```bash
sudo apt install flatpak flatpak-builder
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08
```

## Build And Install Locally

Run from the repository root:

```bash
flatpak-builder --force-clean --user --install build-dir packaging/flatpak/io.github.AbigorDIY.OpenTrofeoLCD.yml
flatpak run io.github.AbigorDIY.OpenTrofeoLCD
```

## Install Release Bundle

Download `open-trofeo-lcd-0.1.0-dev.flatpak` from the GitHub Release page, then:

```bash
flatpak install --user ./open-trofeo-lcd-0.1.0-dev.flatpak
flatpak run io.github.AbigorDIY.OpenTrofeoLCD
```

If your environment does not expose `/dev/fuse`, use:

```bash
flatpak-builder --force-clean --disable-rofiles-fuse --user --install build-dir packaging/flatpak/io.github.AbigorDIY.OpenTrofeoLCD.yml
```

## Current Permissions

The development manifest intentionally uses broad permissions:

- `--device=all` for direct access to the Thermalright Trofeo LCD USB device.
- `--filesystem=home` so users can import images, themes and TTCR files while the editor is still evolving.
- `--socket=session-bus` for MPRIS media metadata from Chromium, Spotify, VLC and other players.
- `--share=network` because the GUI talks to the local backend over `127.0.0.1:18777`.

These permissions should be tightened after hardware testing confirms the
minimal working set.

## Python Dependencies

Flatpak-specific Python versions are pinned in
`packaging/flatpak/requirements.txt`. The build currently lets the dependency
module access the network so `pip` can download wheels from PyPI. Before a
stable public Flatpak release, this should be replaced with generated source
entries and hashes, for example with `flatpak-pip-generator`, so builds do not
depend on live PyPI resolution.

## USB Notes

The LCD identifies as `0416:5408`. For source launches, install the udev rule
from `99-trofeo-lcd.rules`. For Flatpak, `--device=all` is used for the first
test package, but the final distribution may still need documented udev rules
depending on distro policy and user group permissions.

If applying a theme fails with `Resource busy`, make sure no second backend,
service or old `replay_from_pcap.py`/`trofeo_lcd.py` process is still using the
LCD.

## Known Limitations

- Python dependencies are installed from the Flatpak-specific pinned
  requirements file during the build. This is acceptable for the first local
  test package, but a release Flatpak should use generated source entries with
  hashes.
- The package has not yet been validated on clean systems without the source
  checkout.
- DEB/RPM packages are planned after the Flatpak runtime layout is stable.
