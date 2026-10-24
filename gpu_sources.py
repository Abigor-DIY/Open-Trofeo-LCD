"""Linux DRM/sysfs readings for AMD GPUs, without vendor utilities."""

from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


def _read_int(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
        return int(value, 16 if value.lower().startswith("0x") else 10)
    except (OSError, ValueError):
        return None


def find_amd_card(drm_root: Path = Path("/sys/class/drm")) -> Path | None:
    """Prefer the AMD card with the most VRAM over an integrated graphics card."""
    candidates: list[tuple[int, Path]] = []
    for card in drm_root.glob("card[0-9]*"):
        if not card.name[4:].isdigit():
            continue
        device = card / "device"
        if _read_int(device / "vendor") != 0x1002:
            continue
        vram = _read_int(device / "mem_info_vram_total") or 0
        candidates.append((vram, card))
    return max(candidates, key=lambda entry: (entry[0], entry[1].name))[1] if candidates else None


def has_nvidia_card(drm_root: Path = Path("/sys/class/drm")) -> bool:
    return any(
        card.name[4:].isdigit() and _read_int(card / "device" / "vendor") == 0x10DE
        for card in drm_root.glob("card[0-9]*")
    )


@lru_cache(maxsize=8)
def _amd_name(device: Path) -> str:
    for filename in ("product_name", "gpu_name"):
        try:
            name = (device / filename).read_text(encoding="utf-8").strip()
            if name:
                return name
        except OSError:
            pass
    try:
        match = re.search(r"^PCI_SLOT_NAME=(\S+)$", (device / "uevent").read_text(encoding="utf-8"), re.MULTILINE)
        lspci = shutil.which("lspci")
        if match and lspci:
            result = subprocess.run([lspci, "-s", match.group(1)], capture_output=True, text=True, timeout=0.8, check=False)
            if result.returncode == 0 and ": " in result.stdout:
                return result.stdout.strip().split(": ", 1)[1]
    except (OSError, subprocess.TimeoutExpired):
        pass
    device_id = _read_int(device / "device")
    return f"AMD Radeon (PCI {device_id:04x})" if device_id is not None else "AMD Radeon"


def read_amd_gpu_stats(card: Path) -> dict[str, str]:
    device = card / "device"
    stats = {"gpu_name": _amd_name(device)}
    load = _read_int(device / "gpu_busy_percent")
    if load is not None and 0 <= load <= 100:
        stats["gpu_load"] = f"{load}%"

    used = _read_int(device / "mem_info_vram_used")
    total = _read_int(device / "mem_info_vram_total")
    if total is not None and total > 0:
        stats["vram_total_mb"] = str(round(total / 1048576))
        if used is not None and used >= 0:
            stats["vram_used_mb"] = str(round(used / 1048576))
            stats["vram_percent"] = f"{min(100, round(used * 100 / total))}%"

    for hwmon in sorted((device / "hwmon").glob("hwmon*")):
        try:
            if (hwmon / "name").read_text(encoding="utf-8").strip() != "amdgpu":
                continue
        except OSError:
            continue
        temp = _read_int(hwmon / "temp1_input")
        if temp is not None and -40000 <= temp <= 150000:
            stats["gpu_temp"] = f"{round(temp / 1000)}°C"
            break
    return stats
