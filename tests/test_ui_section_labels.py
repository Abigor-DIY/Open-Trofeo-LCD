import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QGroupBox, QLabel, QLineEdit, QPushButton, QTabWidget, QWidget

from ui_section_labels import (
    refresh_config_weather_labels,
    refresh_configuration_action_labels,
    refresh_log_panel_labels,
    refresh_shell_chrome_labels,
    refresh_system_overview_labels,
    refresh_theme_gallery_labels,
)

_APP = QApplication.instance() or QApplication([])


class UiSectionLabelTests(unittest.TestCase):
    def test_refresh_shell_chrome_labels_updates_header_navigation_and_tabs(self) -> None:
        main_tabs = QTabWidget()
        studio_tabs = QTabWidget()
        for tab in (main_tabs, studio_tabs):
            for title in ("old1", "old2", "old3", "old4"):
                tab.addTab(QWidget(), title)
        owner = SimpleNamespace(
            brand_sub=QLabel("old"),
            sidebar_footer_note=QLabel("old"),
            chrome_box=QGroupBox("old"),
            shell_title_sub=QLabel("old"),
            header_mode_label=QLabel("old"),
            header_scale_label=QLabel("old"),
            header_conn_label=QLabel("old"),
            header_device_label=QLabel("old"),
            header_language_label=QLabel("old"),
            header_donate_btn=QPushButton("old"),
            header_ready_label=QLabel("Ready"),
            header_connection_label=QLabel("● Connected"),
            nav_library_btn=QPushButton("old"),
            nav_designer_btn=QPushButton("old"),
            nav_animation_studio_btn=QPushButton("old"),
            nav_system_btn=QPushButton("old"),
            nav_logs_btn=QPushButton("old"),
            nav_config_btn=QPushButton("old"),
            main_tabs=main_tabs,
            studio_sections_tabs=studio_tabs,
        )

        refresh_shell_chrome_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.brand_sub.text(), "TROFEO LCD")
        self.assertEqual(owner.chrome_box.title(), "Sterowanie")
        self.assertEqual(owner.header_ready_label.text(), "Gotowe")
        self.assertEqual(owner.header_connection_label.text(), "● Połączono")
        self.assertEqual(owner.header_language_label.text(), "Język")
        self.assertEqual(owner.header_donate_btn.toolTip(), "Otwórz GitHub Sponsors dla Open Trofeo LCD")
        self.assertEqual(owner._nav_button_meta[owner.nav_library_btn], ("🗂", "Galeria motywów"))
        self.assertEqual(owner.main_tabs.tabText(1), "Projektant motywów")
        self.assertEqual(owner.studio_sections_tabs.tabText(2), "Studio animacji")

    def test_refresh_system_overview_labels_updates_runtime_and_system_controls(self) -> None:
        tabs = QTabWidget()
        for title in ("old1", "old2", "old3"):
            tabs.addTab(QWidget(), title)
        owner = SimpleNamespace(
            endpoint_box=QGroupBox("old"),
            control_box=QGroupBox("old"),
            runtime_hero_text_label=QLabel("old"),
            runtime_sections_tabs=tabs,
            work_box=QGroupBox("old"),
            cfg_box=QGroupBox("old"),
            status_box=QGroupBox("old"),
            runtime_legacy_theme_box=QGroupBox("old"),
            runtime_theme_cards_box=QGroupBox("old"),
            system_intro_text_label=QLabel("old"),
            backend_status_box=QGroupBox("old"),
            system_api_status_title=QLabel("old"),
            system_theme_engine_title=QLabel("old"),
            system_cpu_title=QLabel("old"),
            system_disk_title=QLabel("old"),
            system_info_box=QGroupBox("old"),
            resources_box=QGroupBox("old"),
            runtime_dashboard_device_box=QGroupBox("old"),
            system_events_box=QGroupBox("old"),
            system_events_header_labels=[QLabel("old") for _ in range(4)],
            system_quick_actions_box=QGroupBox("old"),
            system_restart_backend_btn=QPushButton("old"),
            system_restart_service_btn=QPushButton("old"),
            system_refresh_status_btn=QPushButton("old"),
            system_export_logs_btn=QPushButton("old"),
            system_diagnostic_btn=QPushButton("old"),
        )

        refresh_system_overview_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.control_box.title(), "Kontrola urządzenia")
        self.assertIn("Steruj panelem", owner.runtime_hero_text_label.text())
        self.assertEqual(owner.runtime_sections_tabs.tabText(2), "Motywy")
        self.assertEqual(owner.runtime_legacy_theme_box.title(), "Biblioteka motywów")
        self.assertIn("status backendu", owner.system_intro_text_label.text())
        self.assertEqual(owner.system_api_status_title.text(), "Serwer API")
        self.assertEqual(owner.system_theme_engine_title.text(), "Silnik motywów")
        self.assertEqual(owner.system_disk_title.text(), "DYSK")
        self.assertEqual(owner.runtime_dashboard_device_box.title(), "Sieć i urządzenie")
        self.assertEqual([label.text() for label in owner.system_events_header_labels], ["Czas", "Poziom", "Źródło", "Komunikat"])
        self.assertEqual(owner.system_restart_backend_btn.text(), "Restart backendu")
        self.assertEqual(owner.system_diagnostic_btn.text(), "Diagnostyka")

    def test_refresh_config_weather_labels_updates_weather_controls(self) -> None:
        owner = SimpleNamespace(
            config_intro_text_label=QLabel("old"),
            cfg_weather_refresh_now_btn=QPushButton("old"),
            weather_box=QGroupBox("old"),
            cfg_weather_city_search_edit=QLineEdit(),
            cfg_weather_search_btn=QPushButton("old"),
            cfg_weather_apply_btn=QPushButton("old"),
        )

        refresh_config_weather_labels(owner, lambda _en, pl: pl)

        self.assertIn("Zatwierdzaj zmiany", owner.config_intro_text_label.text())
        self.assertEqual(owner.cfg_weather_refresh_now_btn.text(), "Odśwież pogodę")
        self.assertEqual(owner.weather_box.title(), "Pogoda")
        self.assertEqual(owner.cfg_weather_city_search_edit.placeholderText(), "Szukaj miasta, np. Warszawa")
        self.assertEqual(owner.cfg_weather_search_btn.text(), "Szukaj")
        self.assertEqual(owner.cfg_weather_apply_btn.text(), "Zastosuj pogodę")

    def test_refresh_config_weather_labels_keeps_busy_search_text(self) -> None:
        owner = SimpleNamespace(cfg_weather_search_btn=QPushButton("Searching…"))
        owner.cfg_weather_search_btn.setEnabled(False)

        refresh_config_weather_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.cfg_weather_search_btn.text(), "Searching…")

    def test_refresh_configuration_action_labels_updates_action_controls(self) -> None:
        owner = SimpleNamespace(
            appearance_box=QGroupBox("old"),
            paths_box=QGroupBox("old"),
            audio_eq_box=QGroupBox("old"),
            cfg_audio_eq_apply_btn=QPushButton("old"),
            quick_cfg_box=QGroupBox("old"),
            automation_tools_box=QGroupBox("old"),
            cfg_cancel_btn=QPushButton("old"),
            cfg_apply_btn=QPushButton("old"),
            cfg_save_btn=QPushButton("old"),
            cfg_reset_btn=QPushButton("old"),
            cfg_export_btn=QPushButton("old"),
            cfg_import_btn=QPushButton("old"),
            cfg_clear_cache_btn=QPushButton("old"),
            cfg_restart_app_btn=QPushButton("old"),
            cfg_usb_recovery_btn=QPushButton("old"),
            cfg_usb_recovery_note_label=QLabel("old"),
            usb_recovery_btn=QPushButton("old"),
            usb_recovery_hint_label=QLabel("old"),
        )

        refresh_configuration_action_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.appearance_box.title(), "Wygląd Aplikacji")
        self.assertEqual(owner.audio_eq_box.title(), "Korektor audio")
        self.assertEqual(owner.quick_cfg_box.title(), "Szybkie Akcje")
        self.assertEqual(owner.cfg_save_btn.text(), "Zapisz ustawienia")
        self.assertEqual(owner.cfg_restart_app_btn.text(), "Uruchom całą aplikację ponownie")
        self.assertIn("głębokim uśpieniu", owner.cfg_usb_recovery_note_label.text())
        self.assertEqual(owner.usb_recovery_btn.text(), "Uruchom recovery USB...")

    def test_refresh_theme_gallery_labels_updates_gallery_controls(self) -> None:
        theme_combo = QComboBox()
        theme_combo.addItem("Orbital Relay")
        owner = SimpleNamespace(
            library_summary_label=QLabel("old"),
            library_import_ttcr_btn=QPushButton("old"),
            library_refresh_btn=QPushButton("old"),
            new_theme_create_btn=QPushButton("old"),
            new_theme_advanced_btn=QPushButton("old"),
            new_theme_hint_label=QLabel("old"),
            new_theme_name_edit=QLineEdit(),
            theme_browser_box=QGroupBox("old"),
            asset_gallery_box=QGroupBox("old"),
            library_current_theme_label=QLabel("old"),
            theme_combo=theme_combo,
            theme_browser_controls_search_label=QLabel("old"),
            theme_browser_controls_type_label=QLabel("old"),
            theme_browser_controls_sort_label=QLabel("old"),
        )

        refresh_theme_gallery_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.library_summary_label.text(), "Szybkie akcje galerii motywów")
        self.assertEqual(owner.library_refresh_btn.text(), "Odśwież")
        self.assertEqual(owner.new_theme_create_btn.text(), "Utwórz motyw")
        self.assertEqual(owner.new_theme_name_edit.placeholderText(), "Np. Mój dashboard")
        self.assertEqual(owner.theme_browser_box.title(), "Motywy")
        self.assertEqual(owner.asset_gallery_box.title(), "Zasoby motywu")
        self.assertEqual(owner.library_current_theme_label.text(), "Aktualnie wybrany: Orbital Relay")
        self.assertEqual(owner.theme_browser_controls_type_label.text(), "Typ")

    def test_refresh_log_panel_labels_updates_log_controls(self) -> None:
        owner = SimpleNamespace(
            log_panel_box=QGroupBox("old"),
            log_filter_edit=QLineEdit(),
            log_only_errors_chk=QCheckBox("old"),
            log_hide_status_chk=QCheckBox("old"),
            log_copy_btn=QPushButton("old"),
            log_copy_selection_btn=QPushButton("old"),
            log_clear_btn=QPushButton("old"),
            log_search_label=QLabel("old"),
        )

        refresh_log_panel_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.log_panel_box.title(), "Logi API i aplikacji")
        self.assertEqual(owner.log_filter_edit.placeholderText(), "Filtr logów…")
        self.assertEqual(owner.log_only_errors_chk.text(), "Tylko błędy")
        self.assertEqual(owner.log_hide_status_chk.text(), "Ukryj status")
        self.assertEqual(owner.log_copy_btn.text(), "Kopiuj widok")
        self.assertEqual(owner.log_copy_selection_btn.text(), "Kopiuj zaznaczenie")
        self.assertEqual(owner.log_clear_btn.text(), "Wyczyść")
        self.assertEqual(owner.log_search_label.text(), "Szukaj:")


if __name__ == "__main__":
    unittest.main()
