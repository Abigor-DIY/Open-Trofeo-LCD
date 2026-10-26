import os
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from trofeo_gui import TrofeoGui


class TrofeoGuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_builds_without_backend_background_tasks(self) -> None:
        window = TrofeoGui("http://127.0.0.1:18777", start_background_tasks=False)
        try:
            self.assertEqual(window.main_tabs.count(), 4)
            self.assertTrue(hasattr(window, "configuration_panel"))
            self.assertTrue(hasattr(window, "system_events_list"))
            self.assertTrue(hasattr(window, "runtime_sections_tabs"))
            self.assertTrue(hasattr(window, "theme_gallery_browser"))
            self.assertEqual(window.main_tabs.currentIndex(), 0)
            self.assertFalse(window.status_timer.isActive())
            self.assertFalse(window.show_request_timer.isActive())
        finally:
            window.status_timer.stop()
            window.show_request_timer.stop()
            window.close()
            window.deleteLater()
            QApplication.processEvents()

    def test_old_fps_probe_has_an_upgrade_hint_until_reconfigured(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            manifest = home / ".local/share/vulkan/implicit_layer.d/VkLayer_OPEN_TROFEO_fps.json"
            manifest.parent.mkdir(parents=True)
            owner = SimpleNamespace(cfg_fps_layer_status_label=QLabel(),
                                    _steam_flatpak_installed=lambda: False,
                                    _refresh_gaming_auto_theme_status=lambda: None,
                                    _tr=lambda en, pl: en)
            with patch.object(Path, "home", return_value=home):
                for version, expected in ((1, True), (2, False)):
                    manifest.write_text(json.dumps({"layer": {"implementation_version": version}}))
                    TrofeoGui.refresh_fps_layer_status(owner)
                    self.assertEqual("update available" in owner.cfg_fps_layer_status_label.text(), expected)

    def test_global_rotation_apply_acknowledgement_and_cancel(self) -> None:
        window = TrofeoGui("http://127.0.0.1:18777", start_background_tasks=False)
        try:
            window.api_call = Mock()
            window._lcd_rotation = 0
            window.cfg_display_rotation_combo.setCurrentIndex(1)
            window.apply_lcd_config()
            window.api_call.assert_called_once_with("lcd-config", "POST", "/v1/config", {"display_rotation": 180})
            self.assertTrue(window._lcd_rotation_dirty)
            window._on_api_result("lcd-config", True, {"status": {"ok": True, "config": {"display_rotation": 180}}})
            self.assertFalse(window._lcd_rotation_dirty)
            self.assertEqual(window._lcd_rotation, 180)
            window.cfg_display_rotation_combo.setCurrentIndex(0)
            window._update_status({"ok": True, "config": {"display_rotation": 180}})
            self.assertEqual(window.cfg_display_rotation_combo.currentData(), 0)
            window.cfg_cancel_btn.click()
            self.assertEqual(window.cfg_display_rotation_combo.currentData(), 180)
        finally:
            window.status_timer.stop()
            window.show_request_timer.stop()
            window.close()
            window.deleteLater()
            QApplication.processEvents()

    def test_gaming_auto_theme_applies_selected_theme_and_restores_previous_theme(self) -> None:
        window = TrofeoGui("http://127.0.0.1:18777", start_background_tasks=False)
        applied: list[str] = []
        try:
            window.theme_items = {
                "Daily": {"name": "Daily", "type": "theme-doc", "path": "daily.json"},
                "Gaming": {"name": "Gaming", "type": "theme-doc", "path": "gaming.json"},
            }
            window.theme_combo.clear()
            window.theme_combo.addItems(["Daily", "Gaming"])
            window.theme_combo.setCurrentText("Daily")
            window._gaming_auto_theme_enabled = True
            window._gaming_auto_theme_name = "Gaming"
            window._gaming_auto_theme_restore_on_fps_loss = False
            window.append_log = lambda _message: None
            window._apply_runtime_theme_card = lambda name: applied.append(name)

            window._sync_gaming_auto_theme_combo()
            window._maybe_apply_gaming_auto_theme({"config": {"game": {"game_active": "yes", "game_name": "Heroes"}}})
            self.assertEqual(applied, ["Gaming"])
            self.assertEqual(window._gaming_auto_theme_previous_name, "Daily")

            window.theme_combo.setCurrentText("Gaming")
            window._maybe_apply_gaming_auto_theme({"config": {"game": {"game_active": "no", "game_name": "N/A"}}})

            self.assertEqual(window.cfg_game_auto_theme_combo.currentData(), "Gaming")
            self.assertEqual(applied, ["Gaming", "Daily"])
            self.assertFalse(window._gaming_auto_theme_restore_pending)
            self.assertEqual(window._gaming_auto_theme_previous_name, "")
        finally:
            window.status_timer.stop()
            window.show_request_timer.stop()
            window.close()
            window.deleteLater()
            QApplication.processEvents()

    def test_gaming_fps_panel_shows_live_summary_and_csv_path(self) -> None:
        window = TrofeoGui("http://127.0.0.1:18777", start_background_tasks=False)
        try:
            window._update_gaming_fps_metrics(
                {
                    "game_name": "Space Marine 2",
                    "game_fps": "84",
                    "game_frametime_ms": "12.2 ms",
                    "game_fps_avg": "91",
                    "game_fps_min": "50",
                    "game_fps_max": "112",
                    "game_fps_1pct_low": "72",
                    "game_fps_0_1pct_low": "61",
                    "game_stutter_count": "3",
                    "game_session_time": "3m 09s",
                },
                {
                    "active": "yes",
                    "log_path": "/tmp/fps-session.csv",
                    "log_error": "",
                    "log_dropped_samples": 0,
                },
            )

            text = window.cfg_fps_metrics_label.text()
            self.assertIn("Space Marine 2", text)
            self.assertIn("MIN 50", text)
            self.assertIn("MAX 112", text)
            self.assertIn("1% LOW 72", text)
            self.assertEqual(window.cfg_fps_log_path_edit.text(), "/tmp/fps-session.csv")
        finally:
            window.status_timer.stop()
            window.show_request_timer.stop()
            window.close()
            window.deleteLater()
            QApplication.processEvents()

    def test_vrr_controls_show_policy_and_reenable_buttons(self) -> None:
        window = TrofeoGui("http://127.0.0.1:18777", start_background_tasks=False)
        messages: list[str] = []
        try:
            window.append_log = messages.append
            window._vrr_action_in_flight = True
            window._set_vrr_controls_enabled(False)

            window._finish_vrr_control(True, "DP-4: Automatic")

            self.assertFalse(window._vrr_action_in_flight)
            self.assertIn("DP-4: Automatic", window.cfg_vrr_status_label.text())
            self.assertTrue(window.cfg_vrr_automatic_btn.isEnabled())
            self.assertTrue(window.cfg_vrr_off_btn.isEnabled())
            self.assertIn("[vrr] OK", messages[-1])
        finally:
            window.status_timer.stop()
            window.show_request_timer.stop()
            window.close()
            window.deleteLater()
            QApplication.processEvents()

    def test_gaming_auto_theme_test_option_restores_on_fps_loss_and_reapplies_on_return(self) -> None:
        window = TrofeoGui("http://127.0.0.1:18777", start_background_tasks=False)
        applied: list[str] = []
        try:
            window.theme_items = {
                "Daily": {"name": "Daily", "type": "theme-doc", "path": "daily.json"},
                "Gaming": {"name": "Gaming", "type": "theme-doc", "path": "gaming.json"},
            }
            window.theme_combo.clear()
            window.theme_combo.addItems(["Daily", "Gaming"])
            window.theme_combo.setCurrentText("Daily")
            window._gaming_auto_theme_enabled = True
            window._gaming_auto_theme_name = "Gaming"
            window._gaming_auto_theme_restore_on_fps_loss = True
            window._gaming_auto_theme_fps_loss_delay_s = 5
            window.append_log = lambda _message: None
            window._apply_runtime_theme_card = lambda name: applied.append(name)

            window._maybe_apply_gaming_auto_theme(
                {"game": {"game_active": "yes", "game_name": "Heroes", "game_fps": "91", "game_frametime_ms": "11.0 ms"}}
            )
            self.assertEqual(applied, ["Gaming"])
            self.assertEqual(window._gaming_auto_theme_previous_name, "Daily")

            window.theme_combo.setCurrentText("Gaming")
            window._gaming_auto_theme_fps_missing_since = time.monotonic() - 10.0
            window._maybe_apply_gaming_auto_theme(
                {"game": {"game_active": "yes", "game_name": "Heroes", "game_fps": "N/A", "game_frametime_ms": "N/A"}}
            )
            self.assertEqual(applied, ["Gaming", "Daily"])
            self.assertTrue(window._gaming_auto_theme_restored_for_fps_loss)

            window.theme_combo.setCurrentText("Daily")
            window._maybe_apply_gaming_auto_theme(
                {"game": {"game_active": "yes", "game_name": "Heroes", "game_fps": "88", "game_frametime_ms": "11.4 ms"}}
            )
            self.assertEqual(applied, ["Gaming", "Daily", "Gaming"])
            self.assertEqual(window._gaming_auto_theme_previous_name, "Daily")
            self.assertFalse(window._gaming_auto_theme_restored_for_fps_loss)
        finally:
            window.status_timer.stop()
            window.show_request_timer.stop()
            window.close()
            window.deleteLater()
            QApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
