"""Layer action controls for the Theme Designer side panel."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
)

TranslateFn = Callable[[str, str], str]


def setup_layer_action_controls(owner: object) -> QGroupBox:
    """Create the nudge and layer action controls, wiring them to the main window."""
    move_box = QGroupBox("Nudge selection")
    owner.designer_move_box = move_box
    move_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
    move_layout = QVBoxLayout(move_box)
    move_layout.setContentsMargins(6, 5, 6, 5)
    move_layout.setSpacing(4)

    move_step_row = QHBoxLayout()
    move_step_row.setSpacing(5)
    owner.designer_nudge_step_label = QLabel("Step:")
    move_step_row.addWidget(owner.designer_nudge_step_label)
    owner.designer_nudge_step_combo = QComboBox()
    for step in (1, 2, 3, 5, 8, 10, 16, 24, 32):
        owner.designer_nudge_step_combo.addItem(f"{step} px", step)
    owner.designer_nudge_step_combo.setCurrentIndex(3)
    owner.designer_nudge_step_combo.setMaximumWidth(120)
    move_step_row.addWidget(owner.designer_nudge_step_combo, 1)
    move_layout.addLayout(move_step_row)

    dpad = QGridLayout()
    dpad.setHorizontalSpacing(5)
    dpad.setVerticalSpacing(4)
    nudge_icon_size = QSize(22, 22)
    style = owner.style()
    owner.designer_nudge_up_btn = QPushButton()
    owner.designer_nudge_up_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
    owner.designer_nudge_up_btn.setIconSize(nudge_icon_size)
    owner.designer_nudge_up_btn.setToolTip("Nudge up")
    owner.designer_nudge_left_btn = QPushButton()
    owner.designer_nudge_left_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
    owner.designer_nudge_left_btn.setIconSize(nudge_icon_size)
    owner.designer_nudge_left_btn.setToolTip("Nudge left")
    owner.designer_nudge_right_btn = QPushButton()
    owner.designer_nudge_right_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
    owner.designer_nudge_right_btn.setIconSize(nudge_icon_size)
    owner.designer_nudge_right_btn.setToolTip("Nudge right")
    owner.designer_nudge_down_btn = QPushButton()
    owner.designer_nudge_down_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
    owner.designer_nudge_down_btn.setIconSize(nudge_icon_size)
    owner.designer_nudge_down_btn.setToolTip("Nudge down")
    for btn in (
        owner.designer_nudge_up_btn,
        owner.designer_nudge_left_btn,
        owner.designer_nudge_right_btn,
        owner.designer_nudge_down_btn,
    ):
        btn.setMinimumHeight(32)
        btn.setMaximumHeight(36)
        btn.setMinimumWidth(36)
        btn.setMaximumWidth(44)
    dpad.addWidget(owner.designer_nudge_up_btn, 0, 1)
    dpad.addWidget(owner.designer_nudge_left_btn, 1, 0)
    dpad.addWidget(owner.designer_nudge_right_btn, 1, 2)
    dpad.addWidget(owner.designer_nudge_down_btn, 2, 1)
    move_layout.addLayout(dpad)

    owner.designer_nudge_up_btn.clicked.connect(lambda: owner.nudge_selected_elements(0, -1, step_override=owner._selected_nudge_step(), require_keyboard_focus=False))
    owner.designer_nudge_left_btn.clicked.connect(lambda: owner.nudge_selected_elements(-1, 0, step_override=owner._selected_nudge_step(), require_keyboard_focus=False))
    owner.designer_nudge_right_btn.clicked.connect(lambda: owner.nudge_selected_elements(1, 0, step_override=owner._selected_nudge_step(), require_keyboard_focus=False))
    owner.designer_nudge_down_btn.clicked.connect(lambda: owner.nudge_selected_elements(0, 1, step_override=owner._selected_nudge_step(), require_keyboard_focus=False))

    owner.designer_layer_actions_label = QLabel("Layer actions")
    owner.designer_layer_actions_label.setObjectName("selectionSummaryLabel")
    owner.designer_layer_actions_label.setMaximumHeight(16)
    move_layout.addWidget(owner.designer_layer_actions_label)
    layer_actions_grid = QGridLayout()
    layer_actions_grid.setContentsMargins(0, 0, 0, 0)
    layer_actions_grid.setHorizontalSpacing(5)
    layer_actions_grid.setVerticalSpacing(4)
    owner.designer_layer_down_btn = QPushButton("Lower")
    owner.designer_layer_up_btn = QPushButton("Raise")
    owner.designer_layer_back_btn = QPushButton("Back")
    owner.designer_layer_front_btn = QPushButton("Front")
    owner.designer_visibility_toggle_btn = QPushButton("Show")
    owner.designer_lock_toggle_btn = QPushButton("Lock")
    for btn in (
        owner.designer_layer_down_btn,
        owner.designer_layer_up_btn,
        owner.designer_layer_back_btn,
        owner.designer_layer_front_btn,
        owner.designer_visibility_toggle_btn,
        owner.designer_lock_toggle_btn,
    ):
        btn.setObjectName("compactActionButton")
        btn.setMinimumHeight(24)
        btn.setMaximumHeight(28)
        btn.setMinimumWidth(64)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    owner.designer_layer_down_btn.clicked.connect(owner.lower_designer_layer)
    owner.designer_layer_up_btn.clicked.connect(owner.raise_designer_layer)
    owner.designer_layer_back_btn.clicked.connect(lambda: owner.move_designer_layer_to_edge("back"))
    owner.designer_layer_front_btn.clicked.connect(lambda: owner.move_designer_layer_to_edge("front"))
    owner.designer_visibility_toggle_btn.clicked.connect(owner.toggle_selected_visible)
    owner.designer_lock_toggle_btn.clicked.connect(owner.toggle_selected_locked)
    layer_actions_grid.addWidget(owner.designer_layer_down_btn, 0, 0)
    layer_actions_grid.addWidget(owner.designer_layer_up_btn, 0, 1)
    layer_actions_grid.addWidget(owner.designer_layer_back_btn, 0, 2)
    layer_actions_grid.addWidget(owner.designer_layer_front_btn, 1, 0)
    layer_actions_grid.addWidget(owner.designer_visibility_toggle_btn, 1, 1)
    layer_actions_grid.addWidget(owner.designer_lock_toggle_btn, 1, 2)
    for action_col in range(3):
        layer_actions_grid.setColumnStretch(action_col, 1)
    move_layout.addLayout(layer_actions_grid)

    move_actions_row = QHBoxLayout()
    move_actions_row.setContentsMargins(0, 0, 0, 0)
    move_actions_row.setSpacing(6)
    move_actions_row.addStretch(1)
    owner.designer_remove_btn = QPushButton("🗑 Delete")
    owner.designer_remove_btn.setMinimumHeight(28)
    owner.designer_remove_btn.setMaximumWidth(112)
    owner.designer_remove_btn.setStyleSheet(
        "QPushButton { background: #3a1f25; border: 1px solid #a33a48; color: #ffd7dc; }"
        "QPushButton:hover { background: #512730; border: 1px solid #d05b6b; }"
        "QPushButton:pressed { background: #2a1418; }"
    )
    owner.designer_remove_btn.clicked.connect(owner.remove_designer_element)
    move_actions_row.addWidget(owner.designer_remove_btn)
    move_layout.addLayout(move_actions_row)
    move_box.setMaximumHeight(270)
    return move_box


def refresh_layer_action_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels and tooltips for nudge/layer action controls."""
    if hasattr(owner, "designer_move_box"):
        owner.designer_move_box.setTitle(translate("Nudge selection", "Przesuwanie zaznaczenia"))
    if hasattr(owner, "designer_nudge_step_label"):
        owner.designer_nudge_step_label.setText(translate("Step:", "Krok:"))
    if hasattr(owner, "designer_nudge_up_btn"):
        owner.designer_nudge_up_btn.setToolTip(translate("Nudge up", "Przesuń w górę"))
    if hasattr(owner, "designer_nudge_left_btn"):
        owner.designer_nudge_left_btn.setToolTip(translate("Nudge left", "Przesuń w lewo"))
    if hasattr(owner, "designer_nudge_right_btn"):
        owner.designer_nudge_right_btn.setToolTip(translate("Nudge right", "Przesuń w prawo"))
    if hasattr(owner, "designer_nudge_down_btn"):
        owner.designer_nudge_down_btn.setToolTip(translate("Nudge down", "Przesuń w dół"))
    if hasattr(owner, "designer_layer_actions_label"):
        owner.designer_layer_actions_label.setText(translate("Layer actions", "Akcje warstw"))
    if hasattr(owner, "designer_layer_down_btn"):
        owner.designer_layer_down_btn.setText(translate("Lower", "Niżej"))
        owner.designer_layer_down_btn.setToolTip(translate("Lower selected layer", "Przesuń warstwę niżej"))
    if hasattr(owner, "designer_layer_up_btn"):
        owner.designer_layer_up_btn.setText(translate("Raise", "Wyżej"))
        owner.designer_layer_up_btn.setToolTip(translate("Raise selected layer", "Przesuń warstwę wyżej"))
    if hasattr(owner, "designer_layer_back_btn"):
        owner.designer_layer_back_btn.setText(translate("Back", "Tył"))
        owner.designer_layer_back_btn.setToolTip(translate("Send selected layer to back", "Wyślij warstwę na tył"))
    if hasattr(owner, "designer_layer_front_btn"):
        owner.designer_layer_front_btn.setText(translate("Front", "Przód"))
        owner.designer_layer_front_btn.setToolTip(translate("Bring selected layer to front", "Przenieś warstwę na przód"))
    if hasattr(owner, "designer_visibility_toggle_btn"):
        owner.designer_visibility_toggle_btn.setText(translate("Show", "Pokaż"))
        owner.designer_visibility_toggle_btn.setToolTip(translate("Show or hide selected layers", "Pokaż lub ukryj zaznaczone warstwy"))
    if hasattr(owner, "designer_lock_toggle_btn"):
        owner.designer_lock_toggle_btn.setText(translate("Lock", "Blokuj"))
        owner.designer_lock_toggle_btn.setToolTip(translate("Lock or unlock selected layers", "Zablokuj lub odblokuj zaznaczone warstwy"))
    if hasattr(owner, "designer_auto_layout_btn"):
        owner.designer_auto_layout_btn.setText(translate("Arrange", "Ułóż"))
        owner.designer_auto_layout_btn.setToolTip(
            translate(
                "Auto-arrange selected layers, or all visible widgets and stats when nothing is selected.",
                "Automatycznie rozmieść zaznaczenie albo wszystkie widoczne widgety i statystyki, gdy nic nie jest zaznaczone.",
            )
        )
    if hasattr(owner, "designer_remove_btn"):
        owner.designer_remove_btn.setText(translate("🗑 Delete", "🗑 Usuń"))
