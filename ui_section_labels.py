"""Shared UI section label refresh helpers."""

from __future__ import annotations

from collections.abc import Callable

TranslateFn = Callable[[str, str], str]


def refresh_shell_chrome_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels for the application shell, header and navigation."""
    if hasattr(owner, "brand_sub"):
        owner.brand_sub.setText("TROFEO LCD")
    if hasattr(owner, "sidebar_footer_note"):
        owner.sidebar_footer_note.setText("Open Trofeo LCD\nLinux Open Driver")
    if hasattr(owner, "chrome_box"):
        owner.chrome_box.setTitle(translate("Control", "Sterowanie"))
    if hasattr(owner, "shell_title_sub"):
        owner.shell_title_sub.setText(translate("LCD control and themes.", "Sterowanie LCD i motywami."))
    if hasattr(owner, "header_mode_label"):
        owner.header_mode_label.setText(translate("Mode", "Tryb"))
    if hasattr(owner, "header_scale_label"):
        owner.header_scale_label.setText(translate("Scale", "Skala"))
    if hasattr(owner, "header_conn_label"):
        owner.header_conn_label.setText(translate("Connection", "Połączenie"))
    if hasattr(owner, "header_device_label"):
        owner.header_device_label.setText(translate("Device", "Urządzenie"))
    if hasattr(owner, "header_language_label"):
        owner.header_language_label.setText(translate("Language", "Język"))
    if hasattr(owner, "header_donate_btn"):
        owner.header_donate_btn.setText(translate("Donate", "Donate"))
        owner.header_donate_btn.setToolTip(
            translate("Open GitHub Sponsors for Open Trofeo LCD", "Otwórz GitHub Sponsors dla Open Trofeo LCD")
        )
    if hasattr(owner, "header_ready_label"):
        current = owner.header_ready_label.text().strip().lower()
        if current in {"start", "ready", "gotowe"}:
            owner.header_ready_label.setText(translate("Ready", "Gotowe"))
        elif current in {"error", "błąd"}:
            owner.header_ready_label.setText(translate("Error", "Błąd"))
    if hasattr(owner, "header_connection_label"):
        current = owner.header_connection_label.text()
        if "Połączono" in current or "Connected" in current:
            owner.header_connection_label.setText(translate("● Connected", "● Połączono"))
        elif "Rozłączono" in current or "Disconnected" in current:
            owner.header_connection_label.setText(translate("● Disconnected", "● Rozłączono"))
    nav_attrs = (
        ("nav_library_btn", "🗂", "Theme Gallery", "Galeria motywów"),
        ("nav_designer_btn", "✎", "Theme Designer", "Projektant motywów"),
        ("nav_animation_studio_btn", "🎞", "Animation Studio", "Studio animacji"),
        ("nav_system_btn", "◉", "System", "System"),
        ("nav_logs_btn", "☰", "Logs", "Logi"),
        ("nav_config_btn", "⚙", "Configuration", "Konfiguracja"),
    )
    nav_meta = {}
    for attr, icon, en, pl in nav_attrs:
        widget = getattr(owner, attr, None)
        if widget is not None:
            nav_meta[widget] = (icon, translate(en, pl))
    if nav_meta:
        owner._nav_button_meta = nav_meta
    if hasattr(owner, "main_tabs"):
        owner.main_tabs.setTabText(0, translate("System", "System"))
        owner.main_tabs.setTabText(1, translate("Theme Designer", "Projektant motywów"))
        owner.main_tabs.setTabText(2, translate("Configuration", "Konfiguracja"))
        owner.main_tabs.setTabText(3, translate("Logs", "Logi"))
    if hasattr(owner, "studio_sections_tabs"):
        owner.studio_sections_tabs.setTabText(0, translate("Theme Gallery", "Galeria motywów"))
        owner.studio_sections_tabs.setTabText(1, translate("Designer", "Projektant"))
        owner.studio_sections_tabs.setTabText(2, translate("Animation Studio", "Studio animacji"))


def refresh_system_overview_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels for runtime/device/system overview panels."""
    if hasattr(owner, "endpoint_box"):
        owner.endpoint_box.setTitle(translate("Backend", "Backend"))
    if hasattr(owner, "control_box"):
        owner.control_box.setTitle(translate("Device control", "Kontrola urządzenia"))
    if hasattr(owner, "runtime_hero_text_label"):
        owner.runtime_hero_text_label.setText(
            translate(
                "Control the panel like a native Plasma app: start the runtime, push single frames "
                "and manage themes from clear cards instead of raw fields.",
                "Steruj panelem jak natywną aplikację Plasma: uruchom runtime, wyślij pojedyncze klatki "
                "i zarządzaj motywami z czytelnych kart zamiast surowych pól.",
            )
        )
    if hasattr(owner, "runtime_sections_tabs"):
        owner.runtime_sections_tabs.setTabText(0, translate("Device", "Urządzenie"))
        owner.runtime_sections_tabs.setTabText(1, translate("Image", "Obraz"))
        owner.runtime_sections_tabs.setTabText(2, translate("Themes", "Motywy"))
    if hasattr(owner, "work_box"):
        owner.work_box.setTitle(translate("Single image", "Pojedynczy obraz"))
    if hasattr(owner, "cfg_box"):
        owner.cfg_box.setTitle(translate("Playback settings", "Ustawienia odtwarzania"))
    if hasattr(owner, "status_box"):
        owner.status_box.setTitle(translate("System monitor", "Monitor systemu"))
    if hasattr(owner, "runtime_legacy_theme_box"):
        owner.runtime_legacy_theme_box.setTitle(translate("Theme library", "Biblioteka motywów"))
    if hasattr(owner, "runtime_theme_cards_box"):
        owner.runtime_theme_cards_box.setTitle(translate("Theme cards", "Karty motywów"))
    if hasattr(owner, "system_intro_text_label"):
        owner.system_intro_text_label.setText(
            translate(
                "This tab shows backend status, device state and basic host metrics. "
                "Quick actions use the same live API endpoints as before.",
                "Ta zakładka pokazuje status backendu, stan urządzenia i podstawowe metryki hosta. "
                "Szybkie akcje korzystają z tych samych endpointów API co wcześniej.",
            )
        )
    if hasattr(owner, "backend_status_box"):
        owner.backend_status_box.setTitle(translate("Backend status", "Status backendu"))
    for attr, en, pl in (
        ("system_api_status_title", "API Server", "Serwer API"),
        ("system_ws_status_title", "WebSocket", "WebSocket"),
        ("system_lcd_status_title", "LCD Daemon", "Demon LCD"),
        ("system_queue_status_title", "Queue Worker", "Worker kolejki"),
        ("system_theme_engine_title", "Theme Engine", "Silnik motywów"),
        ("system_backup_title", "Auto Backup", "Auto backup"),
        ("system_cpu_title", "CPU", "CPU"),
        ("system_mem_title", "RAM", "RAM"),
        ("system_disk_title", "DISK", "DYSK"),
        ("system_temp_title", "TEMP", "TEMP"),
    ):
        widget = getattr(owner, attr, None)
        if widget is not None:
            widget.setText(translate(en, pl))
    if hasattr(owner, "system_info_box"):
        owner.system_info_box.setTitle(translate("System information", "Informacje o systemie"))
    if hasattr(owner, "resources_box"):
        owner.resources_box.setTitle(translate("System resources", "Zasoby systemu"))
    if hasattr(owner, "runtime_dashboard_device_box"):
        owner.runtime_dashboard_device_box.setTitle(translate("Network & device", "Sieć i urządzenie"))
    if hasattr(owner, "system_events_box"):
        owner.system_events_box.setTitle(translate("System events", "Zdarzenia systemowe"))
    if hasattr(owner, "system_events_header_labels") and len(getattr(owner, "system_events_header_labels", [])) == 4:
        hdr = owner.system_events_header_labels
        hdr[0].setText(translate("Time", "Czas"))
        hdr[1].setText(translate("Level", "Poziom"))
        hdr[2].setText(translate("Source", "Źródło"))
        hdr[3].setText(translate("Message", "Komunikat"))
    if hasattr(owner, "system_quick_actions_box"):
        owner.system_quick_actions_box.setTitle(translate("Quick actions", "Szybkie akcje"))
    if hasattr(owner, "system_restart_backend_btn"):
        owner.system_restart_backend_btn.setText(translate("Restart backend", "Restart backendu"))
    if hasattr(owner, "system_restart_service_btn"):
        owner.system_restart_service_btn.setText(translate("Restart service", "Restart usługi"))
    if hasattr(owner, "system_refresh_status_btn"):
        owner.system_refresh_status_btn.setText(translate("Refresh status", "Odśwież status"))
    if hasattr(owner, "system_export_logs_btn"):
        owner.system_export_logs_btn.setText(translate("Export logs", "Eksport logów"))
    if hasattr(owner, "system_diagnostic_btn"):
        owner.system_diagnostic_btn.setText(translate("Diagnostics", "Diagnostyka"))


