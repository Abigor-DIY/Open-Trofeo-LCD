#!/usr/bin/env python3
"""Deterministic stats used by static GUI and documentation previews."""

from __future__ import annotations

import json
from dataclasses import dataclass

from stats_sources import StatsSnapshot


def preview_stats_values() -> dict[str, str]:
    values: dict[str, str] = {
        "hostname": "ValhallaPC",
        "ip_local": "192.168.1.42",
        "time_hms": "10:49:02",
        "date_ymd": "2026-05-18",
        "cpu_usage_percent": "42%",
        "cpu_core_avg_percent": "38%",
        "cpu_core_max_percent": "71%",
        "cpu_core_count": "16",
        "cpu_freq_ghz": "4.20",
        "cpu_temp_c": "55C",
        "load_average": "0.42",
        "mem_used_mb": "8192",
        "mem_total_mb": "32768",
        "mem_percent": "25%",
        "disk_used_gb": "512",
        "disk_total_gb": "2048",
        "disk_percent": "25%",
        "net_dl_kbps": "1200 KB/s",
        "net_ul_kbps": "180 KB/s",
        "volume_percent": "67%",
        "volume_state": "active",
        "gpu_name": "Preview GPU",
        "gpu_temp": "61C",
        "gpu_load": "44%",
        "vram_used_mb": "4096",
        "vram_total_mb": "12288",
        "vram_percent": "33%",
        "uptime_human": "1d 2h",
        "audio_eq_bars": json.dumps(
            [0.22, 0.38, 0.62, 0.78, 0.54, 0.31, 0.46, 0.72, 0.88, 0.60, 0.34, 0.50, 0.76, 0.67, 0.41, 0.29],
            separators=(",", ":"),
        ),
        "audio_eq_raw_bars": json.dumps(
            [0.18, 0.34, 0.59, 0.82, 0.49, 0.28, 0.43, 0.69, 0.91, 0.57, 0.30, 0.47, 0.73, 0.63, 0.38, 0.24],
            separators=(",", ":"),
        ),
        "audio_eq_source": "preview",
        "audio_eq_status": "running",
        "audio_eq_age_ms": "32",
        "game_active": "yes",
        "game_name": "Cyberpunk 2077",
        "game_process": "Cyberpunk2077",
        "game_launcher": "Steam/Proton",
        "game_fps": "118",
        "game_frametime_ms": "8.5 ms",
        "game_fps_source": "mangohud-log",
        "game_overlay": "MangoHud",
        "media_title": "We are the North",
        "media_artist": "Hando Viking Music",
        "media_album": "Preview Album",
        "media_app": "chromium",
        "media_state": "playing",
        "media_cover_path": "",
        "media_video_frame_path": "",
        "weather_location": "Walbrzych",
        "weather_temp_c": "21C",
        "weather_feels_like_c": "20C",
        "weather_humidity_percent": "55%",
        "weather_wind_kph": "12 km/h",
        "weather_precip_mm": "0 mm",
        "weather_cloud_percent": "25%",
        "weather_code": "1",
        "weather_condition": "Partly cloudy",
        "weather_icon": "partly_cloudy",
        "weather_icon_path": "../assets/weather/icons/meteocons/png/partly-cloudy-day.png",
        "weather_is_day": "1",
        "weather_daily_json": "[]",
    }
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    conditions = ["Cloudy", "Clear", "Rain", "Cloudy", "Sunny", "Wind", "Clear"]
    icons = ["cloudy", "clear-day", "rain", "cloudy", "clear-day", "wind", "clear-night"]
    icon_paths = [
        "../assets/weather/icons/meteocons/png/cloudy.png",
        "../assets/weather/icons/meteocons/png/clear-day.png",
        "../assets/weather/icons/meteocons/png/rain.png",
        "../assets/weather/icons/meteocons/png/cloudy.png",
        "../assets/weather/icons/meteocons/png/clear-day.png",
        "../assets/weather/icons/meteocons/png/wind.png",
        "../assets/weather/icons/meteocons/png/clear-night.png",
    ]
    for idx in range(7):
        values[f"weather_day_{idx}_label"] = labels[idx]
        values[f"weather_day_{idx}_condition"] = conditions[idx]
        values[f"weather_day_{idx}_icon"] = icons[idx]
        values[f"weather_day_{idx}_icon_path"] = icon_paths[idx]
        values[f"weather_day_{idx}_temp_min_c"] = f"{12 + idx}C"
        values[f"weather_day_{idx}_temp_max_c"] = f"{20 + idx}C"
        values[f"weather_day_{idx}_precip_mm"] = "2 mm" if idx == 2 else "0 mm"
    return values


@dataclass
class PreviewStatsProvider:
    values: dict[str, str] | None = None

    def snapshot(self) -> StatsSnapshot:
        return StatsSnapshot(values=dict(self.values or preview_stats_values()))
