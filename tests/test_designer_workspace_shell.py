import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from designer.workspace_shell import (
    DesignerWorkspaceCallbacks,
    bind_designer_workspace_shell_controls,
    build_designer_workspace_shell,
)


class DesignerWorkspaceShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_build_workspace_shell_creates_tabs_and_wires_animation(self) -> None:
        calls: list[str] = []
        root = QWidget()
        layout = QVBoxLayout(root)

        controls = build_designer_workspace_shell(
            layout,
            DesignerWorkspaceCallbacks(animate_widget=lambda widget: calls.append(f"animate:{widget is not None}")),
        )
        controls.studio_left_tabs.setCurrentIndex(1)

        self.assertEqual(layout.count(), 1)
        self.assertEqual(controls.studio_left_tabs.count(), 2)
        self.assertEqual(controls.studio_left_tabs.tabText(0), "Designer")
        self.assertEqual(controls.studio_left_tabs.tabText(1), "JSON")
        self.assertTrue(controls.studio_left_scroll.widgetResizable())
        self.assertEqual(controls.studio_left_tabs.minimumHeight(), 0)
        self.assertIn("animate:True", calls)

    def test_bind_workspace_shell_controls_exposes_legacy_aliases(self) -> None:
        root = QWidget()
        controls = build_designer_workspace_shell(
            QVBoxLayout(root),
            DesignerWorkspaceCallbacks(animate_widget=lambda _widget: None),
        )
        owner = SimpleNamespace()

        bind_designer_workspace_shell_controls(owner, controls)

        self.assertIs(owner.studio_left_tabs, controls.studio_left_tabs)
        self.assertIs(owner.designer_tab_layout, controls.designer_tab_layout)
        self.assertIs(owner.json_tab_layout, controls.json_tab_layout)
        self.assertIsNone(owner.studio_splitter)
        self.assertIsNone(owner.studio_right_container)


if __name__ == "__main__":
    unittest.main()