def refresh_configuration_action_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels for Configuration cards and action buttons."""
    if hasattr(owner, "appearance_box"):
        owner.appearance_box.setTitle(translate("App Appearance", "Wygląd Aplikacji"))
    if hasattr(owner, "paths_box"):
        owner.paths_box.setTitle(translate("Paths and Integration", "Ścieżki i Integracja"))
    if hasattr(owner, "audio_eq_box"):
        owner.audio_eq_box.setTitle(translate("Audio EQ", "Korektor audio"))
    if hasattr(owner, "cfg_audio_eq_apply_btn"):
        owner.cfg_audio_eq_apply_btn.setText(translate("Apply EQ", "Zastosuj EQ"))
    if hasattr(owner, "quick_cfg_box"):
        owner.quick_cfg_box.setTitle(translate("Quick Actions", "Szybkie Akcje"))
    if hasattr(owner, "automation_tools_box"):
        owner.automation_tools_box.setTitle(translate("Automation and Bundles", "Automatyzacja i Bundles"))
    for attr, en, pl in (
        ("cfg_cancel_btn", "Cancel", "Anuluj"),
        ("cfg_apply_btn", "Apply", "Zastosuj"),
        ("cfg_save_btn", "Save Settings", "Zapisz ustawienia"),
        ("cfg_reset_btn", "Restore Defaults", "Przywróć domyślne"),
        ("cfg_export_btn", "Export Configuration", "Eksportuj konfigurację"),
        ("cfg_import_btn", "Import Configuration", "Importuj konfigurację"),
        ("cfg_clear_cache_btn", "Clear Cache", "Wyczyść cache"),
        ("cfg_restart_app_btn", "Restart Whole App", "Uruchom całą aplikację ponownie"),
        ("cfg_usb_recovery_btn", "LCD USB Recovery (sudo)", "Recovery USB LCD (sudo)"),
        ("usb_recovery_btn", "Run USB recovery...", "Uruchom recovery USB..."),
    ):
        widget = getattr(owner, attr, None)
        if widget is not None:
            widget.setText(translate(en, pl))
    if hasattr(owner, "cfg_usb_recovery_note_label"):
        owner.cfg_usb_recovery_note_label.setText(
            translate(
                "For a frozen LCD after deep sleep: run USB recovery from here or from a terminal. "
                "If it still shows an old frame, reboot usually helps; full power-off is stronger than a warm reboot.",
                "Gdy LCD zamarznie po głębokim uśpieniu: uruchom recovery USB tutaj albo z terminala. "
                "Jeżeli nadal pokazuje starą klatkę, reboot zwykle pomaga; pełne wyłączenie zasilania jest mocniejsze niż ciepły restart.",
            )
        )
    if hasattr(owner, "usb_recovery_hint_label"):
        owner.usb_recovery_hint_label.setText(
            translate(
                "Use after deep suspend, USB timeout or frozen clock/EQ. Requires sudo and briefly resets the Trofeo LCD USB device. "
                "A full PC reboot usually helps too; if USB remains powered in standby, power off the PC for a few seconds.",
                "Użyj po głębokim uśpieniu, timeoutach USB albo zamrożonym zegarze/EQ. Wymaga sudo i krótko resetuje urządzenie USB Trofeo LCD. "
                "Pełny reboot PC zwykle też pomaga; jeżeli USB zostaje zasilone w standby, wyłącz PC na kilka sekund.",
            )
        )


def refresh_config_weather_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels for the Configuration weather panel."""
    if hasattr(owner, "config_intro_text_label"):
        owner.config_intro_text_label.setText(
            translate(
                "Configuration centralizes interface settings, LCD preferences and integrations in one place. "
                "App theme management now lives here instead of the top control bar.",
                "Konfiguracja grupuje ustawienia interfejsu, preferencje LCD i integracje w jednym miejscu. "
                "Motyw aplikacji jest ustawiany tutaj zamiast na górnym pasku.",
            )
        )
    if hasattr(owner, "cfg_weather_refresh_now_btn"):
        owner.cfg_weather_refresh_now_btn.setText(translate("Refresh weather", "Odśwież pogodę"))
    if hasattr(owner, "weather_box"):
        owner.weather_box.setTitle(translate("Weather", "Pogoda"))
    if hasattr(owner, "cfg_weather_city_search_edit"):
        owner.cfg_weather_city_search_edit.setPlaceholderText(translate("Search city, e.g. Warsaw", "Szukaj miasta, np. Warszawa"))
    if hasattr(owner, "cfg_weather_search_btn") and owner.cfg_weather_search_btn.isEnabled():
        owner.cfg_weather_search_btn.setText(translate("Search", "Szukaj"))
    if hasattr(owner, "cfg_weather_apply_btn"):
        owner.cfg_weather_apply_btn.setText(translate("Apply weather", "Zastosuj pogodę"))


