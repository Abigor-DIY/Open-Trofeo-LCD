import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from designer.layer_actions import refresh_layer_action_labels, setup_layer_action_controls

_APP = QApplication.instance() or QApplication([])


class _Owner(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.designer_auto_layout_btn = QPushButton("Arrange")

    def nudge_selected_elements(self, *_args, **_kwargs) -> None:
        pass

    def _selected_nudge_step(self) -> int:
        return 5

    def lower_designer_layer(self) -> None:
        pass

    def raise_designer_layer(self) -> None:
        pass

    def move_designer_layer_to_edge(self, _edge: str) -> None:
        pass

    def toggle_selected_visible(self) -> None:
        pass

    def toggle_selected_locked(self) -> None:
        pass

    def remove_designer_element(self) -> None:
        pass


class DesignerLayerActionTests(unittest.TestCase):
    def test_refresh_layer_action_labels_updates_controls(self) -> None:
        owner = _Owner()
        setup_layer_action_controls(owner)

        refresh_layer_action_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.designer_move_box.title(), "Przesuwanie zaznaczenia")
        self.assertEqual(owner.designer_nudge_step_label.text(), "Krok:")
        self.assertEqual(owner.designer_nudge_up_btn.toolTip(), "Przesuń w górę")
        self.assertEqual(owner.designer_layer_actions_label.text(), "Akcje warstw")
        self.assertEqual(owner.designer_layer_down_btn.text(), "Niżej")
        self.assertEqual(owner.designer_layer_front_btn.toolTip(), "Przenieś warstwę na przód")
        self.assertEqual(owner.designer_visibility_toggle_btn.text(), "Pokaż")
        self.assertEqual(owner.designer_lock_toggle_btn.toolTip(), "Zablokuj lub odblokuj zaznaczone warstwy")
        self.assertEqual(owner.designer_auto_layout_btn.text(), "Ułóż")
        self.assertEqual(owner.designer_remove_btn.text(), "🗑 Usuń")


if __name__ == "__main__":
    unittest.main()
