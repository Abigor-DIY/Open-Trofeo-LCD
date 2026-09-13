import unittest

from stats_sources import StatsProvider


class GameProcessDetectionTests(unittest.TestCase):
    def test_wine_helper_is_not_presented_as_game(self) -> None:
        score, label, _launcher = StatsProvider._score_game_process(
            "winedevice.exe",
            "C:\\windows\\system32\\winedevice.exe",
            "SteamGameId=12345",
            {"SteamGameId": "12345"},
        )
        self.assertLessEqual(score, 40)
        self.assertEqual(label, "N/A")

    def test_explicit_steam_launch_name_overrides_helper_process(self) -> None:
        score, label, launcher = StatsProvider._score_game_process(
            "winedevice.exe",
            "C:\\windows\\system32\\winedevice.exe",
            "OPEN_TROFEO_GAME_NAME=Heroes Olden Era OPEN_TROFEO_GAME_LAUNCHER=Steam",
            {
                "OPEN_TROFEO_GAME_NAME": "Heroes Olden Era",
                "OPEN_TROFEO_GAME_LAUNCHER": "Steam",
            },
        )
        self.assertGreater(score, 40)
        self.assertEqual(label, "Heroes Olden Era")
        self.assertEqual(launcher, "Steam")

    def test_regular_exe_still_scores_as_game_candidate(self) -> None:
        score, label, launcher = StatsProvider._score_game_process(
            "Game-Win64-Shipping.exe",
            "/steamapps/common/Game/Game-Win64-Shipping.exe",
            "SteamGameId=12345",
            {"SteamGameId": "12345"},
        )
        self.assertGreater(score, 40)
        self.assertEqual(label, "Game-Win64-Shipping")
        self.assertEqual(launcher, "Steam")


if __name__ == "__main__":
    unittest.main()

