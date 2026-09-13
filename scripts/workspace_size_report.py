#!/usr/bin/env python3
"""
Report large local Open Trofeo LCD workspace directories.

Read-only helper for deciding what can be cleaned before Flatpak builds,
backups, or captures make the tree unwieldy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_TARGETS = [
    "dist",
    "build-dir",
    ".flatpak-builder",
    "repo-current",
    ".codex-backups",
    "backups",
    "Windows_Cap",
    "themes",
    ".venv",
    ".venv-gui",
    ".venv-trcc",
]


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def measure(path: Path) -> dict[str, object]:
    total = 0
    files = 0
    dirs = 0
    if path.is_file():
        return {"path": str(path), "exists": True, "bytes": _file_size(path), "files": 1, "dirs": 0}
    if not path.exists():
        return {"path": str(path), "exists": False, "bytes": 0, "files": 0, "dirs": 0}
    for child in path.rglob("*"):
        if child.is_file():
            files += 1
            total += _file_size(child)
        elif child.is_dir():
            dirs += 1
    return {"path": str(path), "exists": True, "bytes": total, "files": files, "dirs": dirs}


def human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Report local workspace size hot spots.")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("targets", nargs="*", help="optional paths relative to root")
    args = parser.parse_args()
    root = args.root.resolve()
    targets = args.targets or DEFAULT_TARGETS
    rows = [measure((root / target).resolve()) for target in targets]
    rows.sort(key=lambda row: int(row["bytes"]), reverse=True)
    report = {"root": str(root), "targets": rows}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Open Trofeo LCD workspace size report")
        print(f"Root: {root}")
        for row in rows:
            if not row["exists"]:
                continue
            try:
                rel = Path(str(row["path"])).relative_to(root)
            except ValueError:
                rel = Path(str(row["path"]))
            print(f"- {rel}: {human_size(int(row['bytes']))}, files={row['files']}, dirs={row['dirs']}")
        print("\nRead-only report. No files were removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
