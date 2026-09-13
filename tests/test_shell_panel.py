import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from shell_panel import ShellCallbacks, bind_shell_controls, build_shell


class ShellPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _build_controls(self, calls: list[str]):
        return build_shell(
            app_version_text="v0.test",
            ui_theme_names=["Plasma Blue", "Dark"],
            ui_languages={"English": "en", "Polski": "pl"},
            callbacks=ShellCallbacks(
                apply_ui_chrome=lambda: calls.append("chrome"),
                apply_language_selection=lambda label: calls.append(f"lang:{label}"),
                open_donate=lambda: calls.append("donate"),
                main_tab_changed=lambda widget: calls.append(f"tab:{widget is not None}"),
                go_system=lambda: calls.append("system"),
                go_logs=lambda: calls.append("logs"),
                go_config=lambda: calls.append("config"),
            ),
        )

    def test_build_shell_wires_navigation_and_header_callbacks(self) -> None:
        calls: list[str] = []
        controls = self._build_controls(calls)
        calls.clear()

        controls.header_donate_btn.click()
        controls.nav_system_btn.click()
        controls.nav_logs_btn.click()
        controls.nav_config_btn.click()
        controls.ui_mode_combo.setCurrentText("Light")
        controls.ui_scale_combo.setCurrentText("90%")
        controls.header_language_combo.setCurrentText("Polski")
        controls.main_tabs.setCurrentIndex(1)

        self.assertEqual(controls.main_tabs.count(), 4)
        self.assertEqual(controls.sidebar_version_label.text(), "v0.test")
        self.assertEqual(controls.header_device_combo.currentText(), "Trofeo LCD")
        self.assertIn("donate", calls)
        self.assertIn("system", calls)
        self.assertIn("logs", calls)
        self.assertIn("config", calls)
        self.assertGreaterEqual(calls.count("chrome"), 2)
        self.assertIn("lang:Polski", calls)
        self.assertIn("tab:True", calls)

    def test_bind_shell_controls_exposes_owner_aliases(self) -> None:
        controls = self._build_controls([])
        owner = SimpleNamespace()

        bind_shell_controls(owner, controls)

        self.assertIs(owner.sidebar_layout, controls.sidebar_layout)
        self.assertIs(owner.main_tabs, controls.main_tabs)
        self.assertIs(owner.nav_system_btn, controls.nav_system_btn)
        self.assertIs(owner.header_connection_label, controls.header_connection_label)
        self.assertIs(owner.ui_scale_combo, controls.ui_scale_combo)
        self.assertFalse(owner.sidebar_collapsed)


if __name__ == "__main__":
    unittest.main()
