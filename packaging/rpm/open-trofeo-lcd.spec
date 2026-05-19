Name:           open-trofeo-lcd
Version:        %{?version:%{version}}%{!?version:0.1.0}
Release:        %{?release:%{release}}%{!?release:0.dev1}%{?dist}
Summary:        Linux driver and theme editor for Thermalright Trofeo LCD
%{!?_udevrulesdir:%global _udevrulesdir /usr/lib/udev/rules.d}

License:        GPL-3.0-only
URL:            https://github.com/Abigor-DIY/Open-Trofeo-LCD
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

# Dependency names vary by RPM distribution. Treat this list as the Fedora-like
# baseline and adjust before publishing distro-specific packages.
Requires:       python3
Requires:       python3-pyside6
Requires:       python3-pillow
Requires:       python3-pyusb
Requires:       playerctl
Requires:       ffmpeg
Recommends:     cava
Recommends:     python3-opencv

%description
Open Trofeo LCD is a reverse-engineered Linux driver, backend and Qt theme
editor for the Thermalright Trofeo LCD cooler display.

This is a development preview package skeleton. Dependency names for PySide6,
OpenCV, TRCC and optional audio helpers may still need per-distro adjustment.

%prep
%autosetup

%build

%install
rm -rf %{buildroot}
install -d %{buildroot}%{_datadir}/open-trofeo-lcd
cp -a . %{buildroot}%{_datadir}/open-trofeo-lcd/
rm -rf \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.git \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.agents \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.codex \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.codex-backups \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.flatpak-builder \
  %{buildroot}%{_datadir}/open-trofeo-lcd/build-dir \
  %{buildroot}%{_datadir}/open-trofeo-lcd/dist \
  %{buildroot}%{_datadir}/open-trofeo-lcd/repo \
  %{buildroot}%{_datadir}/open-trofeo-lcd/repo-current \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.venv \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.venv-gui \
  %{buildroot}%{_datadir}/open-trofeo-lcd/.venv-trcc \
  %{buildroot}%{_datadir}/open-trofeo-lcd/Windows_Cap \
  %{buildroot}%{_datadir}/open-trofeo-lcd/backups

printf 'rpm-%{version}-%{release}\\n' > %{buildroot}%{_datadir}/open-trofeo-lcd/.package-source-version

install -Dm755 packaging/linux/open-trofeo-lcd %{buildroot}%{_bindir}/open-trofeo-lcd
install -Dm644 open-trofeo-lcd.desktop %{buildroot}%{_datadir}/applications/open-trofeo-lcd.desktop
install -Dm644 packaging/flatpak/io.github.AbigorDIY.OpenTrofeoLCD.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.AbigorDIY.OpenTrofeoLCD.svg
install -Dm644 packaging/flatpak/io.github.AbigorDIY.OpenTrofeoLCD.metainfo.xml %{buildroot}%{_datadir}/metainfo/io.github.AbigorDIY.OpenTrofeoLCD.metainfo.xml
install -Dm644 99-trofeo-lcd.rules %{buildroot}%{_udevrulesdir}/99-trofeo-lcd.rules

%post
if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules || true
  udevadm trigger || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q %{_datadir}/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q %{_datadir}/icons/hicolor || true
fi

%postun
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q %{_datadir}/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q %{_datadir}/icons/hicolor || true
fi

%files
%license LICENSE
%doc README.md docs/flatpak.md docs/linux-packaging.md docs/third-party-licenses.md
%{_bindir}/open-trofeo-lcd
%{_datadir}/open-trofeo-lcd
%{_datadir}/applications/open-trofeo-lcd.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.AbigorDIY.OpenTrofeoLCD.svg
%{_datadir}/metainfo/io.github.AbigorDIY.OpenTrofeoLCD.metainfo.xml
%{_udevrulesdir}/99-trofeo-lcd.rules

%changelog
* Tue May 19 2026 Abigor-DIY <abigor-diy@users.noreply.github.com> - 0.1.0-0.dev1
- Development preview package skeleton.
