import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit

from config_preferences import ConfigPreferencesController


class ConfigPreferencesControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _owner(self) -> SimpleNamespace:
        calls: list[str] = []
        owner = SimpleNamespace(
            calls=calls,
            _close_to_tray_enabled=True,
            apply_ui_chrome=lambda: calls.append("chrome"),
            apply_weather_config=lambda: calls.append("weather"),
            apply_audio_eq_config=lambda: calls.append("audio"),
            _save_ui_state=lambda: calls.append("save"),
            _restore_ui_state=lambda: calls.append("restore"),
            _load_ui_state_payload=lambda: {"ui_theme": "Plasma Blue"},
            append_log=lambda message: calls.append(message),
        )
        owner.ui_theme_combo = QComboBox()
        owner.ui_theme_combo.addItems(["Plasma Blue", "Dark"])
        owner.ui_mode_combo = QComboBox()
        owner.ui_mode_combo.addItems(["Dark", "Light"])
        owner.ui_scale_combo = QComboBox()
        owner.ui_scale_combo.addItems(["90%", "100%"])
        owner.ui_scale_combo.setCurrentText("100%")
        owner.cfg_ui_theme_combo = QComboBox()
        owner.cfg_ui_theme_combo.addItems(["Plasma Blue", "Dark"])
        owner.cfg_ui_mode_combo = QComboBox()
        owner.cfg_ui_mode_combo.addItems(["Dark", "Light"])
        owner.cfg_ui_scale_combo = QComboBox()
        owner.cfg_ui_scale_combo.addItems(["90%", "100%"])
        owner.cfg_weather_lat_edit = QLineEdit("50.0")
        owner.cfg_audio_eq_input_combo = QComboBox()
        owner.theme_doc_path_edit = QLineEdit("/themes/current.json")
        return owner

    def test_sync_ui_controls_from_header_copies_header_state(self) -> None:
        owner = self._owner()
        owner.ui_theme_combo.setCurrentText("Dark")
        owner.ui_mode_combo.setCurrentText("Light")
        owner.ui_scale_combo.setCurrentText("90%")
        controller = ConfigPreferencesController(
            owner,
            ui_state_path=Path("unused-ui-state.json"),
            theme_autosave_path=Path("unused-theme-autosave.json"),
        )

        controller.sync_ui_controls_from_header()

        self.assertEqual(owner.cfg_ui_theme_combo.currentText(), "Dark")
        self.assertEqual(owner.cfg_ui_mode_combo.currentText(), "Light")
        self.assertEqual(owner.cfg_ui_scale_combo.currentText(), "90%")

    def test_apply_preferences_updates_header_and_applies_integrations(self) -> None:
        owner = self._owner()
        owner.cfg_ui_theme_combo.setCurrentText("Dark")
        owner.cfg_ui_mode_combo.setCurrentText("Light")
        owner.cfg_ui_scale_combo.setCurrentText("90%")
        controller = ConfigPreferencesController(
            owner,
            ui_state_path=Path("unused-ui-state.json"),
            theme_autosave_path=Path("unused-theme-autosave.json"),
        )

        controller.apply_preferences()

        self.assertEqual(owner.ui_theme_combo.currentText(), "Dark")
        self.assertEqual(owner.ui_mode_combo.currentText(), "Light")
        self.assertEqual(owner.ui_scale_combo.currentText(), "90%")
        self.assertEqual(owner.calls[:4], ["chrome", "weather", "audio", "save"])

    def test_clear_cache_removes_known_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ui_state = Path(tmp) / "ui.json"
            autosave = Path(tmp) / "autosave.json"
            ui_state.write_text("{}", encoding="utf-8")
            autosave.write_text("{}", encoding="utf-8")
            owner = self._owner()
            controller = ConfigPreferencesController(
                owner,
                ui_state_path=ui_state,
                theme_autosave_path=autosave,
            )

            controller.clear_cache()

            self.assertFalse(ui_state.exists())
            self.assertFalse(autosave.exists())
            self.assertIn("[config] Wyczyszczono cache aplikacji.", owner.calls)

    def test_export_and_import_configuration_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_path = Path(tmp) / "export.json"
            import_path = Path(tmp) / "import.json"
            ui_state = Path(tmp) / "ui-state.json"
            import_path.write_text(json.dumps({"ui_theme": "Dark"}), encoding="utf-8")
            owner = self._owner()
            controller = ConfigPreferencesController(
                owner,
                ui_state_path=ui_state,
                theme_autosave_path=Path(tmp) / "autosave.json",
            )

            with patch("config_preferences.QFileDialog.getSaveFileName", return_value=(str(export_path), "")):
                controller.export_file()
            with patch("config_preferences.QFileDialog.getOpenFileName", return_value=(str(import_path), "")):
                controller.import_file()

            self.assertEqual(json.loads(export_path.read_text(encoding="utf-8"))["theme_json"], "/themes/current.json")
            self.assertEqual(json.loads(ui_state.read_text(encoding="utf-8"))["ui_theme"], "Dark")
            self.assertIn("restore", owner.calls)
            self.assertIn("chrome", owner.calls)


if __name__ == "__main__":
    unittest.main()
