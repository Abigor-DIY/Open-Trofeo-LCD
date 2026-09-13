"""Configuration preference actions shared by the Qt shell and config panel."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


class ConfigPreferencesController:
    def __init__(
        self,
        owner: Any,
        *,
        ui_state_path: Path,
        theme_autosave_path: Path,
    ) -> None:
        self.owner = owner
        self.ui_state_path = ui_state_path
        self.theme_autosave_path = theme_autosave_path

    def sync_ui_controls_from_header(self) -> None:
        owner = self.owner
        if not hasattr(owner, "cfg_ui_theme_combo"):
            return
        if getattr(owner, "cfg_ui_theme_combo", None) is getattr(owner, "ui_theme_combo", None):
            return
        pairs = [
            (owner.cfg_ui_theme_combo, getattr(owner, "ui_theme_combo", None), "currentText"),
            (owner.cfg_ui_mode_combo, getattr(owner, "ui_mode_combo", None), "currentText"),
        ]
        for target, source, accessor in pairs:
            if source is None:
                continue
            target.blockSignals(True)
            target.setCurrentText(getattr(source, accessor)())
            target.blockSignals(False)
        if hasattr(owner, "cfg_ui_scale_combo") and hasattr(owner, "ui_scale_combo"):
            owner.cfg_ui_scale_combo.blockSignals(True)
            owner.cfg_ui_scale_combo.setCurrentIndex(owner.ui_scale_combo.currentIndex())
            owner.cfg_ui_scale_combo.blockSignals(False)

    def apply_preferences(self) -> None:
        owner = self.owner
        if hasattr(owner, "cfg_ui_theme_combo"):
            owner.ui_theme_combo.setCurrentText(owner.cfg_ui_theme_combo.currentText())
        if hasattr(owner, "cfg_ui_mode_combo"):
            owner.ui_mode_combo.setCurrentText(owner.cfg_ui_mode_combo.currentText())
        if hasattr(owner, "cfg_ui_scale_combo"):
            owner.ui_scale_combo.setCurrentIndex(owner.cfg_ui_scale_combo.currentIndex())
        owner.apply_ui_chrome()
        if hasattr(owner, "cfg_weather_lat_edit"):
            owner.apply_weather_config()
        if hasattr(owner, "cfg_audio_eq_input_combo"):
            owner.apply_audio_eq_config()
        owner._save_ui_state()
        owner.append_log("[config] Zastosowano ustawienia interfejsu.")

    def reset_defaults(self) -> None:
        owner = self.owner
        if hasattr(owner, "cfg_ui_theme_combo"):
            owner.cfg_ui_theme_combo.setCurrentText("Plasma Blue")
        if hasattr(owner, "cfg_ui_mode_combo"):
            owner.cfg_ui_mode_combo.setCurrentText("Dark")
        if hasattr(owner, "cfg_ui_scale_combo"):
            owner.cfg_ui_scale_combo.setCurrentText("100%")
        if hasattr(owner, "cfg_preview_fps_combo"):
            owner.cfg_preview_fps_combo.setCurrentText("30")
        if hasattr(owner, "cfg_refresh_combo"):
            owner.cfg_refresh_combo.setCurrentText("1.5 s")
        self.apply_preferences()

    def export_file(self) -> None:
        owner = self.owner
        selected, _ = QFileDialog.getSaveFileName(
            owner,
            "Eksportuj konfigurację",
            str(Path.cwd() / "trofeo-ui-config.json"),
            "JSON (*.json);;All files (*)",
        )
        if not selected:
            return
        payload = owner._load_ui_state_payload()
        payload["theme_json"] = owner.theme_doc_path_edit.text().strip() if hasattr(owner, "theme_doc_path_edit") else ""
        Path(selected).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        owner.append_log(f"[config] Eksport ustawień: {selected}")

    def import_file(self) -> None:
        owner = self.owner
        selected, _ = QFileDialog.getOpenFileName(
            owner,
            "Importuj konfigurację",
            str(Path.cwd()),
            "JSON (*.json);;All files (*)",
        )
        if not selected:
            return
        payload = json.loads(Path(selected).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Nieprawidłowy plik konfiguracji.")
        self.ui_state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        owner._restore_ui_state()
        self.sync_ui_controls_from_header()
        owner.apply_ui_chrome()
        owner.append_log(f"[config] Import ustawień: {selected}")

    def clear_cache(self) -> None:
        owner = self.owner
        for path in (self.theme_autosave_path, self.ui_state_path):
            try:
                if path.exists():
                    path.unlink()
            except Exception as exc:
                owner.append_log(f"[config] cache-skip {path}: {exc}")
        owner.append_log("[config] Wyczyszczono cache aplikacji.")

    def restart_application(self) -> None:
        owner = self.owner
        try:
            launcher_path = Path(__file__).resolve().with_name("main.py")
            if not launcher_path.exists():
                raise FileNotFoundError(f"Launcher not found: {launcher_path}")
            subprocess.Popen([sys.executable, str(launcher_path), "--replace-existing-backend"])
            owner._close_to_tray_enabled = False
            QApplication.quit()
        except Exception as exc:
            QMessageBox.warning(owner, "Restart", str(exc))
