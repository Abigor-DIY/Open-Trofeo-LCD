import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gpu_sources import find_amd_card, has_nvidia_card, read_amd_gpu_stats
from stats_sources import StatsProvider


class AmdGpuSourceTests(unittest.TestCase):
    def test_selects_discrete_amd_card_and_reads_common_sysfs_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            drm = Path(tmp)
            for index, total in ((0, 512 * 1048576), (1, 24 * 1024 * 1048576)):
                device = drm / f"card{index}" / "device"
                device.mkdir(parents=True)
                (device / "vendor").write_text("0x1002\n", encoding="utf-8")
                (device / "mem_info_vram_total").write_text(str(total), encoding="utf-8")
            device = drm / "card1" / "device"
            (device / "product_name").write_text("AMD Radeon RX 7900 XTX\n", encoding="utf-8")
            (device / "mem_info_vram_used").write_text(str(12 * 1024 * 1048576), encoding="utf-8")
            (device / "gpu_busy_percent").write_text("73\n", encoding="utf-8")
            hwmon = device / "hwmon" / "hwmon2"
            hwmon.mkdir(parents=True)
            (hwmon / "name").write_text("amdgpu\n", encoding="utf-8")
            (hwmon / "temp1_input").write_text("65000\n", encoding="utf-8")

            card = find_amd_card(drm)
            self.assertEqual(card, drm / "card1")
            self.assertFalse(has_nvidia_card(drm))
            self.assertEqual(read_amd_gpu_stats(card), {
                "gpu_name": "AMD Radeon RX 7900 XTX",
                "gpu_load": "73%", "gpu_temp": "65°C",
                "vram_used_mb": "12288", "vram_total_mb": "24576", "vram_percent": "50%",
            })
            (drm / "card0" / "device" / "vendor").write_text("0x10de\n", encoding="utf-8")
            self.assertTrue(has_nvidia_card(drm))

    def test_amd_detection_survives_installed_nvidia_smi_without_nvidia_card(self) -> None:
        provider = StatsProvider.__new__(StatsProvider)
        provider._local_or_host_cmd = lambda _name: ["nvidia-smi"]
        with patch("stats_sources.find_amd_card", return_value=Path("/sys/class/drm/card2")):
            with patch("stats_sources.has_nvidia_card", return_value=False):
                with patch("stats_sources.subprocess.check_output", side_effect=OSError("No NVIDIA device")):
                    with patch.dict("os.environ", {"OPEN_TROFEO_GPU_VENDOR": "auto"}):
                        self.assertEqual(provider._detect_gpu_type(), "card2")


class WeatherUnitTests(unittest.TestCase):
    def _provider(self, cache_path: Path) -> StatsProvider:
        provider = StatsProvider.__new__(StatsProvider)
        provider._weather_temp_unit = "celsius"
        provider._weather_icon_map = {}
        provider._weather_cache_path = str(cache_path)
        provider._weather_lat = 40.0
        provider._weather_lon = -75.0
        provider._weather_location = "Test City"
        provider._weather_refresh_s = 900.0
        provider._last_weather_snapshot = {}
        provider._last_weather_at = 0.0
        provider._last_weather_error = ""
        provider._last_weather_source = "none"
        return provider

    def test_fahrenheit_updates_current_and_forecast_from_celsius_cache(self) -> None:
        raw = {
            "current": {"temperature_2m": 20, "apparent_temperature": 19, "weather_code": 0},
            "daily": {"time": ["2026-10-24"], "temperature_2m_min": [10], "temperature_2m_max": [25], "weather_code": [0]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "open-meteo.json"
            provider = self._provider(cache_path)
            celsius = provider._normalize_weather_response(raw, "Test City")
            cache_path.write_text(json.dumps({"fetched_at": 123, "raw": raw, "normalized": celsius}), encoding="utf-8")
            self.assertEqual(celsius["weather_temp_c"], "20°C")

            provider.set_weather_config(lat=40.0, lon=-75.0, temperature_unit="fahrenheit")
            fahrenheit, cached_at = provider._cached_weather_snapshot()
            self.assertEqual(cached_at, 123)
            self.assertEqual(fahrenheit["weather_temp_c"], "68°F")
            self.assertEqual(fahrenheit["weather_feels_like_c"], "66°F")
            self.assertEqual(fahrenheit["weather_day_0_temp_min_c"], "50°F")
            self.assertEqual(fahrenheit["weather_day_0_temp_max_c"], "77°F")
            self.assertEqual(provider.weather_config()["temperature_unit"], "fahrenheit")


if __name__ == "__main__":
    unittest.main()
