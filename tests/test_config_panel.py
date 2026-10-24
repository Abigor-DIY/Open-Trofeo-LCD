import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from config_panel import (
    ConfigAudioEqCallbacks,
    ConfigActionCallbacks,
    ConfigAutomationCallbacks,
    ConfigGamingFpsCallbacks,
    ConfigPanelCallbacks,
    ConfigurationPanel,
    ConfigQuickActionCallbacks,
    ConfigWeatherCallbacks,
    bind_config_panel_controls,
    build_config_appearance_box,
    build_config_action_row,
    build_config_audio_eq_box,
    build_config_automation_box,
    build_config_gaming_fps_box,
    build_config_lcd_preferences_box,
    build_config_panel_callbacks,
    build_config_panel_controls,
    build_config_quick_actions_box,
    build_config_runtime_paths_box,
    build_config_weather_box,
)


class ConfigPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_build_config_appearance_box_creates_expected_controls(self) -> None:
        controls = build_config_appearance_box(["Plasma Blue", "Dark"])

        self.assertEqual(controls.box.objectName(), "configCardBox")
        self.assertEqual(controls.theme_combo.count(), 2)
        self.assertEqual(controls.mode_combo.currentText(), "Dark")
        self.assertEqual(controls.scale_combo.currentText(), "70%")
        self.assertEqual(controls.font_scale_slider.value(), 100)
        self.assertTrue(controls.animations_chk.isChecked())

    def test_build_config_lcd_preferences_box_keeps_brightness_disabled_note(self) -> None:
        controls = build_config_lcd_preferences_box()

        self.assertEqual(controls.box.title(), "LCD Preferences")
        self.assertIn("Brightness control is disabled", controls.note_label.text())

    def test_build_config_gaming_fps_box_wires_actions_and_command(self) -> None:
        calls: list[str] = []
        controls = build_config_gaming_fps_box(
            steam_launch_options='OPEN_TROFEO_GAME_NAME="Game" %command%',
            callbacks=ConfigGamingFpsCallbacks(
                configure_layer=lambda: calls.append("setup"),
                refresh_status=lambda: calls.append("refresh"),
                copy_steam_command=lambda: calls.append("copy"),
                auto_theme_changed=lambda: calls.append("auto-theme"),
                refresh_vrr=lambda: calls.append("vrr-refresh"),
                set_vrr_policy=lambda policy: calls.append(f"vrr:{policy}"),
            ),
        )

        controls.setup_btn.click()
        controls.refresh_btn.click()
        controls.copy_steam_command_btn.click()
        controls.auto_theme_chk.setChecked(True)
        controls.auto_theme_combo.addItem("Neon Frame Arena")
        controls.auto_theme_combo.setCurrentText("Neon Frame Arena")
        controls.auto_theme_restore_on_fps_loss_chk.setChecked(True)
        controls.auto_theme_fps_loss_delay_spin.setValue(15)
        controls.vrr_automatic_btn.click()
        controls.vrr_off_btn.click()
        controls.vrr_refresh_btn.click()

        self.assertIn("setup", calls)
        self.assertIn("refresh", calls)
        self.assertIn("copy", calls)
        self.assertIn("auto-theme", calls)
        self.assertIn("vrr:automatic", calls)
        self.assertIn("vrr:never", calls)
        self.assertIn("vrr-refresh", calls)
        self.assertIn("OPEN_TROFEO_GAME_NAME", controls.steam_command_edit.text())
        self.assertTrue(controls.steam_command_edit.isReadOnly())
        self.assertIn("No FPS session", controls.metrics_label.text())
        self.assertTrue(controls.log_path_edit.isReadOnly())
        self.assertEqual(controls.auto_theme_fps_loss_delay_spin.value(), 15)

    def test_build_config_audio_eq_box_wires_dirty_and_apply(self) -> None:
        calls: list[str] = []
        controls = build_config_audio_eq_box(
            ConfigAudioEqCallbacks(
                apply_eq=lambda: calls.append("apply"),
                mark_dirty=lambda: calls.append("dirty"),
            )
        )

        controls.input_combo.activated.emit(1)
        controls.profile_combo.activated.emit(1)
        controls.sensitivity_spin.setValue(125)
        controls.apply_btn.click()

        self.assertIn("dirty", calls)
        self.assertEqual(calls[-1], "apply")
        self.assertEqual(controls.input_combo.itemData(0), "auto")
        self.assertEqual(controls.profile_combo.itemData(0), "responsive")

    def test_build_config_weather_box_wires_search_apply_and_refresh(self) -> None:
        calls: list[str] = []
        controls = build_config_weather_box(
            ConfigWeatherCallbacks(
                search_city=lambda: calls.append("search"),
                apply_selected_city=lambda index: calls.append(f"select:{index}"),
                apply_weather=lambda: calls.append("apply"),
                refresh_weather=lambda: calls.append("refresh"),
            )
        )

        controls.search_btn.click()
        controls.city_search_edit.returnPressed.emit()
        controls.results_combo.addItem("Warsaw", {"lat": 52.2})
        controls.results_combo.setCurrentIndex(1)
        controls.apply_btn.click()
        controls.refresh_now_btn.click()

        self.assertEqual(controls.results_combo.itemData(0), None)
        self.assertEqual(controls.refresh_spin.value(), 900)
        self.assertEqual(controls.temperature_unit_combo.currentData(), "celsius")
        controls.temperature_unit_combo.setCurrentIndex(1)
        self.assertEqual(controls.temperature_unit_combo.currentData(), "fahrenheit")
        self.assertIn("search", calls)
        self.assertIn("select:1", calls)
        self.assertEqual(calls[-2:], ["apply", "refresh"])

    def test_build_config_quick_actions_box_wires_callbacks(self) -> None:
        calls: list[str] = []
        controls = build_config_quick_actions_box(
            ConfigQuickActionCallbacks(
                reset_defaults=lambda: calls.append("reset"),
                export_config=lambda: calls.append("export"),
                import_config=lambda: calls.append("import"),
                clear_cache=lambda: calls.append("clear"),
                restart_app=lambda: calls.append("restart"),
                usb_recovery=lambda: calls.append("usb"),
            )
        )

        buttons = {button.text(): button for button in controls.box.findChildren(QPushButton)}
        buttons["LCD USB Recovery (sudo)"].click()
        buttons["Restore Defaults"].click()
        buttons["Export Configuration"].click()
        buttons["Import Configuration"].click()
        buttons["Clear Cache"].click()
        buttons["Restart Application"].click()

        self.assertEqual(calls, ["usb", "reset", "export", "import", "clear", "restart"])
        self.assertIn("deep sleep", controls.usb_recovery_note_label.text())

    def test_build_config_runtime_paths_box_marks_paths_readonly(self) -> None:
        controls = build_config_runtime_paths_box(
            app_path="/app",
            theme_path="/themes",
            state_path="/state",
            fps_socket_path="/run/fps.sock",
        )

        self.assertTrue(controls.app_path_edit.isReadOnly())
        self.assertEqual(controls.theme_path_edit.text(), "/themes")
        self.assertEqual(controls.fps_socket_path_edit.objectName(), "readonlyPathEdit")

    def test_build_config_automation_box_wires_playlist_and_bundle_actions(self) -> None:
        calls: list[str] = []
        controls = build_config_automation_box(
            ConfigAutomationCallbacks(
                add_playlist_item=lambda: calls.append("add"),
                remove_playlist_item=lambda: calls.append("remove"),
                start_playlist=lambda: calls.append("start"),
                stop_playlist=lambda: calls.append("stop"),
                browse_bundle_path=lambda: calls.append("browse"),
                save_bundle=lambda: calls.append("save"),
                load_bundle=lambda: calls.append("load"),
            )
        )

        controls.playlist_add_btn.click()
        controls.playlist_remove_btn.click()
        controls.playlist_start_btn.click()
        controls.playlist_stop_btn.click()
        controls.bundle_browse_btn.click()
        controls.bundle_save_btn.click()
        controls.bundle_load_btn.click()

        self.assertEqual(calls, ["add", "remove", "start", "stop", "browse", "save", "load"])
        self.assertEqual(controls.bundle_path_edit.text(), ".trofeo-bundle.json")
        self.assertEqual(controls.playlist_duration_spin.value(), 15.0)

    def test_build_config_action_row_wires_cancel_apply_save(self) -> None:
        calls: list[str] = []
        controls = build_config_action_row(
            ConfigActionCallbacks(
                cancel=lambda: calls.append("cancel"),
                apply=lambda: calls.append("apply"),
                save=lambda: calls.append("save"),
            )
        )

        controls.cancel_btn.click()
        controls.apply_btn.click()
        controls.save_btn.click()

        self.assertEqual(calls, ["cancel", "apply", "save"])
        self.assertEqual(controls.apply_btn.objectName(), "secondaryAccentButton")
        self.assertEqual(controls.save_btn.objectName(), "primaryButton")

    def test_build_config_panel_controls_composes_grid_and_callbacks(self) -> None:
        calls: list[str] = []
        controls = build_config_panel_controls(
            theme_names=["Plasma Blue"],
            steam_launch_options='OPEN_TROFEO_GAME_NAME="Game" %command%',
            app_path="/app",
            theme_path="/themes",
            state_path="/state",
            fps_socket_path="/run/fps.sock",
            callbacks=ConfigPanelCallbacks(
                gaming_fps=ConfigGamingFpsCallbacks(
                    configure_layer=lambda: calls.append("setup"),
                    refresh_status=lambda: calls.append("refresh-fps"),
                    copy_steam_command=lambda: calls.append("copy"),
                    auto_theme_changed=lambda: calls.append("auto-theme"),
                    refresh_vrr=lambda: calls.append("vrr-refresh"),
                    set_vrr_policy=lambda policy: calls.append(f"vrr:{policy}"),
                ),
                weather=ConfigWeatherCallbacks(
                    search_city=lambda: calls.append("search"),
                    apply_selected_city=lambda index: calls.append(f"select:{index}"),
                    apply_weather=lambda: calls.append("weather"),
                    refresh_weather=lambda: calls.append("refresh-weather"),
                ),
                audio_eq=ConfigAudioEqCallbacks(
                    apply_eq=lambda: calls.append("eq"),
                    mark_dirty=lambda: calls.append("dirty"),
                ),
                quick_actions=ConfigQuickActionCallbacks(
                    reset_defaults=lambda: calls.append("reset"),
                    export_config=lambda: calls.append("export"),
                    import_config=lambda: calls.append("import"),
                    clear_cache=lambda: calls.append("clear"),
                    restart_app=lambda: calls.append("restart"),
                    usb_recovery=lambda: calls.append("usb"),
                ),
                automation=ConfigAutomationCallbacks(
                    add_playlist_item=lambda: calls.append("add"),
                    remove_playlist_item=lambda: calls.append("remove"),
                    start_playlist=lambda: calls.append("start"),
                    stop_playlist=lambda: calls.append("stop"),
                    browse_bundle_path=lambda: calls.append("browse"),
                    save_bundle=lambda: calls.append("save-bundle"),
                    load_bundle=lambda: calls.append("load-bundle"),
                ),
                actions=ConfigActionCallbacks(
                    cancel=lambda: calls.append("cancel"),
                    apply=lambda: calls.append("apply"),
                    save=lambda: calls.append("save"),
                ),
            ),
        )

        controls.gaming_fps.setup_btn.click()
        controls.weather.search_btn.click()
        controls.audio_eq.apply_btn.click()
        controls.quick_actions.usb_recovery_btn.click()
        controls.automation.playlist_add_btn.click()
        controls.actions.save_btn.click()

        self.assertEqual(controls.grid.count(), 7)
        self.assertEqual(controls.appearance.theme_combo.currentText(), "Plasma Blue")
        self.assertEqual(controls.runtime_paths.fps_socket_path_edit.text(), "/run/fps.sock")
        self.assertEqual(calls, ["setup", "search", "eq", "usb", "add", "save"])

    def test_build_config_panel_callbacks_maps_owner_methods(self) -> None:
        calls: list[str] = []
        owner = SimpleNamespace(
            config_preferences=SimpleNamespace(
                reset_defaults=lambda: calls.append("reset"),
                export_file=lambda: calls.append("export"),
                import_file=lambda: calls.append("import"),
                clear_cache=lambda: calls.append("clear"),
                restart_application=lambda: calls.append("restart"),
                sync_ui_controls_from_header=lambda: calls.append("cancel"),
                apply_preferences=lambda: calls.append("apply"),
            ),
            configure_fps_layer_user=lambda: calls.append("setup"),
            refresh_fps_layer_status=lambda: calls.append("refresh-fps"),
            copy_steam_fps_launch_options=lambda: calls.append("copy"),
            update_gaming_auto_theme_config=lambda: calls.append("auto-theme"),
            refresh_vrr_status=lambda: calls.append("vrr-refresh"),
            set_vrr_policy=lambda policy: calls.append(f"vrr:{policy}"),
            search_weather_city=lambda: calls.append("search"),
            _apply_selected_weather_city=lambda index: calls.append(f"select:{index}"),
            apply_weather_config=lambda: calls.append("weather"),
            refresh_weather_now=lambda: calls.append("refresh-weather"),
            apply_audio_eq_config=lambda: calls.append("eq"),
            run_usb_recovery=lambda: calls.append("usb"),
            add_playlist_item=lambda: calls.append("add"),
            remove_playlist_item=lambda: calls.append("remove"),
            start_playlist=lambda: calls.append("start"),
            stop_playlist=lambda: calls.append("stop"),
            browse_bundle_path=lambda: calls.append("browse"),
            save_bundle=lambda: calls.append("save-bundle"),
            load_bundle=lambda: calls.append("load-bundle"),
            _save_ui_state=lambda: calls.append("save-state"),
            append_log=lambda message: calls.append(message),
        )
        callbacks = build_config_panel_callbacks(owner)

        callbacks.gaming_fps.configure_layer()
        callbacks.gaming_fps.set_vrr_policy("automatic")
        callbacks.weather.apply_selected_city(3)
        callbacks.audio_eq.mark_dirty()
        callbacks.quick_actions.usb_recovery()
        callbacks.automation.save_bundle()
        callbacks.actions.save()

        self.assertTrue(owner._audio_eq_config_dirty)
        self.assertEqual(
            calls,
            [
                "setup",
                "vrr:automatic",
                "select:3",
                "usb",
                "save-bundle",
                "apply",
                "save-state",
                "[config] Zapisano ustawienia.",
            ],
        )

    def test_bind_config_panel_controls_exposes_legacy_owner_aliases(self) -> None:
        controls = build_config_panel_controls(
            theme_names=["Plasma Blue"],
            steam_launch_options='OPEN_TROFEO_GAME_NAME="Game" %command%',
            app_path="/app",
            theme_path="/themes",
            state_path="/state",
            fps_socket_path="/run/fps.sock",
            callbacks=self._noop_panel_callbacks(),
        )
        owner = SimpleNamespace()

        bind_config_panel_controls(owner, controls)

        self.assertIs(owner.cfg_ui_theme_combo, controls.appearance.theme_combo)
        self.assertIs(owner.cfg_fps_metrics_label, controls.gaming_fps.metrics_label)
        self.assertIs(owner.cfg_fps_log_path_edit, controls.gaming_fps.log_path_edit)
        self.assertIs(owner.cfg_vrr_status_label, controls.gaming_fps.vrr_status_label)
        self.assertIs(owner.cfg_vrr_automatic_btn, controls.gaming_fps.vrr_automatic_btn)
        self.assertIs(owner.cfg_weather_status_label, controls.weather.status_label)
        self.assertIs(owner.cfg_weather_temp_unit_combo, controls.weather.temperature_unit_combo)
        self.assertIs(owner.cfg_audio_eq_apply_btn, controls.audio_eq.apply_btn)
        self.assertIs(owner.automation_tools_box, controls.automation.box)
        self.assertIs(owner.cfg_save_btn, controls.actions.save_btn)

    def test_configuration_panel_owns_intro_grid_automation_and_actions(self) -> None:
        factory_calls: list[str] = []

        def make_intro_card(name: str) -> QFrame:
            factory_calls.append(name)
            return QFrame()

        panel = ConfigurationPanel(
            theme_names=["Plasma Blue"],
            steam_launch_options='OPEN_TROFEO_GAME_NAME="Game" %command%',
            app_path="/app",
            theme_path="/themes",
            state_path="/state",
            fps_socket_path="/run/fps.sock",
            callbacks=self._noop_panel_callbacks(),
            intro_card_factory=make_intro_card,
        )

        self.assertEqual(panel.objectName(), "configurationPanel")
        self.assertEqual(factory_calls, ["runtimeHeroCard"])
        self.assertEqual(panel.intro_card.objectName(), "runtimeHeroCard")
        self.assertIn("Configuration centralizes", panel.intro_label.text())
        self.assertEqual(panel.controls.grid.count(), 7)
        self.assertEqual(panel.layout().count(), 5)

    @staticmethod
    def _noop_panel_callbacks() -> ConfigPanelCallbacks:
        return ConfigPanelCallbacks(
            gaming_fps=ConfigGamingFpsCallbacks(
                configure_layer=lambda: None,
                refresh_status=lambda: None,
                copy_steam_command=lambda: None,
                auto_theme_changed=lambda: None,
                refresh_vrr=lambda: None,
                set_vrr_policy=lambda _policy: None,
            ),
            weather=ConfigWeatherCallbacks(
                search_city=lambda: None,
                apply_selected_city=lambda _index: None,
                apply_weather=lambda: None,
                refresh_weather=lambda: None,
            ),
            audio_eq=ConfigAudioEqCallbacks(
                apply_eq=lambda: None,
                mark_dirty=lambda: None,
            ),
            quick_actions=ConfigQuickActionCallbacks(
                reset_defaults=lambda: None,
                export_config=lambda: None,
                import_config=lambda: None,
                clear_cache=lambda: None,
                restart_app=lambda: None,
                usb_recovery=lambda: None,
            ),
            automation=ConfigAutomationCallbacks(
                add_playlist_item=lambda: None,
                remove_playlist_item=lambda: None,
                start_playlist=lambda: None,
                stop_playlist=lambda: None,
                browse_bundle_path=lambda: None,
                save_bundle=lambda: None,
                load_bundle=lambda: None,
            ),
            actions=ConfigActionCallbacks(
                cancel=lambda: None,
                apply=lambda: None,
                save=lambda: None,
            ),
        )


if __name__ == "__main__":
    unittest.main()
