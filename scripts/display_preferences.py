"""Shared, atomically saved LCD preferences, readable by display workers."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

DISPLAY_PREFERENCES_FILE = ".trofeo-display.json"


def validate_display_rotation(value) -> int:
    if isinstance(value, str) and value in {"0", "180"}:
        return int(value)
    if type(value) is int and value in {0, 180}:
        return value
    raise ValueError("display_rotation must be 0 or 180 degrees")


def read_display_rotation(path: Path, default=0) -> int:
    try:
        return validate_display_rotation(json.loads(path.read_text())["display_rotation"])
    except (OSError, ValueError, KeyError, TypeError):
        return default


def save_display_rotation(path: Path, rotation: int) -> None:
    rotation = validate_display_rotation(rotation)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=".trofeo-display-", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump({"display_rotation": rotation}, handle)
        handle.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class DisplayRotation:
    def __init__(self, path: Path | None = None):
        self.path = path or Path.cwd() / DISPLAY_PREFERENCES_FILE
        self._signature = None
        self._value = 0

    @property
    def value(self) -> int:
        try:
            info = self.path.stat()
            signature = (info.st_ino, info.st_mtime_ns, info.st_size)
        except OSError:
            self._signature, self._value = None, 0
            return 0
        if signature != self._signature:
            self._value = read_display_rotation(self.path, self._value)
            self._signature = signature
        return self._value
