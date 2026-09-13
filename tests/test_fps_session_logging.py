import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stats_sources import StatsProvider


class FpsSessionLoggingTests(unittest.TestCase):
    def _provider(self, state_home: str) -> StatsProvider:
        env = {
            "XDG_STATE_HOME": state_home,
            "OPEN_TROFEO_AUDIO_EQ": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(StatsProvider, "_start_fps_probe_server"):
                return StatsProvider()

    @staticmethod
    def _send(provider: StatsProvider, *, fps: float, frametime_ms: float, frames: int, pid: int = 1234) -> None:
        provider._accept_fps_probe_payload(
            json.dumps(
                {
                    "fps": fps,
                    "frametime_ms": frametime_ms,
                    "session_frames": frames,
                    "source": "open-trofeo-test-probe",
                    "game_name": "Test Game",
                    "game_process": "test-game",
                    "game_launcher": "tests",
                    "pid": pid,
                }
            ).encode("utf-8")
        )

    def test_session_stats_and_csv_log_are_updated(self) -> None:
        with tempfile.TemporaryDirectory() as state_home:
            provider = self._provider(state_home)
            try:
                self._send(provider, fps=60.0, frametime_ms=40.0, frames=15)
                self._send(provider, fps=120.0, frametime_ms=8.0, frames=45)

                status = provider.game_status()
                probe = provider.fps_probe_status()
                self.assertEqual(status["game_fps_avg"], "90")
                self.assertEqual(status["game_fps_min"], "60")
                self.assertEqual(status["game_fps_max"], "120")
                self.assertEqual(status["game_stutter_count"], "1")
                self.assertEqual(probe["session"]["game_fps_max"], "120")

                log_path = Path(str(probe["log_path"]))
                provider.close_fps_logging()
                self.assertTrue(log_path.exists())
                with log_path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[-1]["session_avg_fps"], "90")
                self.assertEqual(rows[-1]["session_min_fps"], "60")
                self.assertEqual(rows[-1]["session_max_fps"], "120")
                self.assertEqual(rows[-1]["game_name"], "Test Game")
            finally:
                provider.close_fps_logging()

    def test_new_probe_pid_starts_a_new_session_log(self) -> None:
        with tempfile.TemporaryDirectory() as state_home:
            provider = self._provider(state_home)
            try:
                self._send(provider, fps=60.0, frametime_ms=16.7, frames=15, pid=111)
                first_path = str(provider.fps_probe_status()["log_path"])
                self._send(provider, fps=144.0, frametime_ms=6.9, frames=36, pid=222)
                second_status = provider.fps_probe_status()

                self.assertNotEqual(first_path, second_status["log_path"])
                self.assertEqual(second_status["session"]["game_fps_avg"], "144")
                self.assertEqual(second_status["session"]["game_fps_min"], "144")
            finally:
                provider.close_fps_logging()


if __name__ == "__main__":
    unittest.main()