def refresh_theme_gallery_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels for the theme gallery and browser controls."""
    if hasattr(owner, "library_summary_label"):
        owner.library_summary_label.setText(translate("Theme gallery quick actions", "Szybkie akcje galerii motywów"))
    if hasattr(owner, "library_import_ttcr_btn"):
        owner.library_import_ttcr_btn.setText(translate("Import TTCR", "Import TTCR"))
    if hasattr(owner, "library_refresh_btn"):
        owner.library_refresh_btn.setText(translate("Refresh", "Odśwież"))
    if hasattr(owner, "new_theme_create_btn"):
        owner.new_theme_create_btn.setText(translate("Create Theme", "Utwórz motyw"))
    if hasattr(owner, "new_theme_advanced_btn"):
        owner.new_theme_advanced_btn.setText(translate("File Settings", "Ustawienia pliku"))
    if hasattr(owner, "new_theme_hint_label"):
        owner.new_theme_hint_label.setText(
            translate(
                "Enter a name and style. The theme file path will be suggested automatically.",
                "Podaj nazwę i styl. Plik motywu zostanie zaproponowany automatycznie.",
            )
        )
    if hasattr(owner, "new_theme_name_edit"):
        owner.new_theme_name_edit.setPlaceholderText(translate("e.g. My Dashboard", "Np. Mój dashboard"))
    if hasattr(owner, "theme_browser_box"):
        owner.theme_browser_box.setTitle(translate("Themes", "Motywy"))
    if hasattr(owner, "asset_gallery_box"):
        owner.asset_gallery_box.setTitle(translate("Theme Assets", "Zasoby motywu"))
    if hasattr(owner, "library_current_theme_label"):
        current = getattr(owner, "theme_combo", None)
        current_name = current.currentText().strip() if current is not None else ""
        owner.library_current_theme_label.setText(
            translate(f"Currently selected: {current_name}", f"Aktualnie wybrany: {current_name}")
            if current_name
            else translate("No active theme.", "Brak aktywnego motywu.")
        )
    if hasattr(owner, "theme_browser_controls_search_label"):
        owner.theme_browser_controls_search_label.setText(translate("Search", "Szukaj"))
    if hasattr(owner, "theme_browser_controls_type_label"):
        owner.theme_browser_controls_type_label.setText(translate("Type", "Typ"))
    if hasattr(owner, "theme_browser_controls_sort_label"):
        owner.theme_browser_controls_sort_label.setText(translate("Sort", "Sortuj"))


def refresh_log_panel_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels for the logs view controls."""
    if hasattr(owner, "log_panel_box"):
        owner.log_panel_box.setTitle(translate("API & application logs", "Logi API i aplikacji"))
    if hasattr(owner, "log_filter_edit"):
        owner.log_filter_edit.setPlaceholderText(translate("Filter logs…", "Filtr logów…"))
    if hasattr(owner, "log_only_errors_chk"):
        owner.log_only_errors_chk.setText(translate("Errors only", "Tylko błędy"))
    if hasattr(owner, "log_hide_status_chk"):
        owner.log_hide_status_chk.setText(translate("Hide status lines", "Ukryj status"))
    if hasattr(owner, "log_copy_btn"):
        owner.log_copy_btn.setText(translate("Copy view", "Kopiuj widok"))
    if hasattr(owner, "log_copy_selection_btn"):
        owner.log_copy_selection_btn.setText(translate("Copy selection", "Kopiuj zaznaczenie"))
    if hasattr(owner, "log_clear_btn"):
        owner.log_clear_btn.setText(translate("Clear", "Wyczyść"))
    if hasattr(owner, "log_search_label"):
        owner.log_search_label.setText(translate("Search:", "Szukaj:"))
