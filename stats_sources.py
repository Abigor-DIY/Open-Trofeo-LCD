#!/usr/bin/env python3
"""
System statistics sources for Open Trofeo LCD themes.
"""

from __future__ import annotations

import os
import subprocess
import time
import re
import shutil
import threading
import hashlib
import json
import mimetypes
import tempfile
import math
from urllib.parse import unquote, urlparse, urlencode
from urllib.request import Request, urlopen
from dataclasses import dataclass


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.0f}%"


def _parse_proc_stat():
    total = None
    cores = []

    with open("/proc/stat", "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("cpu"):
                break
            parts = line.split()
            if len(parts) < 5:
                continue
            label = parts[0]
            values = [int(x) for x in parts[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            busy = sum(values) - idle
            pair = (busy, idle)
            if label == "cpu":
                total = pair
            elif label.startswith("cpu") and label[3:].isdigit():
                cores.append(pair)

    return total, cores


@dataclass
class StatsSnapshot:
    values: dict[str, str]


class StatsProvider:
    def __init__(self) -> None:
        self._cpu_snapshot = None
        self._cpu_core_snapshot = None
        self._net_io_snapshot = (time.time(), 0, 0)
        self._last_volume_snapshot = {"volume_percent": "N/A", "volume_state": "N/A"}
        self._last_volume_at = 0.0
        self._gpu_type = self._detect_gpu_type()
        self._last_media_snapshot = self._default_media_snapshot()
        self._last_media_at = 0.0
        self._ffmpeg_bin = shutil.which("ffmpeg")
        self._media_cover_cache: dict[str, str] = {}
        self._media_cover_failures: dict[str, float] = {}
        self._public_api_lock = threading.Lock()
        self._musicbrainz_last_request_at = 0.0
        self._media_frame_cache: dict[str, str] = {}
        self._media_frame_jobs: set[str] = set()
        self._media_frame_failures: dict[str, float] = {}
        self._media_frame_lock = threading.Lock()
        self._media_frame_runtime_dir = os.path.join(
            os.path.expanduser("~/.local/state/open-trofeo-lcd/runtime"),
            "media-video-frames",
        )
        self._media_cover_runtime_dir = os.path.join(
            os.path.expanduser("~/.local/state/open-trofeo-lcd/runtime"),
            "media-covers",
        )
        state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        self._audio_eq_runtime_dir = os.path.join(state_home, "open-trofeo-lcd", "audio-eq")
        self._audio_eq_lock = threading.Lock()
        self._audio_eq_bars: list[float] = [0.0] * 32
        self._audio_eq_raw_bars: list[float] = [0.0] * 32
        self._audio_eq_last_shape_at = 0.0
        self._audio_eq_updated_at = 0.0
        self._audio_eq_status = "unavailable"
        self._audio_eq_source = "none"
        self._audio_eq_process: subprocess.Popen[bytes] | None = None
        self._audio_eq_thread_started = False
        self._audio_eq_cava_bin = self._local_or_host_cmd("cava")
        self._audio_eq_input_method = self._normalize_audio_eq_input(os.environ.get("OPEN_TROFEO_CAVA_INPUT", "pulse"))
        self._weather_runtime_dir = os.path.join(state_home, "open-trofeo-lcd", "weather")
        self._weather_cache_path = os.path.join(self._weather_runtime_dir, "open-meteo.json")
        self._weather_icon_map = self._load_weather_icon_map()
        self._weather_lat = self._weather_float(os.environ.get("OPEN_TROFEO_WEATHER_LAT", ""))
        self._weather_lon = self._weather_float(os.environ.get("OPEN_TROFEO_WEATHER_LON", ""))
        self._weather_location = os.environ.get("OPEN_TROFEO_WEATHER_LOCATION", "").strip()
        self._weather_refresh_s = self._parse_weather_refresh_s(os.environ.get("OPEN_TROFEO_WEATHER_REFRESH_S", "900"))
        self._last_weather_snapshot = self._default_weather_snapshot()
        self._last_weather_at = 0.0
        self._last_weather_error = ""
        self._last_weather_source = "none"
        self._weather_lock = threading.Lock()
        self._weather_refresh_inflight = False
        self._start_audio_eq_thread()

    def _start_audio_eq_thread(self) -> None:
        if self._audio_eq_thread_started:
            return
        if str(os.environ.get("OPEN_TROFEO_AUDIO_EQ", "")).strip().lower() in {"0", "false", "off", "no"}:
            self._audio_eq_status = "disabled"
            return
        if not self._audio_eq_cava_bin:
            self._audio_eq_status = "unavailable"
            return
        self._audio_eq_thread_started = True
        thread = threading.Thread(target=self._audio_eq_worker, name="trofeo-audio-eq", daemon=True)
        thread.start()

    @staticmethod
    def _normalize_audio_eq_input(value: object) -> str:
        method = str(value or "pulse").strip().lower() or "pulse"
        if method not in {"pulse", "pipewire", "alsa", "fifo", "sndio", "oss", "portaudio"}:
            return "pulse"
        return method

    def set_audio_eq_config(self, *, input_method: object | None = None, restart: bool = True) -> dict[str, object]:
        if input_method is not None:
            self._audio_eq_input_method = self._normalize_audio_eq_input(input_method)
        if restart:
            with self._audio_eq_lock:
                self._audio_eq_bars = [0.0] * 32
                self._audio_eq_raw_bars = [0.0] * 32
                self._audio_eq_last_shape_at = 0.0
                self._audio_eq_updated_at = 0.0
                self._audio_eq_status = "restarting" if self._audio_eq_cava_bin else "unavailable"
                self._audio_eq_source = "cava" if self._audio_eq_cava_bin else "none"
            proc = self._audio_eq_process
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            self._start_audio_eq_thread()
        return self.audio_eq_status()

    def _audio_eq_config_path(self) -> str:
        runtime_dir = self._audio_eq_runtime_dir
        try:
            os.makedirs(runtime_dir, exist_ok=True)
        except OSError:
            runtime_dir = os.path.join(tempfile.gettempdir(), "open-trofeo-lcd", "audio-eq")
            os.makedirs(runtime_dir, exist_ok=True)
        path = os.path.join(runtime_dir, "cava.conf")
        input_method = self._normalize_audio_eq_input(self._audio_eq_input_method)
        content = "\n".join(
            [
                "[general]",
                "bars = 32",
                "framerate = 30",
                "autosens = 1",
                "",
                "[input]",
                f"method = {input_method}",
                "",
                "[output]",
                "method = raw",
                "data_format = ascii",
                "ascii_max_range = 1000",
                "channels = mono",
                "",
            ]
        )
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except Exception:
            pass
        return path

    @staticmethod
    def _parse_audio_eq_line(raw: bytes) -> list[float]:
        if not raw:
            return []
        if raw.startswith(b"\x1b]") or raw.startswith(b"\x1b["):
            return []
        text = raw.decode("utf-8", errors="ignore").strip()
        if re.search(r"[A-Za-z]", text):
            return []
        numbers = [float(match) for match in re.findall(r"-?\d+(?:\.\d+)?", text)]
        if len(numbers) >= 2:
            peak = max(1.0, max(numbers))
            scale = 1000.0 if peak <= 1000.0 else peak
            return [max(0.0, min(1.0, value / scale)) for value in numbers[:64]]
        values = [byte for byte in raw.strip() if byte not in (10, 13, 59, 32, 9)]
        if not values:
            return []
        if len(values) < 2:
            return []
        peak = max(1, max(values))
        return [max(0.0, min(1.0, value / peak)) for value in values[:64]]

    @staticmethod
    def _resample_audio_eq_levels(levels: list[float], count: int = 32) -> list[float]:
        clean = [max(0.0, min(1.0, float(value))) for value in levels if isinstance(value, (int, float))]
        if not clean:
            return [0.0] * count
        if len(clean) == count:
            return clean
        if len(clean) == 1:
            return [clean[0]] * count
        out: list[float] = []
        for idx in range(count):
            pos = (idx / float(max(1, count - 1))) * (len(clean) - 1)
            left = int(math.floor(pos))
            right = min(len(clean) - 1, left + 1)
            frac = pos - left
            out.append(clean[left] * (1.0 - frac) + clean[right] * frac)
        return out

    def _shape_audio_eq_levels_locked(self, levels: list[float], now: float) -> list[float]:
        raw = self._resample_audio_eq_levels(levels, 32)
        previous = self._audio_eq_bars if len(self._audio_eq_bars) == 32 else [0.0] * 32
        dt = max(1.0 / 120.0, min(0.25, now - self._audio_eq_last_shape_at)) if self._audio_eq_last_shape_at > 0 else 1.0 / 30.0
        attack = 1.0 - math.exp(-dt / 0.030)
        release = 1.0 - math.exp(-dt / 0.145)
        shaped: list[float] = []
        gate = 0.018
        for idx, value in enumerate(raw):
            if value <= gate:
                target = 0.0
            else:
                target = ((value - gate) / (1.0 - gate)) ** 0.72
            prev = previous[idx]
            alpha = attack if target >= prev else release
            shaped.append(prev + (target - prev) * alpha)
        if len(shaped) >= 3:
            smoothed = list(shaped)
            for idx in range(1, len(shaped) - 1):
                smoothed[idx] = shaped[idx] * 0.78 + shaped[idx - 1] * 0.11 + shaped[idx + 1] * 0.11
            shaped = smoothed
        self._audio_eq_raw_bars = raw
        self._audio_eq_last_shape_at = now
        return [max(0.0, min(1.0, value)) for value in shaped]

    def _audio_eq_worker(self) -> None:
        while True:
            try:
                config_path = self._audio_eq_config_path()
                with self._audio_eq_lock:
                    self._audio_eq_status = "starting"
                    self._audio_eq_source = "cava"
                process = subprocess.Popen(
                    [*self._audio_eq_cava_bin, "-p", config_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                self._audio_eq_process = process
                with self._audio_eq_lock:
                    self._audio_eq_status = "running"
                    self._audio_eq_source = "cava"
                assert process.stdout is not None
                for line in iter(process.stdout.readline, b""):
                    levels = self._parse_audio_eq_line(line)
                    if not levels:
                        continue
                    now = time.time()
                    with self._audio_eq_lock:
                        self._audio_eq_bars = self._shape_audio_eq_levels_locked(levels, now)
                        self._audio_eq_updated_at = now
                        self._audio_eq_status = "running"
                        self._audio_eq_source = "cava"
                return_code = process.wait(timeout=1.0)
                if return_code:
                    with self._audio_eq_lock:
                        self._audio_eq_status = f"error:cava-exit-{return_code}"
                        self._audio_eq_source = "cava"
            except Exception as exc:
                with self._audio_eq_lock:
                    self._audio_eq_status = f"error:{type(exc).__name__}"
                    self._audio_eq_source = "cava"
            finally:
                process = self._audio_eq_process
                self._audio_eq_process = None
                if process is not None and process.poll() is None:
                    try:
                        process.terminate()
                    except Exception:
                        pass
            time.sleep(5.0)

    def read_audio_eq_stats(self) -> dict[str, str]:
        now = time.time()
        with self._audio_eq_lock:
            bars = list(self._audio_eq_bars)
            raw_bars = list(self._audio_eq_raw_bars)
            updated_at = float(self._audio_eq_updated_at or 0.0)
            status = str(self._audio_eq_status or "unavailable")
            source = str(self._audio_eq_source or "none")
        age_ms = int((now - updated_at) * 1000) if updated_at > 0 else -1
        if status == "running" and age_ms > 1800:
            status = "stale"
        return {
            "audio_eq_bars": json.dumps(bars, separators=(",", ":")),
            "audio_eq_raw_bars": json.dumps(raw_bars, separators=(",", ":")),
            "audio_eq_source": source,
            "audio_eq_status": status,
            "audio_eq_age_ms": "N/A" if age_ms < 0 else str(age_ms),
        }

    def audio_eq_status(self) -> dict[str, object]:
        stats = self.read_audio_eq_stats()
        bars: list[float] = []
        raw_bars: list[float] = []
        try:
            parsed = json.loads(stats.get("audio_eq_bars", "[]"))
            if isinstance(parsed, list):
                for value in parsed:
                    try:
                        bars.append(max(0.0, min(1.0, float(value))))
                    except (TypeError, ValueError):
                        continue
        except Exception:
            bars = []
        try:
            parsed_raw = json.loads(stats.get("audio_eq_raw_bars", "[]"))
            if isinstance(parsed_raw, list):
                for value in parsed_raw:
                    try:
                        raw_bars.append(max(0.0, min(1.0, float(value))))
                    except (TypeError, ValueError):
                        continue
        except Exception:
            raw_bars = []
        return {
            "status": stats.get("audio_eq_status", "unavailable"),
            "source": stats.get("audio_eq_source", "none"),
            "age_ms": stats.get("audio_eq_age_ms", "N/A"),
            "bar_count": len(bars),
            "peak": round(max(bars), 3) if bars else 0.0,
            "raw_peak": round(max(raw_bars), 3) if raw_bars else 0.0,
            "cava_available": bool(self._audio_eq_cava_bin),
            "input_method": self._audio_eq_input_method,
            "config_dir": self._audio_eq_runtime_dir,
        }

    @staticmethod
    def _parse_weather_refresh_s(value: object) -> float:
        try:
            return max(300.0, float(value or 900))
        except (TypeError, ValueError):
            return 900.0

    def weather_config(self) -> dict[str, object]:
        return {
            "lat": self._weather_lat,
            "lon": self._weather_lon,
            "location": self._weather_location,
            "refresh_s": self._weather_refresh_s,
            "enabled": self._weather_lat is not None and self._weather_lon is not None,
        }

    def weather_status(self) -> dict[str, object]:
        cached = self._read_weather_cache()
        cached_at = 0.0
        if cached:
            try:
                cached_at = float(cached.get("fetched_at", 0.0) or 0.0)
            except (TypeError, ValueError):
                cached_at = 0.0
        now = time.time()
        snapshot = self._last_weather_snapshot or self._default_weather_snapshot()
        return {
            **self.weather_config(),
            "cache_path": self._weather_cache_path,
            "cache_exists": bool(cached),
            "cache_age_s": round(now - cached_at, 1) if cached_at > 0 else None,
            "last_update_age_s": round(now - self._last_weather_at, 1) if self._last_weather_at > 0 else None,
            "last_source": self._last_weather_source,
            "last_error": self._last_weather_error,
            "condition": snapshot.get("weather_condition", "N/A"),
            "temperature": snapshot.get("weather_temp_c", "N/A"),
            "location_label": snapshot.get("weather_location", self._weather_location or "N/A"),
        }

    def set_weather_config(
        self,
        *,
        lat: float | None = None,
        lon: float | None = None,
        location: str | None = None,
        refresh_s: float | None = None,
    ) -> dict[str, object]:
        self._weather_lat = lat
        self._weather_lon = lon
        if location is not None:
            self._weather_location = str(location).strip()
        if refresh_s is not None:
            self._weather_refresh_s = self._parse_weather_refresh_s(refresh_s)
        self._last_weather_at = 0.0
        self._last_weather_snapshot = self._default_weather_snapshot()
        self._last_weather_error = ""
        self._last_weather_source = "config"
        return self.weather_config()

    def _load_weather_icon_map(self) -> dict[str, object]:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "weather", "open_meteo_icon_map.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _weather_float(value: str) -> float | None:
        text = str(value or "").strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _format_weather_number(value: object, suffix: str = "", digits: int = 0) -> str:
        if value is None:
            return "N/A"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if digits <= 0:
            text = f"{number:.0f}"
        else:
            text = f"{number:.{digits}f}"
        return f"{text}{suffix}"

    @staticmethod
    def _default_weather_snapshot() -> dict[str, str]:
        out = {
            "weather_location": "N/A",
            "weather_temp_c": "N/A",
            "weather_feels_like_c": "N/A",
            "weather_humidity_percent": "N/A",
            "weather_wind_kph": "N/A",
            "weather_precip_mm": "N/A",
            "weather_cloud_percent": "N/A",
            "weather_code": "N/A",
            "weather_condition": "N/A",
            "weather_icon": "not-available.svg",
            "weather_icon_path": "",
            "weather_is_day": "N/A",
            "weather_daily_json": "[]",
        }
        for idx in range(7):
            out.update(
                {
                    f"weather_day_{idx}_label": "N/A",
                    f"weather_day_{idx}_condition": "N/A",
                    f"weather_day_{idx}_icon": "not-available.svg",
                    f"weather_day_{idx}_icon_path": "",
                    f"weather_day_{idx}_temp_min_c": "N/A",
                    f"weather_day_{idx}_temp_max_c": "N/A",
                    f"weather_day_{idx}_precip_mm": "N/A",
                }
            )
        return out

    def _weather_icon_for_code(self, code: object, is_day: bool = True) -> tuple[str, str]:
        fallback = self._weather_icon_map.get("fallback", {}) if isinstance(self._weather_icon_map, dict) else {}
        fallback_name = "not-available.svg"
        if isinstance(fallback, dict):
            fallback_name = str(fallback.get("day" if is_day else "night") or fallback.get("day") or fallback_name)
        codes = self._weather_icon_map.get("codes", {}) if isinstance(self._weather_icon_map, dict) else {}
        entry = codes.get(str(code)) if isinstance(codes, dict) else None
        if not isinstance(entry, dict):
            return "N/A", fallback_name
        label = str(entry.get("label") or "N/A")
        icon_name = str(entry.get("day" if is_day else "night") or entry.get("day") or fallback_name)
        return label, icon_name

    @staticmethod
    def _weekday_label(date_text: str) -> str:
        try:
            parsed = time.strptime(date_text, "%Y-%m-%d")
            return time.strftime("%a", parsed)
        except Exception:
            return str(date_text or "N/A")

    def _weather_icon_path(self, icon_name: str) -> str:
        name = os.path.basename(str(icon_name or ""))
        if not name:
            return ""
        root = os.path.dirname(os.path.abspath(__file__))
        preferred_dir = "png" if name.lower().endswith(".png") else "fill"
        candidates = [
            os.path.join(root, "assets", "weather", "icons", "meteocons", preferred_dir, name),
            os.path.join(root, "assets", "weather", "icons", "meteocons", "png", os.path.splitext(name)[0] + ".png"),
            os.path.join(root, "assets", "weather", "icons", "meteocons", "fill", os.path.splitext(name)[0] + ".svg"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return ""

    def _read_weather_cache(self) -> dict[str, object] | None:
        try:
            if not os.path.exists(self._weather_cache_path):
                return None
            with open(self._weather_cache_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _write_weather_cache(self, data: dict[str, object]) -> None:
        try:
            os.makedirs(self._weather_runtime_dir, exist_ok=True)
            tmp_path = f"{self._weather_cache_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False)
            os.replace(tmp_path, self._weather_cache_path)
        except Exception:
            pass

    def _normalize_weather_response(self, data: dict[str, object], location: str) -> dict[str, str]:
        out = self._default_weather_snapshot()
        out["weather_location"] = location or "N/A"

        current = data.get("current", {})
        if not isinstance(current, dict):
            current = {}
        code = current.get("weather_code")
        is_day = str(current.get("is_day", "1")) != "0"
        condition, icon_name = self._weather_icon_for_code(code, is_day=is_day)
        out.update(
            {
                "weather_temp_c": self._format_weather_number(current.get("temperature_2m"), "°C"),
                "weather_feels_like_c": self._format_weather_number(current.get("apparent_temperature"), "°C"),
                "weather_humidity_percent": self._format_weather_number(current.get("relative_humidity_2m"), "%"),
                "weather_wind_kph": self._format_weather_number(current.get("wind_speed_10m"), " km/h"),
                "weather_precip_mm": self._format_weather_number(current.get("precipitation"), " mm", digits=1),
                "weather_cloud_percent": self._format_weather_number(current.get("cloud_cover"), "%"),
                "weather_code": "N/A" if code is None else str(code),
                "weather_condition": condition,
                "weather_icon": icon_name,
                "weather_icon_path": self._weather_icon_path(icon_name),
                "weather_is_day": "1" if is_day else "0",
            }
        )

        daily = data.get("daily", {})
        forecast: list[dict[str, object]] = []
        if isinstance(daily, dict):
            dates = daily.get("time") if isinstance(daily.get("time"), list) else []
            codes = daily.get("weather_code") if isinstance(daily.get("weather_code"), list) else []
            mins = daily.get("temperature_2m_min") if isinstance(daily.get("temperature_2m_min"), list) else []
            maxs = daily.get("temperature_2m_max") if isinstance(daily.get("temperature_2m_max"), list) else []
            precips = daily.get("precipitation_sum") if isinstance(daily.get("precipitation_sum"), list) else []
            winds = daily.get("wind_speed_10m_max") if isinstance(daily.get("wind_speed_10m_max"), list) else []
            for idx in range(min(7, len(dates))):
                day_code = codes[idx] if idx < len(codes) else None
                day_condition, day_icon = self._weather_icon_for_code(day_code, is_day=True)
                row = {
                    "date": str(dates[idx]),
                    "weekday": self._weekday_label(str(dates[idx])),
                    "code": day_code,
                    "condition": day_condition,
                    "icon": day_icon,
                    "temp_min_c": mins[idx] if idx < len(mins) else None,
                    "temp_max_c": maxs[idx] if idx < len(maxs) else None,
                    "precip_mm": precips[idx] if idx < len(precips) else None,
                    "wind_kph": winds[idx] if idx < len(winds) else None,
                }
                forecast.append(row)
                out.update(
                    {
                        f"weather_day_{idx}_label": str(row["weekday"]),
                        f"weather_day_{idx}_condition": str(row["condition"]),
                        f"weather_day_{idx}_icon": day_icon,
                        f"weather_day_{idx}_icon_path": self._weather_icon_path(day_icon),
                        f"weather_day_{idx}_temp_min_c": self._format_weather_number(row["temp_min_c"], "°C"),
                        f"weather_day_{idx}_temp_max_c": self._format_weather_number(row["temp_max_c"], "°C"),
                        f"weather_day_{idx}_precip_mm": self._format_weather_number(row["precip_mm"], " mm", digits=1),
                    }
                )
        out["weather_daily_json"] = json.dumps(forecast, ensure_ascii=False, separators=(",", ":"))
        return out

    def _cached_weather_snapshot(self) -> tuple[dict[str, str] | None, float]:
        cached = self._read_weather_cache()
        if cached and isinstance(cached.get("normalized"), dict):
            try:
                cached_at = float(cached.get("fetched_at", 0.0) or 0.0)
            except (TypeError, ValueError):
                cached_at = 0.0
            return {str(k): str(v) for k, v in cached["normalized"].items()}, cached_at  # type: ignore[index]
        return None, 0.0

    def _refresh_weather_stats_sync(
        self,
        *,
        now: float | None = None,
        cached_snapshot: dict[str, str] | None = None,
    ) -> dict[str, str]:
        lat = self._weather_lat
        lon = self._weather_lon
        if lat is None or lon is None:
            self._last_weather_source = "disabled"
            return self._default_weather_snapshot()

        now = time.time() if now is None else now
        params = {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,is_day,precipitation,weather_code,cloud_cover,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
            "forecast_days": "7",
            "timezone": "auto",
            "wind_speed_unit": "kmh",
        }
        location = self._weather_location or f"{lat:.3f},{lon:.3f}"
        url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)
        try:
            req = Request(url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
            with urlopen(req, timeout=2.5) as response:
                payload = response.read()
            data = json.loads(payload.decode("utf-8"))
            if not isinstance(data, dict):
                raise RuntimeError("invalid-weather-payload")
            normalized = self._normalize_weather_response(data, location)
            self._last_weather_snapshot = normalized
            self._last_weather_at = now
            self._last_weather_error = ""
            self._last_weather_source = "open-meteo"
            self._write_weather_cache({"fetched_at": now, "provider": "open-meteo", "raw": data, "normalized": normalized})
            return dict(normalized)
        except Exception as exc:
            self._last_weather_error = str(exc)
            if cached_snapshot:
                self._last_weather_snapshot = dict(cached_snapshot)
                self._last_weather_at = now
                self._last_weather_source = "cache-fallback"
                return dict(self._last_weather_snapshot)
            self._last_weather_source = "error"
            return self._default_weather_snapshot()

    def _start_weather_refresh_thread(self, cached_snapshot: dict[str, str] | None = None) -> None:
        with self._weather_lock:
            if self._weather_refresh_inflight:
                return
            self._weather_refresh_inflight = True

        def _worker() -> None:
            try:
                self._refresh_weather_stats_sync(cached_snapshot=cached_snapshot)
            finally:
                with self._weather_lock:
                    self._weather_refresh_inflight = False

        threading.Thread(target=_worker, name="trofeo-weather-refresh", daemon=True).start()

    def read_weather_stats(self, *, blocking: bool = False, force: bool = False) -> dict[str, str]:
        lat = self._weather_lat
        lon = self._weather_lon
        if lat is None or lon is None:
            self._last_weather_source = "disabled"
            return self._default_weather_snapshot()

        now = time.time()
        refresh_s = self._weather_refresh_s
        if not force and now - self._last_weather_at < refresh_s:
            self._last_weather_source = "memory"
            return dict(self._last_weather_snapshot)

        cached_snapshot, cached_at = self._cached_weather_snapshot()
        if not force and cached_snapshot and now - cached_at < refresh_s:
            self._last_weather_snapshot = dict(cached_snapshot)
            self._last_weather_at = now
            self._last_weather_error = ""
            self._last_weather_source = "cache"
            return dict(self._last_weather_snapshot)

        if blocking or force:
            return self._refresh_weather_stats_sync(now=now, cached_snapshot=cached_snapshot)

        fallback = dict(cached_snapshot or self._last_weather_snapshot or self._default_weather_snapshot())
        self._start_weather_refresh_thread(cached_snapshot=cached_snapshot)
        if cached_snapshot:
            self._last_weather_snapshot = dict(cached_snapshot)
            self._last_weather_source = "stale-cache-refreshing"
        else:
            self._last_weather_source = "refreshing"
        return fallback

    @staticmethod
    def _default_media_snapshot() -> dict[str, str]:
        return {
            "media_title": "N/A",
            "media_artist": "N/A",
            "media_album": "N/A",
            "media_app": "N/A",
            "media_state": "stopped",
            "media_cover_path": "",
            "media_video_frame_path": "",
            "media_source_url": "",
        }

    @staticmethod
    def _media_priority(player_name: str, state: str, title: str) -> tuple[int, int, int]:
        p = player_name.lower()
        state_score = 3 if state == "playing" else (2 if state == "paused" else 1)
        source_score = 1
        if "spotify" in p:
            source_score = 5
        elif any(x in p for x in ("chrom", "brave", "edge", "firefox", "opera", "vivaldi")):
            source_score = 4
        elif "youtube" in p or "ytmusic" in p:
            source_score = 4
        title_score = 1 if title else 0
        return state_score, source_score, title_score

    @staticmethod
    def _cleanup_media_artist(value: str) -> str:
        text = value.strip()
        if not text:
            return ""
        if text.startswith("[") and text.endswith("]"):
            text = text.strip("[]")
            text = re.sub(r"[\"']", "", text)
        text = re.sub(r"\s*,\s*", ", ", text)
        return text.strip()

    @staticmethod
    def _is_browser_player(player_name: str) -> bool:
        player = player_name.strip().lower()
        return any(token in player for token in ("chrom", "brave", "edge", "firefox", "opera", "vivaldi"))

    def is_browser_media_player(self, player_name: str) -> bool:
        return self._is_browser_player(player_name)

    @staticmethod
    def _normalize_media_cover_path(raw_path: str) -> str:
        art_url = str(raw_path).strip()
        if not art_url:
            return ""
        parsed = urlparse(art_url)
        if parsed.scheme == "file":
            cover_path = unquote(parsed.path)
            if cover_path and os.path.exists(cover_path):
                return cover_path
            return ""
        if os.path.exists(art_url):
            return art_url
        return ""

    def _copy_media_cover_to_runtime(self, cover_path: str, stable_key: str = "") -> str:
        os.makedirs(self._media_cover_runtime_dir, exist_ok=True)
        stat = os.stat(cover_path)
        source_key = hashlib.sha1(
            f"{os.path.abspath(cover_path)}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
        ).hexdigest()
        runtime_key = stable_key.strip() or source_key
        suffix = os.path.splitext(cover_path)[1].lower() or ".img"
        out_path = os.path.join(self._media_cover_runtime_dir, f"{runtime_key}{suffix}")
        cached = self._media_cover_cache.get(runtime_key, "") or self._media_cover_cache.get(source_key, "")
        if cached and os.path.exists(cached):
            return cached
        if not os.path.exists(out_path):
            shutil.copyfile(cover_path, out_path)
        self._media_cover_cache[runtime_key] = out_path
        self._media_cover_cache[source_key] = out_path
        return out_path

    def _cached_cover_for_key(self, cache_key: str) -> str:
        cached = self._media_cover_cache.get(cache_key, "")
        if cached and os.path.exists(cached):
            return cached
        try:
            if not os.path.isdir(self._media_cover_runtime_dir):
                return ""
            prefix = f"{cache_key}."
            for name in os.listdir(self._media_cover_runtime_dir):
                if not name.startswith(prefix):
                    continue
                candidate = os.path.join(self._media_cover_runtime_dir, name)
                if os.path.isfile(candidate):
                    self._media_cover_cache[cache_key] = candidate
                    return candidate
        except Exception:
            return ""
        return ""

    @staticmethod
    def _cover_lookup_key(player_name: str, title: str, artist: str, album: str) -> str:
        raw = "\n".join(part.strip().lower() for part in (player_name, title, artist, album))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _cover_lookup_score(result: dict[str, object], title: str, artist: str, album: str) -> int:
        def _norm(value: object) -> str:
            return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

        title_q = _norm(title)
        artist_q = _norm(artist)
        album_q = _norm(album)
        title_r = _norm(result.get("trackName", ""))
        artist_r = _norm(result.get("artistName", ""))
        album_r = _norm(result.get("collectionName", ""))

        score = 0
        if title_q:
            if title_q == title_r:
                score += 8
            elif title_q in title_r or title_r in title_q:
                score += 5
        if artist_q:
            if artist_q == artist_r:
                score += 6
            elif artist_q in artist_r or artist_r in artist_q:
                score += 4
        if album_q:
            if album_q == album_r:
                score += 3
            elif album_q in album_r or album_r in album_q:
                score += 2
        return score

    def _download_cover_bytes(self, image_url: str, cache_key: str) -> str:
        req = Request(image_url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
        with urlopen(req, timeout=2.5) as response:
            payload = response.read()
            content_type = response.headers.get_content_type()
        if not payload:
            raise RuntimeError("empty-cover-payload")
        os.makedirs(self._media_cover_runtime_dir, exist_ok=True)
        suffix = mimetypes.guess_extension(content_type or "") or os.path.splitext(urlparse(image_url).path)[1].lower() or ".img"
        if suffix == ".jpe":
            suffix = ".jpg"
        out_path = os.path.join(self._media_cover_runtime_dir, f"{cache_key}{suffix}")
        tmp_path = f"{out_path}.tmp"
        with open(tmp_path, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, out_path)
        self._media_cover_cache[cache_key] = out_path
        self._media_cover_failures.pop(cache_key, None)
        return out_path

    def _rate_limit_musicbrainz(self) -> None:
        with self._public_api_lock:
            now = time.time()
            wait_s = 1.05 - (now - self._musicbrainz_last_request_at)
            if wait_s > 0:
                time.sleep(wait_s)
            self._musicbrainz_last_request_at = time.time()

    def _resolve_musicbrainz_cover_path(self, cache_key: str, title: str, artist: str, album: str) -> str:
        query_parts = [part.strip() for part in (artist, album or title) if part and part.strip() and part.strip() != "N/A"]
        if len(query_parts) < 2:
            return ""

        mb_query = []
        if artist and artist != "N/A":
            mb_query.append(f'artist:"{artist}"')
        if album and album != "N/A":
            mb_query.append(f'release:"{album}"')
        elif title and title != "N/A":
            mb_query.append(f'release:"{title}"')
        if not mb_query:
            return ""

        search_url = "https://musicbrainz.org/ws/2/release/?" + urlencode(
            {
                "query": " AND ".join(mb_query),
                "fmt": "json",
                "limit": "5",
            }
        )

        try:
            self._rate_limit_musicbrainz()
            req = Request(search_url, headers={"User-Agent": "OpenTrofeoLCD/1.0 (media-cover-fallback)"})
            with urlopen(req, timeout=2.5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            return ""

        releases = payload.get("releases", [])
        if not isinstance(releases, list):
            return ""

        best_id = ""
        best_score = -1
        for release in releases:
            if not isinstance(release, dict):
                continue
            artist_credit = release.get("artist-credit", [])
            if isinstance(artist_credit, list):
                artist_name = " ".join(
                    str(item.get("name", ""))
                    for item in artist_credit
                    if isinstance(item, dict)
                ).strip()
            else:
                artist_name = ""
            candidate = {
                "trackName": title,
                "artistName": artist_name,
                "collectionName": release.get("title", ""),
            }
            score = self._cover_lookup_score(candidate, title or album, artist, album or title)
            release_id = str(release.get("id", "")).strip()
            if release_id and score > best_score:
                best_score = score
                best_id = release_id

        if not best_id or best_score <= 0:
            return ""

        image_url = f"https://coverartarchive.org/release/{best_id}/front-500"
        try:
            self._rate_limit_musicbrainz()
            return self._download_cover_bytes(image_url, cache_key)
        except Exception:
            return ""

    def _resolve_deezer_cover_path(self, cache_key: str, title: str, artist: str, album: str) -> str:
        queries = []
        artist_clean = artist.strip()
        title_clean = title.strip()
        album_clean = album.strip()
        if artist_clean and title_clean and artist_clean != "N/A" and title_clean != "N/A":
            queries.append(f'artist:"{artist_clean}" track:"{title_clean}"')
        plain_parts = [part for part in (artist_clean, title_clean, album_clean) if part and part != "N/A"]
        if plain_parts:
            queries.append(" ".join(plain_parts))

        for query in queries:
            search_url = "https://api.deezer.com/search/track?" + urlencode({"q": query})
            try:
                req = Request(search_url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
                with urlopen(req, timeout=2.5) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except Exception:
                continue

            results = payload.get("data", [])
            if not isinstance(results, list):
                continue

            best_url = ""
            best_score = -1
            for result in results:
                if not isinstance(result, dict):
                    continue
                artist_obj = result.get("artist", {})
                album_obj = result.get("album", {})
                candidate = {
                    "trackName": result.get("title", ""),
                    "artistName": artist_obj.get("name", "") if isinstance(artist_obj, dict) else "",
                    "collectionName": album_obj.get("title", "") if isinstance(album_obj, dict) else "",
                }
                score = self._cover_lookup_score(candidate, title, artist, album)
                if score <= 0 or not isinstance(album_obj, dict):
                    continue
                image_url = str(
                    album_obj.get("cover_xl")
                    or album_obj.get("cover_big")
                    or album_obj.get("cover_medium")
                    or album_obj.get("cover")
                    or ""
                ).strip()
                if image_url and score > best_score:
                    best_score = score
                    best_url = image_url

            if best_url:
                try:
                    return self._download_cover_bytes(best_url, cache_key)
                except Exception:
                    continue
        return ""

    def _resolve_browser_cover_path(self, player_name: str, title: str, artist: str, album: str) -> str:
        if not self._is_browser_player(player_name):
            return ""

        query_parts = [part.strip() for part in (artist, title, album) if part and part.strip() and part.strip() != "N/A"]
        if not query_parts:
            return ""

        cache_key = self._cover_lookup_key(player_name, title, artist, album)
        cached = self._cached_cover_for_key(cache_key)
        if cached:
            return cached

        last_failure = float(self._media_cover_failures.get(cache_key, 0.0))
        if last_failure and (time.time() - last_failure) < 1800.0:
            return ""

        itunes_search_url = "https://itunes.apple.com/search?" + urlencode(
            {
                "term": " ".join(query_parts),
                "media": "music",
                "entity": "song",
                "limit": "5",
            }
        )
        try:
            req = Request(itunes_search_url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
            with urlopen(req, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            payload = {}

        results = payload.get("results", [])
        if isinstance(results, list):
            best_url = ""
            best_score = -1
            for result in results:
                if not isinstance(result, dict):
                    continue
                art_url = str(result.get("artworkUrl100") or result.get("artworkUrl60") or "").strip()
                if not art_url:
                    continue
                score = self._cover_lookup_score(result, title, artist, album)
                if score > best_score:
                    best_score = score
                    best_url = art_url

            if best_url and best_score > 0:
                best_url = re.sub(r"/\d+x\d+bb\.", "/600x600bb.", best_url)
                try:
                    return self._download_cover_bytes(best_url, cache_key)
                except Exception:
                    pass

        musicbrainz_cover = self._resolve_musicbrainz_cover_path(cache_key, title, artist, album)
        if musicbrainz_cover:
            return musicbrainz_cover

        deezer_cover = self._resolve_deezer_cover_path(cache_key, title, artist, album)
        if deezer_cover:
            return deezer_cover

        self._media_cover_failures[cache_key] = time.time()
        return ""

    def resolve_media_cover_path(
        self,
        raw_path: str,
        *,
        player_name: str = "",
        title: str = "",
        artist: str = "",
        album: str = "",
    ) -> str:
        cover_path = self._normalize_media_cover_path(raw_path)
        if cover_path:
            try:
                stable_key = ""
                if any(part and part != "N/A" for part in (title, artist, album)):
                    stable_key = self._cover_lookup_key(player_name, title, artist, album)
                return self._copy_media_cover_to_runtime(cover_path, stable_key=stable_key)
            except Exception:
                return cover_path
        return self._resolve_browser_cover_path(player_name, title, artist, album)

    @staticmethod
    def _normalize_media_source_path(raw_url: str) -> str:
        media_url = str(raw_url).strip()
        if not media_url:
            return ""
        parsed = urlparse(media_url)
        if parsed.scheme == "file":
            media_path = unquote(parsed.path)
            if media_path and os.path.exists(media_path):
                return media_path
            return ""
        if parsed.scheme:
            return ""
        if os.path.exists(media_url):
            return media_url
        return ""

    @staticmethod
    def _is_local_video_path(path: str) -> bool:
        if not path:
            return False
        ext = os.path.splitext(path)[1].lower()
        return ext in {
            ".mp4",
            ".m4v",
            ".mkv",
            ".webm",
            ".avi",
            ".mov",
            ".mpg",
            ".mpeg",
            ".wmv",
            ".flv",
            ".ts",
            ".m2ts",
        }

    def _media_frame_cache_key(self, media_path: str) -> str:
        try:
            stat = os.stat(media_path)
            raw = f"{os.path.abspath(media_path)}:{stat.st_mtime_ns}:{stat.st_size}"
        except Exception:
            raw = os.path.abspath(media_path)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _extract_media_video_frame(self, media_path: str, cache_key: str) -> None:
        try:
            os.makedirs(self._media_frame_runtime_dir, exist_ok=True)
            out_path = os.path.join(self._media_frame_runtime_dir, f"{cache_key}.jpg")
            tmp_path = os.path.join(self._media_frame_runtime_dir, f"{cache_key}.tmp.jpg")
            cmd = [
                str(self._ffmpeg_bin),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                "00:00:01",
                "-i",
                media_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=960:-2:force_original_aspect_ratio=decrease",
                tmp_path,
            ]
            proc = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3.0,
                check=False,
            )
            if proc.returncode == 0 and os.path.exists(tmp_path):
                os.replace(tmp_path, out_path)
                with self._media_frame_lock:
                    self._media_frame_cache[cache_key] = out_path
                    self._media_frame_failures.pop(cache_key, None)
            elif os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        finally:
            with self._media_frame_lock:
                if cache_key not in self._media_frame_cache:
                    self._media_frame_failures[cache_key] = time.time()
                self._media_frame_jobs.discard(cache_key)

    def resolve_media_video_frame_path(self, raw_url: str, fallback_cover_path: str = "") -> str:
        fallback = str(fallback_cover_path).strip()
        media_path = self._normalize_media_source_path(raw_url)
        if not media_path or not self._is_local_video_path(media_path) or not self._ffmpeg_bin:
            return fallback
        cache_key = self._media_frame_cache_key(media_path)
        with self._media_frame_lock:
            cached = self._media_frame_cache.get(cache_key, "")
            if cached and os.path.exists(cached):
                return cached
            last_failure = float(self._media_frame_failures.get(cache_key, 0.0))
            if last_failure and (time.time() - last_failure) < 30.0:
                return fallback
            if cache_key not in self._media_frame_jobs:
                self._media_frame_jobs.add(cache_key)
                threading.Thread(
                    target=self._extract_media_video_frame,
                    args=(media_path, cache_key),
                    daemon=True,
                ).start()
        return fallback

    def should_disable_browser_video_frame(self, player_name: str, raw_url: str) -> bool:
        if not self._is_browser_player(player_name):
            return False
        media_path = self._normalize_media_source_path(raw_url)
        return not media_path or not self._is_local_video_path(media_path)

    def _detect_gpu_type(self) -> str | None:
        if self._local_or_host_cmd("nvidia-smi"):
            return "nvidia"
        for i in range(4):
            if os.path.exists(f"/sys/class/drm/card{i}/device/hwmon"):
                return f"amd{i}"
        return None

    def read_local_ip(self) -> str:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def read_disk_usage(self) -> tuple[int, int, int] | None:
        try:
            st = os.statvfs("/")
            total = (st.f_blocks * st.f_frsize) // (1024 * 1024 * 1024)
            free = (st.f_bfree * st.f_frsize) // (1024 * 1024 * 1024)
            used = total - free
            percent = int((used * 100) // total) if total > 0 else 0
            return used, total, percent
        except Exception:
            return None

    def read_net_speeds(self) -> tuple[float, float]:
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()
            total_recv = 0
            total_sent = 0
            for line in lines[2:]:
                parts = line.split()
                if len(parts) > 9:
                    total_recv += int(parts[1])
                    total_sent += int(parts[9])
            now = time.time()
            prev_time, prev_recv, prev_sent = self._net_io_snapshot
            self._net_io_snapshot = (now, total_recv, total_sent)
            dt = now - prev_time
            if dt <= 0: return 0.0, 0.0
            return (total_recv - prev_recv) / 1024.0 / dt, (total_sent - prev_sent) / 1024.0 / dt
        except Exception:
            return 0.0, 0.0

    def read_volume_stats(self) -> dict[str, str]:
        now = time.time()
        if (now - self._last_volume_at) < 0.4:
            return dict(self._last_volume_snapshot)

        out = {"volume_percent": "N/A", "volume_state": "N/A"}
        try:
            wpctl = self._local_or_host_cmd("wpctl")
            if wpctl:
                payload = subprocess.check_output(
                    wpctl + ["get-volume", "@DEFAULT_AUDIO_SINK@"],
                    encoding="utf-8",
                    stderr=subprocess.DEVNULL,
                    timeout=0.35,
                ).strip()
                match = re.search(r"Volume:\s*([0-9]*\.?[0-9]+)", payload)
                if match:
                    out["volume_percent"] = f"{int(round(float(match.group(1)) * 100.0))}%"
                out["volume_state"] = "muted" if "MUTED" in payload.upper() else "active"
            else:
                pactl = self._local_or_host_cmd("pactl")
                if pactl:
                    vol_payload = subprocess.check_output(
                        pactl + ["get-sink-volume", "@DEFAULT_SINK@"],
                        encoding="utf-8",
                        stderr=subprocess.DEVNULL,
                        timeout=0.45,
                    ).strip()
                    vol_match = re.search(r"(\d+)%", vol_payload)
                    if vol_match:
                        out["volume_percent"] = f"{int(vol_match.group(1))}%"
                    mute_payload = subprocess.check_output(
                        pactl + ["get-sink-mute", "@DEFAULT_SINK@"],
                        encoding="utf-8",
                        stderr=subprocess.DEVNULL,
                        timeout=0.35,
                    ).strip()
                    out["volume_state"] = "muted" if "yes" in mute_payload.lower() else "active"
                else:
                    pamixer = self._local_or_host_cmd("pamixer")
                    if pamixer:
                        volume_value = subprocess.check_output(
                            pamixer + ["--get-volume"],
                            encoding="utf-8",
                            stderr=subprocess.DEVNULL,
                            timeout=0.35,
                        ).strip()
                        if volume_value.isdigit():
                            out["volume_percent"] = f"{int(volume_value)}%"
                        mute_value = subprocess.check_output(
                            pamixer + ["--get-mute"],
                            encoding="utf-8",
                            stderr=subprocess.DEVNULL,
                            timeout=0.35,
                        ).strip()
                        out["volume_state"] = "muted" if mute_value.lower() == "true" else "active"
        except Exception:
            pass

        self._last_volume_snapshot = dict(out)
        self._last_volume_at = now
        return out

    def read_gpu_stats(self) -> dict[str, str]:
        stats = {
            "gpu_name": "N/A", "gpu_temp": "N/A", "gpu_load": "N/A",
            "vram_used_mb": "N/A", "vram_total_mb": "N/A", "vram_percent": "N/A"
        }
        if self._gpu_type == "nvidia":
            try:
                nvidia_smi = self._local_or_host_cmd("nvidia-smi")
                if not nvidia_smi:
                    return stats
                cmd = nvidia_smi + ["--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]
                out = subprocess.check_output(cmd, encoding="utf-8").strip().split(", ")
                if len(out) >= 5:
                    stats.update({
                        "gpu_name": out[0], "gpu_temp": f"{out[1]}°C", "gpu_load": f"{out[2]}%",
                        "vram_used_mb": out[3], "vram_total_mb": out[4],
                        "vram_percent": f"{int(float(out[3])*100/float(out[4]))}%"
                    })
            except Exception: pass
        return stats

    def read_cpu_usage_percent(self) -> str:
        current_total, _ = _parse_proc_stat()
        if current_total is None:
            return "N/A"

        prev = self._cpu_snapshot
        self._cpu_snapshot = current_total
        if prev is None:
            return "N/A"

        busy_delta = current_total[0] - prev[0]
        idle_delta = current_total[1] - prev[1]
        total_delta = busy_delta + idle_delta
        if total_delta <= 0:
            return "N/A"
        return f"{(busy_delta * 100.0 / total_delta):.0f}%"

    def read_cpu_core_summary(self) -> tuple[float, float, int] | None:
        _, current_cores = _parse_proc_stat()
        if not current_cores:
            return None

        prev = self._cpu_core_snapshot
        self._cpu_core_snapshot = current_cores
        if prev is None or len(prev) != len(current_cores):
            return None

        usages = []
        for old_pair, new_pair in zip(prev, current_cores):
            busy_delta = new_pair[0] - old_pair[0]
            idle_delta = new_pair[1] - old_pair[1]
            total_delta = busy_delta + idle_delta
            if total_delta > 0:
                usages.append(busy_delta * 100.0 / total_delta)

        if not usages:
            return None

        return sum(usages) / len(usages), max(usages), len(usages)

    def read_load_average(self) -> str:
        try:
            with open("/proc/loadavg", "r", encoding="utf-8") as handle:
                parts = handle.read().split()
            if len(parts) >= 3:
                return f"{parts[0]}/{parts[1]}/{parts[2]}"
        except Exception:
            pass
        return "N/A"

    def read_cpu_freq_ghz(self) -> str:
        try:
            freqs = []
            with open("/proc/cpuinfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith("cpu mhz"):
                        value = float(line.split(":", 1)[1].strip())
                        freqs.append(value)
            if freqs:
                avg_mhz = sum(freqs) / len(freqs)
                return f"{avg_mhz / 1000.0:.2f} GHz"
        except Exception:
            pass
        return "N/A"

    def read_cpu_temperature(self) -> str:
        candidates = []

        try:
            for zone in os.listdir("/sys/class/thermal"):
                if not zone.startswith("thermal_zone"):
                    continue
                base = f"/sys/class/thermal/{zone}"
                temp_path = f"{base}/temp"
                type_path = f"{base}/type"
                if not os.path.exists(temp_path):
                    continue
                try:
                    with open(temp_path, "r", encoding="utf-8") as handle:
                        raw = int(handle.read().strip())
                    celsius = raw / 1000.0 if raw > 1000 else float(raw)
                    if not (10.0 <= celsius <= 120.0):
                        continue
                    label = ""
                    if os.path.exists(type_path):
                        with open(type_path, "r", encoding="utf-8") as handle:
                            label = handle.read().strip().lower()
                    score = 0
                    if any(x in label for x in ("cpu", "x86_pkg_temp", "package", "tctl", "tdie")):
                        score = 2
                    elif label:
                        score = 1
                    candidates.append((score, celsius))
                except Exception:
                    continue
        except Exception:
            pass

        try:
            for hw in os.listdir("/sys/class/hwmon"):
                base = f"/sys/class/hwmon/{hw}"
                for entry in os.listdir(base):
                    if not entry.startswith("temp") or not entry.endswith("_input"):
                        continue
                    temp_path = f"{base}/{entry}"
                    label_path = f"{base}/{entry[:-6]}_label"
                    try:
                        with open(temp_path, "r", encoding="utf-8") as handle:
                            raw = int(handle.read().strip())
                        celsius = raw / 1000.0 if raw > 1000 else float(raw)
                        if not (10.0 <= celsius <= 120.0):
                            continue
                        label = ""
                        if os.path.exists(label_path):
                            with open(label_path, "r", encoding="utf-8") as handle:
                                label = handle.read().strip().lower()
                        score = 0
                        if any(x in label for x in ("cpu", "package", "tctl", "tdie")):
                            score = 3
                        elif label:
                            score = 1
                        candidates.append((score, celsius))
                    except Exception:
                        continue
        except Exception:
            pass

        if not candidates:
            return "N/A"

        best = sorted(candidates, key=lambda x: (x[0], x[1]), reverse=True)[0][1]
        return f"{best:.0f}°C"

    def _read_meminfo(self) -> tuple[int, int, int] | None:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                lines = handle.readlines()
            total_mb = int(lines[0].split()[1]) // 1024
            avail_mb = int(lines[2].split()[1]) // 1024
            used_mb = total_mb - avail_mb
            return used_mb, total_mb, int((used_mb * 100) // total_mb) if total_mb > 0 else 0
        except Exception:
            return None

    def _read_uptime(self) -> tuple[int, int] | None:
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as handle:
                uptime_sec = float(handle.read().split()[0])
            hours = int(uptime_sec // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            return hours, minutes
        except Exception:
            return None

    def _read_media_now_playing(self) -> dict[str, str]:
        out = self._default_media_snapshot()
        playerctl_cmd = self._playerctl_cmd()

        if not playerctl_cmd:
            return self._read_media_now_playing_mpris(out)

        try:
            payload = subprocess.check_output(
                playerctl_cmd
                + [
                    "-a",
                    "metadata",
                    "--format",
                    "{{playerName}}\t{{status}}\t{{xesam:title}}\t{{xesam:artist}}\t{{mpris:artUrl}}\t{{xesam:url}}\t{{xesam:album}}",
                ],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
                timeout=0.6,
            ).strip()
            if payload:
                best = None
                for line in payload.splitlines():
                    parts = line.split("\t")
                    player = parts[0].strip() if len(parts) > 0 else ""
                    state = parts[1].strip().lower() if len(parts) > 1 else "stopped"
                    title = parts[2].strip() if len(parts) > 2 else ""
                    artist = self._cleanup_media_artist(parts[3] if len(parts) > 3 else "")
                    art_url = parts[4].strip() if len(parts) > 4 else ""
                    media_url = parts[5].strip() if len(parts) > 5 else ""
                    album = parts[6].strip() if len(parts) > 6 else ""
                    score = self._media_priority(player, state, title)
                    row = (score, player, state, title, artist, art_url, media_url, album)
                    if best is None or row[0] > best[0]:
                        best = row
                if best is not None:
                    _score, player, state, title, artist, art_url, media_url, album = best
                    out["media_state"] = state or "stopped"
                    if player:
                        out["media_app"] = player
                    if title:
                        out["media_title"] = title
                    if artist:
                        out["media_artist"] = artist
                    if album:
                        out["media_album"] = album
                    if media_url:
                        out["media_source_url"] = media_url
                    out["media_cover_path"] = self.resolve_media_cover_path(
                        art_url,
                        player_name=player,
                        title=title,
                        artist=artist,
                        album=album,
                    )
                    out["media_video_frame_path"] = self.resolve_media_video_frame_path(
                        out.get("media_source_url", ""),
                        out["media_cover_path"],
                    )
                    if title or artist:
                        self._last_media_snapshot = dict(out)
                        self._last_media_at = time.time()
                    return out
        except Exception:
            pass
        try:
            payload = subprocess.check_output(
                playerctl_cmd + ["-a", "status", "--format", "{{playerName}}\t{{status}}"],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
                timeout=0.35,
            )
            best = None
            for line in payload.strip().splitlines():
                parts = line.split("\t")
                player = parts[0].strip() if len(parts) > 0 else ""
                state = parts[1].strip().lower() if len(parts) > 1 else "stopped"
                score = self._media_priority(player, state, "")
                row = (score, player, state)
                if best is None or row[0] > best[0]:
                    best = row
            if best is not None:
                _score, player, state = best
                out["media_state"] = state or "stopped"
                if player:
                    out["media_app"] = player
        except Exception:
            pass
        if out["media_app"] == "N/A" and out["media_title"] == "N/A":
            mpris_out = self._read_media_now_playing_mpris(dict(out))
            if mpris_out.get("media_app") != "N/A" or mpris_out.get("media_title") != "N/A":
                return mpris_out
        if out["media_state"] in {"playing", "paused"} and (time.time() - self._last_media_at) <= 600.0:
            fallback = dict(self._last_media_snapshot)
            if fallback.get("media_title") and fallback["media_title"] != "N/A":
                out["media_title"] = fallback["media_title"]
            if fallback.get("media_artist"):
                out["media_artist"] = fallback["media_artist"]
            if fallback.get("media_cover_path"):
                out["media_cover_path"] = fallback["media_cover_path"]
            if fallback.get("media_video_frame_path"):
                out["media_video_frame_path"] = fallback["media_video_frame_path"]
            if fallback.get("media_source_url"):
                out["media_source_url"] = fallback["media_source_url"]
            if out["media_app"] == "N/A" and fallback.get("media_app"):
                out["media_app"] = fallback["media_app"]
        return out

    @staticmethod
    def _playerctl_cmd() -> list[str] | None:
        return StatsProvider._local_or_host_cmd("playerctl")

    @staticmethod
    def _local_or_host_cmd(binary_name: str) -> list[str] | None:
        binary = shutil.which(binary_name)
        if binary:
            return [binary]
        flatpak_spawn = shutil.which("flatpak-spawn")
        if flatpak_spawn and os.path.exists("/.flatpak-info"):
            return [flatpak_spawn, "--host", binary_name]
        return None

    @staticmethod
    def _gvariant_unquote(token: str) -> str:
        token = token.strip()
        if len(token) >= 2 and token[0] in {"'", '"'} and token[-1] == token[0]:
            try:
                return bytes(token[1:-1], "utf-8").decode("unicode_escape")
            except Exception:
                return token[1:-1]
        return token

    @classmethod
    def _gvariant_first_string(cls, payload: str) -> str:
        match = re.search(r"<('(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")>", payload)
        return cls._gvariant_unquote(match.group(1)) if match else ""

    @classmethod
    def _gvariant_metadata_string(cls, payload: str, key: str) -> str:
        escaped_key = re.escape(key)
        match = re.search(rf"['\"]{escaped_key}['\"]:\s*<('(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")>", payload)
        return cls._gvariant_unquote(match.group(1)) if match else ""

    @classmethod
    def _gvariant_metadata_artist(cls, payload: str) -> str:
        match = re.search(r"['\"]xesam:artist['\"]:\s*<\[(.*?)\]>", payload, flags=re.S)
        if not match:
            return ""
        artists = re.findall(r"'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"", match.group(1))
        return cls._cleanup_media_artist(", ".join(cls._gvariant_unquote(item) for item in artists))

    def _gdbus_call(self, args: list[str], *, timeout: float = 0.45) -> str:
        gdbus = shutil.which("gdbus")
        if not gdbus:
            return ""
        try:
            return subprocess.check_output(
                [gdbus, "call", "--session", *args],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            ).strip()
        except Exception:
            return ""

    def _read_media_now_playing_mpris(self, out: dict[str, str]) -> dict[str, str]:
        names_payload = self._gdbus_call(
            [
                "--dest",
                "org.freedesktop.DBus",
                "--object-path",
                "/org/freedesktop/DBus",
                "--method",
                "org.freedesktop.DBus.ListNames",
            ],
            timeout=0.35,
        )
        players = sorted(set(re.findall(r"org\.mpris\.MediaPlayer2\.[A-Za-z0-9_.-]+", names_payload)))
        if not players:
            return out

        best = None
        for player in players:
            state_payload = self._gdbus_call(
                [
                    "--dest",
                    player,
                    "--object-path",
                    "/org/mpris/MediaPlayer2",
                    "--method",
                    "org.freedesktop.DBus.Properties.Get",
                    "org.mpris.MediaPlayer2.Player",
                    "PlaybackStatus",
                ],
                timeout=0.3,
            )
            metadata_payload = self._gdbus_call(
                [
                    "--dest",
                    player,
                    "--object-path",
                    "/org/mpris/MediaPlayer2",
                    "--method",
                    "org.freedesktop.DBus.Properties.Get",
                    "org.mpris.MediaPlayer2.Player",
                    "Metadata",
                ],
                timeout=0.45,
            )
            state = self._gvariant_first_string(state_payload).strip().lower() or "stopped"
            player_name = player.rsplit(".", 1)[-1].split(".")[0]
            title = self._gvariant_metadata_string(metadata_payload, "xesam:title")
            artist = self._gvariant_metadata_artist(metadata_payload)
            art_url = self._gvariant_metadata_string(metadata_payload, "mpris:artUrl")
            media_url = self._gvariant_metadata_string(metadata_payload, "xesam:url")
            album = self._gvariant_metadata_string(metadata_payload, "xesam:album")
            score = self._media_priority(player_name, state, title)
            row = (score, player_name, state, title, artist, art_url, media_url, album)
            if best is None or row[0] > best[0]:
                best = row

        if best is None:
            return out
        _score, player, state, title, artist, art_url, media_url, album = best
        out["media_state"] = state or "stopped"
        if player:
            out["media_app"] = player
        if title:
            out["media_title"] = title
        if artist:
            out["media_artist"] = artist
        if album:
            out["media_album"] = album
        if media_url:
            out["media_source_url"] = media_url
        out["media_cover_path"] = self.resolve_media_cover_path(
            art_url,
            player_name=player,
            title=title,
            artist=artist,
            album=album,
        )
        out["media_video_frame_path"] = self.resolve_media_video_frame_path(
            out.get("media_source_url", ""),
            out["media_cover_path"],
        )
        if title or artist:
            self._last_media_snapshot = dict(out)
            self._last_media_at = time.time()
        return out

    def snapshot(self) -> StatsSnapshot:
        now = time.localtime()
        core_summary = self.read_cpu_core_summary()
        mem = self._read_meminfo()
        uptime = self._read_uptime()
        disk = self.read_disk_usage()
        dl_speed, ul_speed = self.read_net_speeds()
        volume = self.read_volume_stats()
        audio_eq = self.read_audio_eq_stats()
        gpu = self.read_gpu_stats()
        media = self._read_media_now_playing()
        weather = self.read_weather_stats()

        values = {
            "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
            "ip_local": self.read_local_ip(),
            "time_hms": time.strftime("%H:%M:%S", now),
            "date_ymd": time.strftime("%Y-%m-%d", now),
            "cpu_usage_percent": self.read_cpu_usage_percent(),
            "cpu_core_avg_percent": _format_percent(None if core_summary is None else core_summary[0]),
            "cpu_core_max_percent": _format_percent(None if core_summary is None else core_summary[1]),
            "cpu_core_count": "N/A" if core_summary is None else str(core_summary[2]),
            "cpu_freq_ghz": self.read_cpu_freq_ghz(),
            "cpu_temp_c": self.read_cpu_temperature(),
            "load_average": self.read_load_average(),
            "mem_used_mb": "N/A" if mem is None else str(mem[0]),
            "mem_total_mb": "N/A" if mem is None else str(mem[1]),
            "mem_percent": "N/A" if mem is None else f"{mem[2]}%",
            "disk_used_gb": "N/A" if disk is None else str(disk[0]),
            "disk_total_gb": "N/A" if disk is None else str(disk[1]),
            "disk_percent": "N/A" if disk is None else f"{disk[2]}%",
            "net_dl_kbps": f"{dl_speed:.1f} KB/s",
            "net_ul_kbps": f"{ul_speed:.1f} KB/s",
            **volume,
            **audio_eq,
            "uptime_human": "N/A" if uptime is None else f"{uptime[0]}h {uptime[1]}m",
            **gpu,
            **media,
            **weather,
        }
        return StatsSnapshot(values=values)
