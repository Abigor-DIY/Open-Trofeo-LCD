import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from designer.theme_doc_panel import ThemeDocCallbacks, bind_theme_doc_panel_controls, build_theme_doc_panel


class ThemeDocPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _callbacks(self, calls: list[str]) -> ThemeDocCallbacks:
        return ThemeDocCallbacks(
            editor_changed=lambda: calls.append("changed"),
            browse_theme_path=lambda: calls.append("browse"),
            use_selected_theme=lambda: calls.append("selected"),
            load_theme=lambda: calls.append("load"),
            save_theme=lambda: calls.append("save"),
            save_theme_as=lambda: calls.append("save-as"),
            apply_theme=lambda: calls.append("apply"),
            open_external=lambda: calls.append("external"),
            insert_field_guide=lambda: calls.append("guide"),
        )

    def test_build_theme_doc_panel_wires_controls(self) -> None:
        calls: list[str] = []
        root = QWidget()
        layout = QVBoxLayout(root)
        controls = build_theme_doc_panel(
            json_tab_layout=layout,
            callbacks=self._callbacks(calls),
            default_path="themes/test.json",
        )
        calls.clear()

        controls.browse_btn.click()
        controls.use_selected_btn.click()
        controls.load_btn.click()
        controls.save_btn.click()
        controls.save_as_btn.click()
        controls.apply_btn.click()
        controls.open_external_btn.click()
        controls.insert_guide_btn.click()
        controls.editor.setPlainText("{}")

        self.assertEqual(layout.count(), 1)
        self.assertEqual(controls.path_edit.text(), "themes/test.json")
        self.assertEqual(controls.apply_btn.objectName(), "primaryButton")
        self.assertEqual(controls.open_external_btn.objectName(), "secondaryAccentButton")
        self.assertTrue(controls.stop_before_apply_chk.isChecked())
        self.assertFalse(controls.resume_chk.isChecked())
        self.assertEqual(controls.editor.minimumHeight(), 460)
        self.assertIn("changed", calls)
        self.assertEqual(
            calls[:8],
            ["browse", "selected", "load", "save", "save-as", "apply", "external", "guide"],
        )

    def test_bind_theme_doc_panel_controls_exposes_legacy_aliases(self) -> None:
        root = QWidget()
        controls = build_theme_doc_panel(
            json_tab_layout=QVBoxLayout(root),
            callbacks=self._callbacks([]),
        )
        owner = SimpleNamespace()

        bind_theme_doc_panel_controls(owner, controls)

        self.assertIs(owner.theme_doc_box, controls.box)
        self.assertIs(owner.theme_doc_path_edit, controls.path_edit)
        self.assertIs(owner.theme_doc_editor, controls.editor)
        self.assertIs(owner.theme_schema_label, controls.schema_label)
        self.assertIs(owner.theme_doc_apply_btn, controls.apply_btn)


if __name__ == "__main__":
    unittest.main()
