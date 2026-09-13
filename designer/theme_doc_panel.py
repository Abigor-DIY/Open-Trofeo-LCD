"""Theme JSON document editor panel widgets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)


@dataclass(frozen=True)
class ThemeDocCallbacks:
    editor_changed: Callable[[], None]
    browse_theme_path: Callable[[], None]
    use_selected_theme: Callable[[], None]
    load_theme: Callable[[], None]
    save_theme: Callable[[], None]
    save_theme_as: Callable[[], None]
    apply_theme: Callable[[], None]
    open_external: Callable[[], None]
    insert_field_guide: Callable[[], None]


@dataclass(frozen=True)
class ThemeDocPanelControls:
    box: QGroupBox
    path_edit: QLineEdit
    browse_btn: QPushButton
    use_selected_btn: QPushButton
    load_btn: QPushButton
    save_btn: QPushButton
    save_as_btn: QPushButton
    apply_btn: QPushButton
    stop_before_apply_chk: QCheckBox
    resume_chk: QCheckBox
    schema_label: QLabel
    editor: QTextEdit
    open_external_btn: QPushButton
    insert_guide_btn: QPushButton
    path_caption: QLabel
    manual_json_label: QLabel
    sources_caption: QLabel


def bind_theme_doc_panel_controls(owner, controls: ThemeDocPanelControls) -> None:
    owner.theme_doc_box = controls.box
    owner.theme_doc_path_edit = controls.path_edit
    owner.theme_doc_browse_btn = controls.browse_btn
    owner.theme_doc_use_selected_btn = controls.use_selected_btn
    owner.theme_doc_load_btn = controls.load_btn
    owner.theme_doc_save_btn = controls.save_btn
    owner.theme_doc_save_as_btn = controls.save_as_btn
    owner.theme_doc_apply_btn = controls.apply_btn
    owner.theme_doc_stop_before_apply_chk = controls.stop_before_apply_chk
    owner.theme_doc_resume_chk = controls.resume_chk
    owner.theme_schema_label = controls.schema_label
    owner.theme_doc_editor = controls.editor
    owner.theme_doc_open_external_btn = controls.open_external_btn
    owner.theme_doc_insert_guide_btn = controls.insert_guide_btn
    owner.theme_doc_path_caption = controls.path_caption
    owner.theme_doc_manual_json_label = controls.manual_json_label
    owner.theme_doc_sources_caption = controls.sources_caption


def build_theme_doc_panel(
    *,
    json_tab_layout: QVBoxLayout,
    callbacks: ThemeDocCallbacks,
    default_path: str = str(Path("themes/obsidian_pulse.json")),
) -> ThemeDocPanelControls:
    box = QGroupBox("Theme")
    grid = QGridLayout(box)
    grid.setColumnStretch(1, 1)

    path_edit = QLineEdit(default_path)
    browse_btn = QPushButton("Browse theme…")
    use_selected_btn = QPushButton("From active theme")
    load_btn = QPushButton("Load")
    save_btn = QPushButton("Save")
    save_as_btn = QPushButton("Save As")
    apply_btn = QPushButton("Apply")
    apply_btn.setObjectName("primaryButton")
    stop_before_apply_chk = QCheckBox("Stop runtime before apply")
    stop_before_apply_chk.setChecked(True)
    resume_chk = QCheckBox("Resume loop after apply")
    resume_chk.setChecked(False)
    schema_label = QLabel("-")

    editor = QTextEdit()
    editor.setPlaceholderText("{\n  \"schema_version\": 1,\n  ...\n}")
    editor.setMinimumHeight(460)
    editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    open_external_btn = QPushButton("Open JSON file…")
    open_external_btn.setObjectName("secondaryAccentButton")
    insert_guide_btn = QPushButton("Insert field guide")
    path_caption = QLabel("Theme file:")
    manual_json_label = QLabel("Manual JSON:")
    sources_caption = QLabel("Declared stats:")

    editor.textChanged.connect(callbacks.editor_changed)
    browse_btn.clicked.connect(callbacks.browse_theme_path)
    use_selected_btn.clicked.connect(callbacks.use_selected_theme)
    load_btn.clicked.connect(callbacks.load_theme)
    save_btn.clicked.connect(callbacks.save_theme)
    save_as_btn.clicked.connect(callbacks.save_theme_as)
    apply_btn.clicked.connect(callbacks.apply_theme)
    open_external_btn.clicked.connect(callbacks.open_external)
    insert_guide_btn.clicked.connect(callbacks.insert_field_guide)

    grid.addWidget(path_caption, 0, 0)
    grid.addWidget(path_edit, 0, 1, 1, 3)
    grid.addWidget(browse_btn, 0, 4)
    grid.addWidget(use_selected_btn, 0, 5)
    grid.addWidget(stop_before_apply_chk, 1, 1, 1, 2)
    grid.addWidget(resume_chk, 1, 3)
    grid.addWidget(load_btn, 1, 4)
    grid.addWidget(save_btn, 1, 5)
    grid.addWidget(manual_json_label, 2, 0)
    grid.addWidget(open_external_btn, 2, 1, 1, 2)
    grid.addWidget(insert_guide_btn, 2, 3)
    grid.addWidget(save_as_btn, 2, 4)
    grid.addWidget(apply_btn, 2, 5)
    grid.addWidget(sources_caption, 3, 0)
    grid.addWidget(schema_label, 3, 1, 1, 4)
    grid.addWidget(editor, 4, 0, 1, 6)

    json_tab_layout.addWidget(box, 1)
    box.hide()

    return ThemeDocPanelControls(
        box=box,
        path_edit=path_edit,
        browse_btn=browse_btn,
        use_selected_btn=use_selected_btn,
        load_btn=load_btn,
        save_btn=save_btn,
        save_as_btn=save_as_btn,
        apply_btn=apply_btn,
        stop_before_apply_chk=stop_before_apply_chk,
        resume_chk=resume_chk,
        schema_label=schema_label,
        editor=editor,
        open_external_btn=open_external_btn,
        insert_guide_btn=insert_guide_btn,
        path_caption=path_caption,
        manual_json_label=manual_json_label,
        sources_caption=sources_caption,
    )
