#!/usr/bin/env python3
"""Validate Linux publication inputs without building packages."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "io.github.AbigorDIY.OpenTrofeoLCD"

EXPECTED_THEMES = {
    "themes/heritage_duality.json": "Heritage Duality",
    "themes/linux_matrix_green.json": "Matrix Green",
    "themes/verdant_bloom.json": "Verdant Bloom",
    "themes/wolfstorm_forge.json": "Wolfstorm Forge",
    "themes/orbital_relay.json": "Orbital Relay",
    "themes/obsidian_pulse.json": "Obsidian Pulse",
}

EXPECTED_SCREENSHOTS = {
    "docs/screenshots/open-trofeo-lcd-animation-studio.png",
    "docs/screenshots/open-trofeo-lcd-theme-designer.png",
    "docs/screenshots/open-trofeo-lcd-theme-gallery.png",
    "docs/screenshots/theme-heritage-duality.png",
    "docs/screenshots/theme-matrix-green.png",
    "docs/screenshots/theme-verdant-bloom.png",
    "docs/screenshots/theme-wolfstorm-forge.png",
    "docs/screenshots/theme-orbital-relay.png",
    "docs/screenshots/theme-obsidian-pulse.png",
}

REQUIRED_FLATPAK_SKIPS = {
    ".git",
    ".agents",
    ".codex",
    ".codex-backups",
    ".flatpak-builder",
    ".venv",
    ".venv-gui",
    ".venv-trcc",
    "build-dir",
    "dist",
    "repo",
    "repo-current",
    "Windows_Cap",
    "backups",
}

REQUIRED_PACKAGE_FILES = {
    "assets/transport/trofeo_1920x462_packet_template.bin",
    "packaging/linux/open-trofeo-lcd",
    "packaging/deb/README.md",
    "packaging/deb/debian/changelog",
    "packaging/deb/debian/control",
    "packaging/deb/debian/copyright",
    "packaging/deb/debian/rules",
    "packaging/deb/debian/open-trofeo-lcd.install",
    "packaging/deb/debian/open-trofeo-lcd.postinst",
    "packaging/deb/debian/open-trofeo-lcd.postrm",
    "packaging/deb/debian/source/format",
    "packaging/rpm/README.md",
    "packaging/rpm/open-trofeo-lcd.spec",
    "scripts/build_deb_package.sh",
    "scripts/cleanup_linux_test_installs.sh",
    "scripts/build_rpm_package.sh",
    "scripts/build_portable_release.sh",
    "docs/linux-packaging.md",
}

REQUIRED_EXECUTABLES = {
    "packaging/linux/open-trofeo-lcd",
    "packaging/deb/debian/rules",
    "packaging/deb/debian/open-trofeo-lcd.postinst",
    "packaging/deb/debian/open-trofeo-lcd.postrm",
    "scripts/build_deb_package.sh",
    "scripts/cleanup_linux_test_installs.sh",
    "scripts/build_rpm_package.sh",
    "scripts/build_portable_release.sh",
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_desktop(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def extract_repo_path(url_or_path: str) -> str:
    value = url_or_path.strip()
    marker = "/Open-Trofeo-LCD/main/"
    if marker in value:
        return value.split(marker, 1)[1]
    screenshot_marker = "/docs/screenshots/"
    if screenshot_marker in value:
        return "docs/screenshots/" + value.split(screenshot_marker, 1)[1]
    return value.lstrip("/")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def warn(condition: bool, message: str) -> None:
        if not condition:
            warnings.append(message)

    for path_text, expected_name in EXPECTED_THEMES.items():
        path = ROOT / path_text
        require(path.exists(), f"missing theme: {path_text}")
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = str(data.get("meta", {}).get("name", ""))
            require(name == expected_name, f"{path_text}: expected meta.name {expected_name!r}, got {name!r}")
            canvas = data.get("canvas", {})
            require(canvas.get("width") == 1920 and canvas.get("height") == 462, f"{path_text}: canvas must be 1920x462")
        except Exception as exc:
            errors.append(f"{path_text}: cannot parse JSON: {exc}")

    actual_theme_files = {rel(path) for path in (ROOT / "themes").glob("*.json")}
    extra_theme_files = sorted(actual_theme_files - set(EXPECTED_THEMES))
    missing_theme_files = sorted(set(EXPECTED_THEMES) - actual_theme_files)
    require(not extra_theme_files, f"unexpected bundled theme JSON files: {', '.join(extra_theme_files)}")
    require(not missing_theme_files, f"expected theme JSON files not present: {', '.join(missing_theme_files)}")

    for path_text in EXPECTED_SCREENSHOTS:
        path = ROOT / path_text
        require(path.exists(), f"missing screenshot: {path_text}")
        if path.exists():
            warn(path.stat().st_size > 20_000, f"screenshot looks too small: {path_text}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    for image_path in re.findall(r"\[[^\]]*\]\((docs/screenshots/[^)]+)\)", readme):
        require((ROOT / image_path).exists(), f"README references missing screenshot: {image_path}")

    metainfo_path = ROOT / "packaging/flatpak" / f"{APP_ID}.metainfo.xml"
    require(metainfo_path.exists(), f"missing metainfo: {rel(metainfo_path)}")
    if metainfo_path.exists():
        try:
            xml_root = ET.parse(metainfo_path).getroot()
            require(xml_root.findtext("id") == APP_ID, "metainfo app id mismatch")
            for image in xml_root.findall(".//image"):
                path_text = extract_repo_path(image.text or "")
                require((ROOT / path_text).exists(), f"metainfo references missing image: {path_text}")
        except Exception as exc:
            errors.append(f"metainfo is not valid XML: {exc}")

    for desktop_path in (
        ROOT / "open-trofeo-lcd.desktop",
        ROOT / "packaging/flatpak" / f"{APP_ID}.desktop",
    ):
        require(desktop_path.exists(), f"missing desktop entry: {rel(desktop_path)}")
        if desktop_path.exists():
            values = read_desktop(desktop_path)
            require(values.get("Type") == "Application", f"{rel(desktop_path)}: Type must be Application")
            require(values.get("Name") == "Open Trofeo LCD", f"{rel(desktop_path)}: Name mismatch")
            require(bool(values.get("Exec")), f"{rel(desktop_path)}: missing Exec")
            require(bool(values.get("Icon")), f"{rel(desktop_path)}: missing Icon")
            require(not values.get("Exec", "").startswith("/home/"), f"{rel(desktop_path)}: Exec must not be user-local")
            require(not values.get("Icon", "").startswith("/home/"), f"{rel(desktop_path)}: Icon must not be user-local")

    icon_path = ROOT / "packaging/flatpak" / f"{APP_ID}.svg"
    require(icon_path.exists(), f"missing app icon: {rel(icon_path)}")

    manifest_path = ROOT / "packaging/flatpak" / f"{APP_ID}.yml"
    require(manifest_path.exists(), f"missing Flatpak manifest: {rel(manifest_path)}")
    if manifest_path.exists():
        manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")
        for skip in sorted(REQUIRED_FLATPAK_SKIPS):
            require(f"- {skip}" in manifest_text, f"Flatpak manifest missing skip entry: {skip}")
        require("--device=all" in manifest_text, "Flatpak manifest must keep USB device access documented for test builds")
        require("--socket=session-bus" in manifest_text, "Flatpak manifest must allow MPRIS session bus access")

    portable_script = ROOT / "scripts/build_portable_release.sh"
    require(portable_script.exists(), "missing portable release builder script")
    if portable_script.exists():
        warn(portable_script.stat().st_mode & 0o111 != 0, "portable release builder is not executable")

    for path_text in sorted(REQUIRED_PACKAGE_FILES):
        require((ROOT / path_text).exists(), f"missing package skeleton file: {path_text}")

    for path_text in sorted(REQUIRED_EXECUTABLES):
        path = ROOT / path_text
        if path.exists():
            require(path.stat().st_mode & 0o111 != 0, f"package helper is not executable: {path_text}")

    wrapper_path = ROOT / "packaging/linux/open-trofeo-lcd"
    if wrapper_path.exists():
        wrapper_text = wrapper_path.read_text(encoding="utf-8", errors="replace")
        require("/usr/share/open-trofeo-lcd" in wrapper_text, "system wrapper must default to /usr/share/open-trofeo-lcd")
        require("open-trofeo-lcd-workdir" in wrapper_text, "system wrapper must use writable user workdir")
        require("/home/" not in wrapper_text, "system wrapper must not contain user-local /home paths")

    deb_control = ROOT / "packaging/deb/debian/control"
    if deb_control.exists():
        deb_text = deb_control.read_text(encoding="utf-8", errors="replace")
        require("Package: open-trofeo-lcd" in deb_text, "DEB control missing binary package")
        require("python3" in deb_text, "DEB control missing python3 dependency")

    rpm_spec = ROOT / "packaging/rpm/open-trofeo-lcd.spec"
    if rpm_spec.exists():
        spec_text = rpm_spec.read_text(encoding="utf-8", errors="replace")
        require("Name:           open-trofeo-lcd" in spec_text, "RPM spec name mismatch")
        require("%files" in spec_text, "RPM spec missing %files section")
        require("%{_bindir}/open-trofeo-lcd" in spec_text, "RPM spec missing wrapper in files")

    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"- {item}")
    if errors:
        print("Linux release check: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Linux release check: OK")
    print(f"Themes: {len(EXPECTED_THEMES)}")
    print(f"Screenshots: {len(EXPECTED_SCREENSHOTS)}")
    print("Desktop, icon, metainfo, Flatpak, DEB and RPM skeletons: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
