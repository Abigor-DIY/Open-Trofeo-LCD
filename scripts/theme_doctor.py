#!/usr/bin/env python3
"""
Audit Open Trofeo LCD theme documents and local theme library state.

The script is intentionally read-only by default. It checks schema validity,
missing assets, paths outside the workspace, legacy split weather/media widgets,
and heavyweight animation/video imports that are likely to hurt iteration speed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme_json_with_comments import parse_theme_json_text
from theme_schema import THEME_SCHEMA_VERSION, load_theme_document


IMAGE_SOURCE_ONLY = {
    "media_cover",
    "media_video_frame",
    "analog_clock",
    "weather_icon",
    *(f"weather_day_{idx}_icon" for idx in range(7)),
}
WEATHER_SOURCES = {
    "weather_location",
    "weather_temp_c",
    "weather_feels_like_c",
    "weather_humidity_percent",
    "weather_wind_kph",
    "weather_precip_mm",
    "weather_cloud_percent",
    "weather_code",
    "weather_condition",
    "weather_icon",
    "weather_icon_path",
    "weather_is_day",
    "weather_daily_json",
    *(f"weather_day_{idx}_{suffix}" for idx in range(7) for suffix in ("label", "condition", "icon", "temp_min_c", "temp_max_c", "precip_mm")),
}
MEDIA_SOURCES = {
    "media_title",
    "media_artist",
    "media_album",
    "media_app",
    "media_state",
    "media_cover",
    "media_video_frame",
}


def _load_json(path: Path) -> dict[str, Any]:
    raw = parse_theme_json_text(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("root JSON value is not an object")
    return raw


def _theme_json_files(root: Path) -> list[Path]:
    themes_dir = root / "themes"
    if not themes_dir.exists():
        return []
    return sorted(path for path in themes_dir.glob("*.json") if path.is_file())


def _iter_asset_refs(document: dict[str, Any]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    background = document.get("background", {})
    if isinstance(background, dict) and background.get("kind") == "image":
        path = str(background.get("path", "")).strip()
        if path:
            refs.append(("background.path", path))
    for idx, item in enumerate(document.get("images", []) if isinstance(document.get("images"), list) else []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        path = str(item.get("path", "")).strip()
        if path and source not in IMAGE_SOURCE_ONLY:
            refs.append((f"images[{idx}].path", path))
    animation = document.get("effects", {}).get("animation", {}) if isinstance(document.get("effects"), dict) else {}
    if isinstance(animation, dict):
        for idx, frame in enumerate(animation.get("frame_paths", []) if isinstance(animation.get("frame_paths"), list) else []):
            path = str(frame).strip()
            if path:
                refs.append((f"effects.animation.frame_paths[{idx}]", path))
    return refs


def _resolve_asset(theme_path: Path, asset_path: str) -> Path:
    candidate = Path(os.path.expanduser(asset_path))
    if candidate.is_absolute():
        return candidate
    return theme_path.parent / candidate


def _inside(path: Path, parent: Path) -> bool:
    try:
        resolved = path.resolve()
        base = parent.resolve()
        return resolved == base or base in resolved.parents
    except Exception:
        return False


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _legacy_counts(document: dict[str, Any]) -> dict[str, int]:
    weather = 0
    media = 0
    for item in document.get("stats", []) if isinstance(document.get("stats"), list) else []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        if source in WEATHER_SOURCES:
            weather += 1
        if source in MEDIA_SOURCES:
            media += 1
    for item in document.get("images", []) if isinstance(document.get("images"), list) else []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        if source in WEATHER_SOURCES:
            weather += 1
        if source in MEDIA_SOURCES:
            media += 1
    return {"weather": weather, "media": media}


def audit_theme(root: Path, path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path.relative_to(root) if _inside(path, root) else path),
        "name": path.stem,
        "schema_ok": False,
        "errors": [],
        "warnings": [],
        "missing_assets": [],
        "external_assets": [],
        "asset_count": 0,
        "asset_bytes": 0,
        "animation_frames": 0,
        "legacy_weather_parts": 0,
        "legacy_media_parts": 0,
        "widgets": {},
    }
    try:
        raw = _load_json(path)
    except Exception as exc:
        result["errors"].append(f"json: {exc}")
        return result

    meta = raw.get("meta", {}) if isinstance(raw.get("meta"), dict) else {}
    result["name"] = str(meta.get("name") or result["name"])
    version = raw.get("schema_version")
    if version != THEME_SCHEMA_VERSION:
        result["warnings"].append(f"schema_version={version!r}, expected {THEME_SCHEMA_VERSION}")

    try:
        document = load_theme_document(path).data
        result["schema_ok"] = True
    except Exception as exc:
        result["errors"].append(f"schema: {exc}")
        document = raw

    refs = _iter_asset_refs(document)
    result["asset_count"] = len(refs)
    for ref_name, asset in refs:
        resolved = _resolve_asset(path, asset)
        if not _inside(resolved, root):
            result["external_assets"].append({"field": ref_name, "path": asset, "resolved": str(resolved)})
        if not resolved.exists():
            result["missing_assets"].append({"field": ref_name, "path": asset, "resolved": str(resolved)})
        else:
            result["asset_bytes"] += _file_size(resolved)

    animation = document.get("effects", {}).get("animation", {}) if isinstance(document.get("effects"), dict) else {}
    if isinstance(animation, dict):
        frames = animation.get("frame_paths", [])
        result["animation_frames"] = len(frames) if isinstance(frames, list) else 0
        fps = animation.get("fps")
        if result["animation_frames"] > 360:
            result["warnings"].append(f"large animation frame set: {result['animation_frames']} frames")
        if isinstance(fps, (int, float)) and fps > 20:
            result["warnings"].append(f"high animation fps: {fps}")

    legacy = _legacy_counts(document)
    result["legacy_weather_parts"] = legacy["weather"]
    result["legacy_media_parts"] = legacy["media"]
    if legacy["weather"]:
        result["warnings"].append(f"legacy split weather parts: {legacy['weather']}")
    if legacy["media"]:
        result["warnings"].append(f"legacy split media parts: {legacy['media']}")

    widgets = document.get("widgets", [])
    if isinstance(widgets, list):
        counts: dict[str, int] = {}
        for item in widgets:
            if isinstance(item, dict):
                kind = str(item.get("kind", "unknown"))
                counts[kind] = counts.get(kind, 0) + 1
        result["widgets"] = counts
    return result


def audit_theme_library(root: Path) -> dict[str, Any]:
    library_path = root / ".trofeo-themes.json"
    result: dict[str, Any] = {"path": str(library_path), "exists": library_path.exists(), "issues": []}
    if not library_path.exists():
        return result
    try:
        raw = json.loads(library_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["issues"].append({"name": None, "issue": f"cannot read library: {exc}"})
        return result
    if not isinstance(raw, dict):
        result["issues"].append({"name": None, "issue": "library root is not an object"})
        return result
    for name, item in raw.items():
        if not isinstance(item, dict):
            result["issues"].append({"name": name, "issue": "entry is not an object"})
            continue
        rel = str(item.get("path", "")).strip()
        resolved = Path(os.path.expanduser(rel))
        if not resolved.is_absolute():
            resolved = root / resolved
        if not resolved.exists():
            result["issues"].append({"name": name, "issue": "path does not exist", "path": rel, "resolved": str(resolved)})
        elif not _inside(resolved, root):
            result["issues"].append({"name": name, "issue": "path outside workspace", "path": rel, "resolved": str(resolved)})
    return result


def workspace_size_report(root: Path) -> list[dict[str, Any]]:
    names = [
        "dist",
        "build-dir",
        ".flatpak-builder",
        "repo-current",
        ".codex-backups",
        "backups",
        "Windows_Cap",
        "themes",
    ]
    out = []
    for name in names:
        path = root / name
        if not path.exists():
            continue
        total = 0
        file_count = 0
        for child in path.rglob("*"):
            if child.is_file():
                file_count += 1
                total += _file_size(child)
        out.append({"path": name, "bytes": total, "file_count": file_count})
    return out


def build_report(root: Path) -> dict[str, Any]:
    themes = [audit_theme(root, path) for path in _theme_json_files(root)]
    return {
        "root": str(root),
        "theme_count": len(themes),
        "summary": {
            "schema_errors": sum(1 for item in themes if not item["schema_ok"]),
            "missing_assets": sum(len(item["missing_assets"]) for item in themes),
            "external_assets": sum(len(item["external_assets"]) for item in themes),
            "legacy_weather_themes": sum(1 for item in themes if item["legacy_weather_parts"]),
            "legacy_media_themes": sum(1 for item in themes if item["legacy_media_parts"]),
            "warnings": sum(len(item["warnings"]) for item in themes),
        },
        "library": audit_theme_library(root),
        "workspace_sizes": workspace_size_report(root),
        "themes": themes,
    }


def print_text(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("Open Trofeo LCD theme doctor")
    print(f"Root: {report['root']}")
    print(f"Themes: {report['theme_count']}")
    print(
        "Issues: "
        f"schema_errors={summary['schema_errors']} "
        f"missing_assets={summary['missing_assets']} "
        f"external_assets={summary['external_assets']} "
        f"legacy_weather_themes={summary['legacy_weather_themes']} "
        f"legacy_media_themes={summary['legacy_media_themes']} "
        f"warnings={summary['warnings']}"
    )
    library_issues = report["library"].get("issues", [])
    if library_issues:
        print("\nTheme library issues:")
        for issue in library_issues:
            print(f"- {issue.get('name')}: {issue.get('issue')} {issue.get('path', '')}")
    problem_themes = [
        item
        for item in report["themes"]
        if item["errors"] or item["warnings"] or item["missing_assets"] or item["external_assets"]
    ]
    if problem_themes:
        print("\nTheme issues:")
        for item in problem_themes:
            print(f"- {item['name']} ({item['file']})")
            for error in item["errors"]:
                print(f"  error: {error}")
            for warning in item["warnings"]:
                print(f"  warning: {warning}")
            for missing in item["missing_assets"][:8]:
                print(f"  missing: {missing['field']} -> {missing['path']}")
            if len(item["missing_assets"]) > 8:
                print(f"  missing: ... {len(item['missing_assets']) - 8} more")
            for external in item["external_assets"][:8]:
                print(f"  external: {external['field']} -> {external['path']}")
    if report["workspace_sizes"]:
        print("\nWorkspace size candidates:")
        for item in sorted(report["workspace_sizes"], key=lambda row: row["bytes"], reverse=True):
            mib = item["bytes"] / (1024 * 1024)
            print(f"- {item['path']}: {mib:.1f} MiB, files={item['file_count']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Open Trofeo LCD themes and local theme state.")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()
    report = build_report(args.root.resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    summary = report["summary"]
    return 1 if summary["schema_errors"] or summary["missing_assets"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
