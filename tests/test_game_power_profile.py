import os
import sys
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from game_power_profile import GamePowerProfile, GamePowerWidget


class GamePowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.c = GamePowerProfile()
        self.c.timer.stop()

    def tearDown(self):
        self.c.shutdown()

    def observe(self, active=True):
        self.c.observe({"config": {"game": {"game_active": active, "game_fps": "N/A"}}})

    def test_opt_in_and_independent_of_fps(self):
        with patch.object(self.c, "start") as start:
            self.observe()
            start.assert_not_called()
            self.c.set_enabled(True)
            start.assert_called_once()

    def test_debounce_and_stale_watchdog(self):
        self.c.enabled = True
        with patch.object(self.c, "start"), patch.object(self.c, "release") as release:
            self.observe()
            self.c.process = object()
            self.c.ready = True
            self.observe(False)
            release.assert_not_called()
            self.observe(True)
            self.assertIsNone(self.c.inactive_since)
            self.c.last_seen -= 31
            self.c.tick()
            release.assert_called_once()
            self.c.process = None

    def test_end_grace_and_error_latch(self):
        self.c.enabled = True
        self.c.failed = True
        with patch.object(self.c, "start") as start:
            self.observe()
            start.assert_not_called()
            self.observe(False)
            self.c.inactive_since -= 13
            self.c.tick()
            self.assertFalse(self.c.failed)
            self.observe()
            start.assert_called_once()

    def test_missing_command(self):
        with patch("game_power_profile.shutil.which", return_value=None):
            self.c.enabled = True
            self.observe()
            self.assertTrue(self.c.failed)
            self.assertIsNone(self.c.process)

    def test_child_ready_and_eof_release(self):
        command = (sys.executable, ["-u", "-c", "import sys; print('TROFEO_HOLD_READY'); sys.stdin.read()"])
        with patch.object(self.c, "command", return_value=command):
            self.c.enabled = True
            self.observe()
            deadline = time.monotonic() + 3
            while not self.c.ready and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
            self.assertTrue(self.c.ready)
            process = self.c.process
            self.c.set_enabled(False)
            self.assertTrue(process.waitForFinished(2000))
            self.assertIsNone(self.c.process)
            self.assertFalse(self.c.failed)

    def test_widget_defaults_disabled(self):
        widget = GamePowerWidget()
        self.assertFalse(widget.checkbox.isChecked())
        widget.controller.shutdown()
        widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
