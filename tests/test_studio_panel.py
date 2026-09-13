import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from studio_panel import StudioCallbacks, bind_studio_panel_controls, build_studio_panel


class StudioPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _callbacks(self, calls: list[str]) -> StudioCallbacks:
        return StudioCallbacks(
            animate_widget=lambda widget: calls.append(f"animate:{widget is not None}"),
            sync_shell_navigation=lambda: calls.append("sync"),
            load_theme_doc=lambda: calls.append("load"),
            save_theme=lambda: calls.append("save"),
            preview_theme=lambda: calls.append("preview"),
            apply_theme=lambda: calls.append("apply"),
            reload_designer_from_json=lambda: calls.append("reload"),
            write_designer_to_json=lambda: calls.append("export"),
            apply_builtin_layout_preset=lambda name: calls.append(f"preset:{name}"),
        )

    def test_build_studio_panel_wires_tabs_toolbar_and_presets(self) -> None:
        calls: list[str] = []
        root = QWidget()
        layout = QVBoxLayout(root)
        controls = build_studio_panel(layout, self._callbacks(calls))
        calls.clear()

        controls.studio_sections_tabs.setCurrentIndex(1)
        controls.studio_toolbar_load_btn.click()
        controls.studio_toolbar_save_btn.click()
        controls.studio_toolbar_preview_btn.click()
        controls.studio_toolbar_apply_btn.click()
        controls.studio_toolbar_reload_btn.click()
        controls.studio_toolbar_export_btn.click()
        controls.quick_preset_dashboard_btn.click()
        controls.quick_preset_minimal_btn.click()
        controls.quick_preset_focus_btn.click()

        self.assertEqual(controls.studio_sections_tabs.count(), 3)
        self.assertEqual(controls.studio_sections_tabs.tabText(0), "Theme Gallery")
        self.assertFalse(controls.studio_toolbar_box.isVisible())
        self.assertFalse(controls.studio_toolbar_reload_btn.isVisible())
        self.assertEqual(controls.quick_preset_dashboard_btn.objectName(), "quickPresetButton")
        self.assertIn("animate:True", calls)
        self.assertIn("sync", calls)
        self.assertEqual(
            calls[-9:],
            ["load", "save", "preview", "apply", "reload", "export", "preset:dashboard", "preset:minimal", "preset:focus"],
        )

    def test_bind_studio_panel_controls_exposes_owner_aliases(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        controls = build_studio_panel(layout, self._callbacks([]))
        owner = SimpleNamespace()

        bind_studio_panel_controls(owner, controls)

        self.assertIs(owner.studio_sections_tabs, controls.studio_sections_tabs)
        self.assertIs(owner.animation_studio_tab, controls.animation_studio_tab)
        self.assertIs(owner.studio_toolbar_apply_btn, controls.studio_toolbar_apply_btn)
        self.assertIs(owner.quick_preset_focus_btn, controls.quick_preset_focus_btn)


if __name__ == "__main__":
    unittest.main()
