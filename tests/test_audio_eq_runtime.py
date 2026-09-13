import os
import tempfile
import unittest
from unittest.mock import patch

from stats_sources import StatsProvider


class AudioEqRuntimeTests(unittest.TestCase):
    def test_audio_eq_is_lazy_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as state_home:
            with patch.dict(
                os.environ,
                {
                    "XDG_STATE_HOME": state_home,
                    "OPEN_TROFEO_AUDIO_EQ": "1",
                    "OPEN_TROFEO_CAVA_FRAMERATE": "30",
                    "OPEN_TROFEO_CAVA_NICE": "8",
                },
                clear=False,
            ):
                with patch.object(StatsProvider, "_local_or_host_cmd", return_value=["/bin/false"]):
                    with patch.object(StatsProvider, "_start_fps_probe_server"):
                        provider = StatsProvider()

        status = provider.audio_eq_status()
        self.assertEqual(status["status"], "idle")
        self.assertTrue(status["enabled"])
        self.assertFalse(status["thread_started"])
        self.assertEqual(status["framerate"], 30)
        self.assertEqual(status["nice"], 8)

    def test_audio_eq_auto_prefers_pipewire_before_pulse(self) -> None:
        with tempfile.TemporaryDirectory() as state_home:
            with patch.dict(os.environ, {"XDG_STATE_HOME": state_home, "OPEN_TROFEO_AUDIO_EQ": "1"}, clear=False):
                with patch.object(StatsProvider, "_local_or_host_cmd", return_value=["/bin/false"]):
                    with patch.object(StatsProvider, "_start_fps_probe_server"):
                        provider = StatsProvider()

        self.assertEqual(provider._audio_eq_input_candidates(), ["pipewire", "pulse", "alsa"])

    def test_audio_eq_framerate_is_clamped(self) -> None:
        self.assertEqual(StatsProvider._parse_audio_eq_framerate("120"), 60)
        self.assertEqual(StatsProvider._parse_audio_eq_framerate("1"), 10)
        self.assertEqual(StatsProvider._parse_audio_eq_framerate("bad"), 30)

    def test_audio_eq_nice_is_clamped(self) -> None:
        self.assertEqual(StatsProvider._parse_audio_eq_nice("30"), 19)
        self.assertEqual(StatsProvider._parse_audio_eq_nice("-5"), 0)
        self.assertEqual(StatsProvider._parse_audio_eq_nice("bad"), 8)

    def test_audio_eq_command_uses_nice_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as state_home:
            with patch.dict(os.environ, {"XDG_STATE_HOME": state_home, "OPEN_TROFEO_CAVA_NICE": "9"}, clear=False):
                with patch.object(StatsProvider, "_local_or_host_cmd", return_value=["/usr/bin/cava"]):
                    with patch.object(StatsProvider, "_start_fps_probe_server"):
                        with patch("stats_sources.shutil.which", return_value="/usr/bin/nice"):
                            provider = StatsProvider()

        self.assertEqual(
            provider._audio_eq_command("/tmp/cava.conf"),
            ["/usr/bin/nice", "-n", "9", "/usr/bin/cava", "-p", "/tmp/cava.conf"],
        )


if __name__ == "__main__":
    unittest.main()
