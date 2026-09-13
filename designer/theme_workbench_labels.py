"""Theme workbench labels for Theme Designer and JSON views."""

from __future__ import annotations

from collections.abc import Callable

TranslateFn = Callable[[str, str], str]


def refresh_theme_workbench_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels and tooltips for theme document and designer toolbar controls."""
    if hasattr(owner, "preview_guides_chk"):
        owner.preview_guides_chk.setText(translate("Show layer bounds", "Pokaż ramki warstw"))
    if hasattr(owner, "theme_doc_manual_json_label"):
        owner.theme_doc_manual_json_label.setText(translate("Manual JSON:", "JSON ręczny:"))
    if hasattr(owner, "theme_doc_open_external_btn"):
        owner.theme_doc_open_external_btn.setText(translate("Open JSON file…", "Otwórz plik JSON…"))
        owner.theme_doc_open_external_btn.setToolTip(
            translate(
                "Writes the theme with an English field guide and opens it in your default app. "
                "After saving in the editor, use Load theme. // and /* */ comments are ignored when loading.",
                "Zapisuje motyw z angielskim opisem pól i otwiera go w domyślnej aplikacji. "
                "Po zapisie w edytorze użyj „Wczytaj motyw”. Komentarze // oraz /* */ są pomijane przy wczytywaniu.",
            )
        )
    if hasattr(owner, "theme_doc_insert_guide_btn"):
        owner.theme_doc_insert_guide_btn.setText(translate("Insert field guide", "Wstaw opis pól"))
        owner.theme_doc_insert_guide_btn.setToolTip(
            translate(
                "Prepends the guide to the JSON tab (persist with Save / Load flow as usual).",
                "Wstawia opis na początku zakładki JSON (zapis jak przy zwykłym Zapisz / Wczytaj).",
            )
        )
    if hasattr(owner, "designer_open_json_btn"):
        owner.designer_open_json_btn.setText(translate("Open JSON…", "Otwórz JSON…"))
        owner.designer_open_json_btn.setToolTip(
            translate(
                "Save the theme file with a field guide and open it externally, then use Load theme.",
                "Zapisuje plik motywu z opisem pól i otwiera go na zewnątrz, potem użyj „Wczytaj motyw”.",
            )
        )
    if hasattr(owner, "designer_save_as_btn"):
        owner.designer_save_as_btn.setText(translate("Save As", "Zapisz jako"))
        owner.designer_save_as_btn.setToolTip(
            translate("Save the current theme as a new editable file.", "Zapisz bieżący motyw jako nowy plik do edycji.")
        )
    if hasattr(owner, "theme_doc_save_as_btn"):
        owner.theme_doc_save_as_btn.setText(translate("Save As", "Zapisz jako"))
    if hasattr(owner, "theme_doc_box"):
        owner.theme_doc_box.setTitle(translate("Theme", "Motyw"))
    if hasattr(owner, "theme_doc_path_caption"):
        owner.theme_doc_path_caption.setText(translate("Theme file:", "Plik motywu:"))
    if hasattr(owner, "theme_doc_sources_caption"):
        owner.theme_doc_sources_caption.setText(translate("Declared stats:", "Źródła danych:"))
    if hasattr(owner, "theme_doc_browse_btn"):
        owner.theme_doc_browse_btn.setText(translate("Browse theme…", "Wybierz motyw…"))
    if hasattr(owner, "theme_doc_use_selected_btn"):
        owner.theme_doc_use_selected_btn.setText(translate("From active theme", "Z aktywnego motywu"))
    if hasattr(owner, "theme_doc_load_btn"):
        owner.theme_doc_load_btn.setText(translate("Load", "Wczytaj"))
    if hasattr(owner, "theme_doc_save_btn"):
        owner.theme_doc_save_btn.setText(translate("Save", "Zapisz"))
    if hasattr(owner, "theme_doc_apply_btn"):
        owner.theme_doc_apply_btn.setText(translate("Apply", "Zastosuj"))
    if hasattr(owner, "theme_doc_stop_before_apply_chk"):
        owner.theme_doc_stop_before_apply_chk.setText(translate("Stop runtime before apply", "Zatrzymaj runtime przed apply"))
    if hasattr(owner, "theme_doc_resume_chk"):
        owner.theme_doc_resume_chk.setText(translate("Resume loop after apply", "Wznów loop po apply"))
    if hasattr(owner, "studio_toolbar_load_btn"):
        owner.studio_toolbar_load_btn.setText(translate("Load theme", "Wczytaj motyw"))
    if hasattr(owner, "studio_toolbar_save_btn"):
        owner.studio_toolbar_save_btn.setText(translate("Save theme", "Zapisz motyw"))
    if hasattr(owner, "studio_toolbar_preview_btn"):
        owner.studio_toolbar_preview_btn.setText(translate("Preview", "Podgląd"))
    if hasattr(owner, "studio_toolbar_apply_btn"):
        owner.studio_toolbar_apply_btn.setText(translate("Apply theme", "Zastosuj motyw"))
    if hasattr(owner, "studio_toolbar_reload_btn"):
        owner.studio_toolbar_reload_btn.setText(translate("JSON → Designer", "JSON → Projektant"))
    if hasattr(owner, "studio_toolbar_export_btn"):
        owner.studio_toolbar_export_btn.setText(translate("Designer → JSON", "Projektant → JSON"))
    if hasattr(owner, "studio_left_tabs"):
        owner.studio_left_tabs.setTabText(0, translate("Designer", "Projektant"))
        owner.studio_left_tabs.setTabText(1, translate("JSON", "JSON"))
    if hasattr(owner, "designer_theme_gauge_bar_label"):
        owner.designer_theme_gauge_bar_label.setText(
            translate("Default gauge preset (meta.gauge_style):", "Domyślny preset gauge (meta.gauge_style):")
        )
    if hasattr(owner, "designer_reload_btn"):
        owner.designer_reload_btn.setText(translate("Load theme", "Wczytaj motyw"))
    if hasattr(owner, "designer_write_btn"):
        owner.designer_write_btn.setText(translate("Save theme", "Zapisz motyw"))
    if hasattr(owner, "designer_animation_mode_btn"):
        owner.designer_animation_mode_btn.setText(translate("Animation", "Animacja"))
    if hasattr(owner, "designer_assets_toggle_btn"):
        owner.designer_assets_toggle_btn.setText(translate("Media", "Multimedia"))
    if hasattr(owner, "designer_preview_btn"):
        owner.designer_preview_btn.setText(translate("Preview", "Podgląd"))
    if hasattr(owner, "designer_apply_btn"):
        owner.designer_apply_btn.setText(translate("Apply theme", "Zastosuj motyw"))
    if hasattr(owner, "designer_theme_gauge_style_combo") and owner.designer_theme_gauge_style_combo.count() > 0:
        owner.designer_theme_gauge_style_combo.setItemText(
            0,
            translate("(default from theme name)", "(domyślny z nazwy motywu)"),
        )
