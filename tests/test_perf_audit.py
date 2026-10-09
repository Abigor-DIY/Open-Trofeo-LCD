import os
import tempfile
import time
import unittest
from pathlib import Path

from stats_sources import StatsProvider
from trofeo_backend import ReplayController


class GameProcessFilterTests(unittest.TestCase):
    def test_steam_shader_compiler_is_not_a_game(self) -> None:
        score, _label, _launcher = StatsProvider._score_game_process(
            "fossilize_replay",
            "/home/u/.steam/steamapps/common/Game/fossilize_replay --cache /tmp/x",
            "STEAMAPPID=1234",
        )
        self.assertLessEqual(score, 40, "fossilize_replay must be filtered out")

    def test_real_steam_game_still_detected(self) -> None:
        score, label, _launcher = StatsProvider._score_game_process(
            "MyGame",
            "/home/u/.steam/steamapps/common/MyGame/MyGame",
            "STEAMAPPID=1234",
        )
        self.assertGreater(score, 40)
        self.assertTrue(label)

    def test_steam_runtime_helper_is_not_a_game(self) -> None:
        score, _label, _launcher = StatsProvider._score_game_process(
            "srt-logger",
            "/usr/lib/steam-runtime/srt-logger --foo",
            "",
        )
        self.assertLessEqual(score, 40)


class FpsWarmupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = StatsProvider(enable_fps_probe=False)
        self.provider._fps_probe_session_warmup_s = 20.0

    def test_warmup_samples_excluded_from_gameplay_min(self) -> None:
        now = time.time()
        self.provider._fps_probe_session_start_at = now
        # Inside warmup: a 1 FPS shader-compile spike must not become the min.
        self.provider._update_fps_session_stats_locked(now, 1.0, 1000.0)
        self.assertIsNone(self.provider._fps_probe_gameplay_fps_min)
        self.assertEqual(self.provider._fps_probe_session_fps_min, 1.0)

        # After warmup: real gameplay becomes the reported minimum.
        later = now + 30.0
        self.provider._update_fps_session_stats_locked(later, 60.0, 16.6)
        self.assertEqual(self.provider._fps_probe_gameplay_fps_min, 60.0)

    def test_session_and_gameplay_min_are_separated(self) -> None:
        now = time.time()
        self.provider._fps_probe_session_start_at = now - 100.0
        self.provider._update_fps_session_stats_locked(now, 30.0, 33.0)
        self.provider._fps_probe_history.append({"at": now, "fps": 30.0, "frametime_ms": 33.0, "warmup": False})
        stats = self.provider._fps_history_stats_locked(now)
        self.assertEqual(stats["game_fps_min"], "30")
        self.assertEqual(stats["game_fps_min_session"], "30")
        self.assertEqual(stats["game_fps_warmup"], "no")


class PruneDirByCountTests(unittest.TestCase):
    def test_keeps_newest_and_removes_rest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for index in range(5):
                target = path / f"f{index}"
                target.write_text("x")
                os.utime(target, (1000 + index, 1000 + index))
            removed = ReplayController._prune_dir_by_count(path, 2)
            self.assertEqual(removed, 3)
            remaining = sorted(p.name for p in path.iterdir())
            self.assertEqual(remaining, ["f3", "f4"])


if __name__ == "__main__":
    unittest.main()
