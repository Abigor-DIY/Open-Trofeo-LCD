import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from stats_sources import StatsProvider


class FpsProbeSocketTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.socket_path = str(Path(self._tmp.name) / "fps.sock")
        self._previous = os.environ.get("OPEN_TROFEO_FPS_SOCKET")
        os.environ["OPEN_TROFEO_FPS_SOCKET"] = self.socket_path

    def tearDown(self) -> None:
        if self._previous is None:
            os.environ.pop("OPEN_TROFEO_FPS_SOCKET", None)
        else:
            os.environ["OPEN_TROFEO_FPS_SOCKET"] = self._previous
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass
        self._tmp.cleanup()

    def _send(self, fps: float) -> None:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            client.sendto(
                json.dumps({"fps": fps, "source": "unit-test"}).encode("utf-8"),
                self.socket_path,
            )
        finally:
            client.close()

    def test_disabled_provider_does_not_create_socket(self) -> None:
        provider = StatsProvider(enable_fps_probe=False)
        time.sleep(0.1)
        self.assertFalse(provider._fps_probe_enabled)
        self.assertFalse(Path(self.socket_path).exists())

    def test_enabled_provider_receives_samples_and_is_not_stolen(self) -> None:
        provider = StatsProvider(enable_fps_probe=True)
        for _ in range(50):
            if StatsProvider._fps_probe_socket_is_live(self.socket_path):
                break
            time.sleep(0.05)
        self.assertTrue(StatsProvider._fps_probe_socket_is_live(self.socket_path), "socket was not served")

        self._send(144.0)
        for _ in range(50):
            if provider._fps_probe_snapshot.get("game_fps") not in {"", "N/A"}:
                break
            time.sleep(0.05)
        self.assertEqual(provider._fps_probe_snapshot.get("game_fps"), "144")

        # A second provider must not steal the live socket from the first one.
        second = StatsProvider(enable_fps_probe=True)
        time.sleep(0.2)
        self._send(90.0)
        for _ in range(50):
            if provider._fps_probe_snapshot.get("game_fps") == "90":
                break
            time.sleep(0.05)
        self.assertEqual(provider._fps_probe_snapshot.get("game_fps"), "90")
        self.assertIn(second._fps_probe_snapshot.get("game_fps"), {"", "N/A"})


if __name__ == "__main__":
    unittest.main()
