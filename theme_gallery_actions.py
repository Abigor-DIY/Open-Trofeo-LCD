"""Action controller for Theme Gallery cards and assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMenu, QMessageBox, QWidget

from theme_json_with_comments import parse_theme_json_text


class ThemeGalleryActionController:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def select_theme(self, theme_name: str, theme_item: dict[str, Any]) -> None:
        owner = self.owner
        owner.theme_combo.setCurrentText(theme_name)
        theme_type = str(theme_item.get("type", ""))
        path = str(theme_item.get("path", "")).strip()
        if theme_type == "theme-doc" and path:
            owner.theme_doc_path_edit.setText(path)
            owner.load_theme_doc()
            owner._go_designer()

    def set_startup_theme_preference(self, theme_name: str, enabled: bool) -> None:
        owner = self.owner
        if enabled:
            next_name = theme_name
        elif owner._startup_theme_name == theme_name:
            next_name = ""
        else:
            return
        if owner._startup_theme_name == next_name:
            return
        owner._startup_theme_name = next_name
        owner._startup_theme_applied = False
        owner._save_ui_state()
        owner._rebuild_library_theme_browser()
        if next_name:
            owner.append_log(f"[theme-startup] Ustawiono motyw startowy: {next_name}")
        else:
            owner.append_log("[theme-startup] Wyczyszczono motyw startowy.")

    def apply_startup_theme_if_needed(self) -> None:
        owner = self.owner
        if owner._startup_theme_applied:
            return
        theme_name = owner._startup_theme_name.strip()
        if not theme_name or theme_name not in owner.theme_items:
            return
        owner._startup_theme_applied = True
        owner._apply_runtime_theme_card(theme_name)

    def show_card_menu(self, theme_name: str, theme_item: dict[str, Any], anchor: QWidget) -> None:
        owner = self.owner
        menu = QMenu(owner)
        tr = owner._tr
        edit_action = menu.addAction(tr("Edit", "Edytuj"))
        preview_action = menu.addAction(tr("Preview", "Podgląd"))
        apply_action = menu.addAction(tr("Apply", "Zastosuj"))
        duplicate_action = menu.addAction(tr("Duplicate", "Duplikuj"))
        remove_action = menu.addAction(tr("Remove", "Usuń"))
        chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        if chosen == edit_action:
            self.select_theme(theme_name, theme_item)
        elif chosen == preview_action:
            owner._open_theme_preview_dialog(theme_name, theme_item)
        elif chosen == apply_action:
            owner._apply_runtime_theme_card(theme_name)
        elif chosen == duplicate_action:
            self.duplicate_theme_card(theme_name, theme_item)
        elif chosen == remove_action:
            owner._remove_runtime_theme_card(theme_name)

    def duplicate_theme_card(self, theme_name: str, theme_item: dict[str, Any]) -> None:
        owner = self.owner
        theme_type = str(theme_item.get("type", "")).strip()
        path = str(theme_item.get("path", "")).strip()
        if theme_type != "theme-doc" or not path:
            QMessageBox.information(
                owner,
                owner._tr("Duplicate theme", "Duplikowanie motywu"),
                owner._tr(
                    "Duplication is only available for saved editable theme documents.",
                    "Duplikowanie jest dostępne tylko dla zapisanych motywów edytowalnych.",
                ),
            )
            return
        try:
            src_path = owner._resolve_theme_asset_path(path)
            document = parse_theme_json_text(src_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("Plik motywu nie zawiera poprawnego dokumentu.")
            new_name = f"{theme_name} Kopia"
            document.setdefault("meta", {})
            document["meta"]["name"] = new_name
            out_path = src_path.with_name(f"{src_path.stem}_kopia{src_path.suffix}")
            idx = 2
            while out_path.exists():
                out_path = src_path.with_name(f"{src_path.stem}_kopia_{idx}{src_path.suffix}")
                idx += 1
            out_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            owner.api_call(
                "theme-add",
                "POST",
                "/v1/themes/add",
                {"name": new_name, "path": str(out_path), "raw_jpeg_passthrough": False},
                timeout=10.0,
            )
        except Exception as exc:
            QMessageBox.warning(owner, owner._tr("Duplicate theme", "Duplikowanie motywu"), str(exc))

    def use_asset_as_background(self, path: Path) -> None:
        owner = self.owner
        owner.bg_path_edit.setText(owner._theme_display_path(path))
        owner.bg_kind_combo.setCurrentText("image")
        animation = owner._current_animation_effect()
        animation["enabled"] = False
        owner._refresh_animation_controls()
        owner._set_image_preview_label(
            owner.background_preview_label,
            owner.bg_path_edit.text(),
            empty_text=owner._empty_background_preview_caption(),
        )
        owner.on_background_field_changed()

    def use_asset_as_image(self, path: Path) -> None:
        owner = self.owner
        combo_index = owner.designer_kind_combo.findData("images")
        if combo_index >= 0:
            owner.designer_kind_combo.setCurrentIndex(combo_index)
        if owner.theme_doc_model is None:
            owner.reload_designer_from_json()
            if owner.theme_doc_model is None:
                return
        items = owner._current_theme_items()
        owner.push_designer_history()
        new_item = owner._make_default_element("images")
        new_item["path"] = owner._theme_display_path(path)
        new_item["fit"] = "cover"
        canvas = owner.theme_doc_model.get("canvas", {}) if owner.theme_doc_model is not None else {}
        new_item["rect"] = [0, 0, int(canvas.get("width", 1920)), int(canvas.get("height", 462))]
        items.append(new_item)
        owner.write_designer_to_json()
        owner.refresh_designer_element_list()
        owner.designer_element_list.setCurrentRow(len(items) - 1)
        owner._set_image_preview_label(
            owner.designer_image_preview_label,
            new_item["path"],
            empty_text=owner._empty_image_preview_caption(),
        )
        owner.schedule_preview_theme_doc()
