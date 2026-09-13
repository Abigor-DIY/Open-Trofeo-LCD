"""Label refresh helpers for the Theme Designer inspector forms."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel

from designer.inspector_animation import refresh_animation_inspector_labels

TranslateFn = Callable[[str, str], str]


def refresh_designer_inspector_form_labels(owner: Any, translate: TranslateFn) -> str:
    """Refresh row captions and related controls for inspector forms."""
    for attr, en, pl in (
        ("row_general_id", "Element ID", "ID elementu"),
        ("row_general_visible", "Visibility", "Widoczność"),
        ("row_general_locked", "Locked", "Zablokowany"),
        ("row_general_z", "Layer (Z)", "Warstwa"),
        ("row_music_tools", "Music tools", "Narzędzia muzyczne"),
        ("row_music_equalizer_bars", "EQ bars", "Słupki EQ"),
        ("row_music_equalizer_gap", "Bar gap", "Odstęp słupków"),
        ("row_music_equalizer_mirror", "Mirror mode", "Tryb lustrzany"),
        ("row_weather_city", "City", "Miasto"),
        ("row_weather_source", "Weather binding", "Dane pogody"),
        ("row_content_text", "Text", "Tekst"),
        ("row_content_label", "Label", "Etykieta"),
        ("row_content_source", "Data source", "Źródło"),
        ("row_content_format", "Value format", "Format wartości"),
        ("row_content_stat_display", "Display mode", "Tryb wyświetlania"),
        ("row_content_stat_range", "Range", "Zakres"),
        ("row_content_stat_show_value", "Show value text", "Tekst wartości"),
        ("row_appearance_font", "Font", "Czcionka"),
        ("row_appearance_font_style", "Style", "Styl"),
        ("row_appearance_align", "Alignment", "Wyrównanie"),
        ("row_appearance_color", "Color", "Kolor"),
        ("row_appearance_label_color", "Label color", "Kolor etykiety"),
        ("row_appearance_value_color", "Value color", "Kolor wartości"),
        ("row_appearance_track_color", "Track / chart background", "Kolor tła gauge / paska / wykresu"),
        ("row_appearance_fill_color", "Line / fill color", "Kolor linii / wypełnienia / wartości"),
        ("row_equalizer_style", "EQ style", "Styl EQ"),
        ("row_equalizer_threshold_color", "EQ high color", "Kolor wysokiego EQ"),
        ("row_sparkline_points", "History points", "Punkty historii"),
        ("row_sparkline_fill_opacity", "Fill opacity", "Przezrocz. wypełnienia"),
        ("row_sparkline_show_points", "Endpoint marker", "Punkt końcowy"),
        ("row_appearance_stroke_width", "Line / gauge stroke (0 = auto)", "Grubość linii / gauge (0 = auto)"),
        ("row_gauge_ring", "Ring diameter", "Średnica pierścienia"),
        ("row_gauge_value_layout", "Value layout", "Układ wartości"),
        ("row_gauge_preset", "Color preset", "Preset kolorów"),
        ("row_gauge_grad_low", "Arc: low color", "Łuk: kolor niski"),
        ("row_gauge_grad_mid", "Arc: mid color", "Łuk: środek"),
        ("row_gauge_grad_high", "Arc: high color", "Łuk: wysoki"),
        ("row_gauge_smooth", "Needle smoothing", "Wygładzanie igły"),
        ("row_gauge_match_value", "Value color matches arc", "Kolor wartości jak łuk"),
        ("row_gauge_inner_alpha", "Inner transparency", "Przezrocz. środka"),
        ("row_panel_fill", "Panel style", "Styl panelu"),
        ("row_panel_opacity", "Panel opacity", "Przezroczystość panelu"),
        ("row_panel_radius", "Corner radius", "Promień narożników"),
        ("row_geometry_x", "X", "X"),
        ("row_geometry_y", "Y", "Y"),
        ("row_geometry_w", "Width", "Szerokość"),
        ("row_geometry_h", "Height", "Wysokość"),
        ("row_geometry_group_bounds", "Group", "Grupa"),
        ("row_geometry_presets", "Presets", "Presety"),
        ("row_motion_enabled", "Motion", "Ruch"),
        ("row_motion_range", "Frame range", "Zakres klatek"),
        ("row_motion_target_x", "End X", "Koniec X"),
        ("row_motion_target_y", "End Y", "Koniec Y"),
        ("row_motion_target_opacity", "End opacity", "Końcowa przezr."),
        ("row_motion_actions", "Motion actions", "Akcje ruchu"),
        ("row_image_path", "Image file", "Plik obrazu"),
        ("row_image_fit", "Transform", "Transformacja"),
        ("row_image_opacity", "Opacity", "Przezroczystość"),
        ("row_image_rotation", "Rotation", "Obrót"),
        ("row_image_import", "Import", "Import"),
        ("row_image_actions", "Quick actions", "Szybkie akcje"),
        ("row_image_preview", "Preview", "Podgląd"),
        ("row_media_bg_mode", "Background mode", "Tryb tła"),
        ("row_media_bg_path", "File / import", "Plik / import"),
        ("row_media_bg_fit", "Fit", "Dopasowanie"),
        ("row_media_bg_opacity", "Opacity", "Przezroczystość"),
        ("row_media_bg_rotation", "Rotation", "Obrót"),
        ("row_media_bg_colors", "Colors", "Kolory"),
        ("row_media_bg_presets", "Presets", "Presety"),
        ("row_media_bg_texture", "Texture", "Tekstura"),
        ("row_media_bg_preview", "Background preview", "Podgląd tła"),
        ("row_animation_overview", "Animation", "Animacja"),
    ):
        widget = getattr(owner, attr, None)
        if isinstance(widget, QLabel):
            widget.setText(translate(en, pl))
    for attr, en, pl in (
        ("panel_fill_compact_label", "Fill", "Kolor"),
        ("panel_opacity_compact_label", "Opacity", "Przezr."),
        ("panel_radius_compact_label", "Radius", "Promień"),
        ("image_fit_compact_label", "Fit", "Dopas."),
        ("image_opacity_compact_label", "Opacity", "Przezr."),
        ("image_rotation_compact_label", "Rotation", "Obrót"),
        ("weather_source_compact_label", "Source", "Źródło"),
        ("weather_format_compact_label", "Format", "Format"),
    ):
        widget = getattr(owner, attr, None)
        if isinstance(widget, QLabel):
            widget.setText(translate(en, pl))
    refresh_animation_inspector_labels(owner, translate)
    for attr, en, pl in (
        ("motion_enabled_chk", "Animate element", "Animuj element"),
        ("motion_capture_current_btn", "Set end from current", "Ustaw koniec z bieżącej"),
        ("motion_remove_btn", "Remove motion", "Usuń ruch"),
        ("designer_path_browse_btn", "Browse…", "Wybierz…"),
        ("designer_path_prepare_btn", "Prepare", "Przygotuj"),
        ("designer_image_fullscreen_btn", "Fullscreen", "Ustaw fullscreen"),
        ("designer_image_left_half_btn", "Left half", "Lewa połowa"),
        ("designer_image_right_half_btn", "Right half", "Prawa połowa"),
        ("designer_image_reset_btn", "Reset frame", "Reset kadru"),
        ("designer_import_image_btn", "Import image into theme", "Importuj obraz do motywu"),
    ):
        widget = getattr(owner, attr, None)
        if widget is not None:
            widget.setText(translate(en, pl))
    preview_label = getattr(owner, "designer_image_preview_label", None)
    if preview_label is not None:
        pixmap = preview_label.pixmap()
        if pixmap is None or pixmap.isNull():
            preview_label.setText(translate("Image preview", "Podgląd obrazu"))
    gauge_placeholder = translate("[R,G,B,A] — optional, empty = from preset", "[R,G,B,A] — opcjonalnie, puste = z presetu")
    metric_placeholder = translate("[R,G,B,A] — optional", "[R,G,B,A] — opcjonalnie")
    for attr, placeholder in (
        ("designer_gauge_low_edit", gauge_placeholder),
        ("designer_gauge_mid_edit", metric_placeholder),
        ("designer_gauge_high_edit", metric_placeholder),
    ):
        widget = getattr(owner, attr, None)
        if widget is not None:
            widget.setPlaceholderText(placeholder)
    if hasattr(owner, "preview_tools_label"):
        owner.preview_tools_label.setText(translate("Mouse:", "Mysz:"))
    return translate("Background preview", "Podgląd tła")
