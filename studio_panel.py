"""Qt builders for the Theme Studio section shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QPushButton, QSizePolicy, QTabWidget, QVBoxLayout, QWidget


@dataclass(frozen=True)
class StudioCallbacks:
    animate_widget: Callable[[QWidget], None]
    sync_shell_navigation: Callable[[], None]
    load_theme_doc: Callable[[], None]
    save_theme: Callable[[], None]
    preview_theme: Callable[[], None]
    apply_theme: Callable[[], None]
    reload_designer_from_json: Callable[[], None]
    write_designer_to_json: Callable[[], None]
    apply_builtin_layout_preset: Callable[[str], None]


@dataclass(frozen=True)
class StudioPanelControls:
    studio_sections_tabs: QTabWidget
    library_tab: QWidget
    library_layout: QVBoxLayout
    designer_workspace_tab: QWidget
    designer_workspace_layout: QVBoxLayout
    animation_studio_tab: QWidget
    animation_studio_layout: QVBoxLayout
    studio_toolbar_box: QGroupBox
    studio_toolbar_load_btn: QPushButton
    studio_toolbar_save_btn: QPushButton
    studio_toolbar_preview_btn: QPushButton
    studio_toolbar_apply_btn: QPushButton
    studio_toolbar_reload_btn: QPushButton
    studio_toolbar_export_btn: QPushButton
    quick_preset_dashboard_btn: QPushButton
    quick_preset_minimal_btn: QPushButton
    quick_preset_focus_btn: QPushButton


def bind_studio_panel_controls(owner, controls: StudioPanelControls) -> None:
    owner.studio_sections_tabs = controls.studio_sections_tabs
    owner.animation_studio_tab = controls.animation_studio_tab
    owner.animation_studio_layout = controls.animation_studio_layout
    owner.studio_toolbar_box = controls.studio_toolbar_box
    owner.studio_toolbar_load_btn = controls.studio_toolbar_load_btn
    owner.studio_toolbar_save_btn = controls.studio_toolbar_save_btn
    owner.studio_toolbar_preview_btn = controls.studio_toolbar_preview_btn
    owner.studio_toolbar_apply_btn = controls.studio_toolbar_apply_btn
    owner.studio_toolbar_reload_btn = controls.studio_toolbar_reload_btn
    owner.studio_toolbar_export_btn = controls.studio_toolbar_export_btn
    owner.quick_preset_dashboard_btn = controls.quick_preset_dashboard_btn
    owner.quick_preset_minimal_btn = controls.quick_preset_minimal_btn
    owner.quick_preset_focus_btn = controls.quick_preset_focus_btn


def build_studio_panel(studio_layout: QVBoxLayout, callbacks: StudioCallbacks) -> StudioPanelControls:
    studio_sections_tabs = QTabWidget()
    studio_sections_tabs.setObjectName("studioSectionTabs")
    studio_sections_tabs.setDocumentMode(True)
    studio_sections_tabs.tabBar().hide()
    # The tab widget must not inherit a huge minimum width from hidden pages
    # (the theme gallery is much wider than the designer); otherwise the outer
    # scroll area shows a horizontal scrollbar that makes the layout jump.
    hidden_page_policy = studio_sections_tabs.sizePolicy()
    hidden_page_policy.setHorizontalPolicy(QSizePolicy.Ignored)
    studio_sections_tabs.setSizePolicy(hidden_page_policy)
    studio_layout.addWidget(studio_sections_tabs, 1)
    studio_sections_tabs.currentChanged.connect(
        lambda _idx: (
            callbacks.animate_widget(studio_sections_tabs.currentWidget()),
            callbacks.sync_shell_navigation(),
        )
    )

    library_tab = QWidget()
    library_layout = QVBoxLayout(library_tab)
    library_layout.setContentsMargins(0, 0, 0, 0)
    library_layout.setSpacing(10)

    designer_workspace_tab = QWidget()
    designer_workspace_layout = QVBoxLayout(designer_workspace_tab)
    designer_workspace_layout.setContentsMargins(0, 0, 0, 0)
    designer_workspace_layout.setSpacing(10)

    animation_studio_tab = QWidget()
    animation_studio_layout = QVBoxLayout(animation_studio_tab)
    animation_studio_layout.setContentsMargins(10, 10, 10, 10)
    animation_studio_layout.setSpacing(10)

    studio_sections_tabs.addTab(library_tab, "Theme Gallery")
    studio_sections_tabs.addTab(designer_workspace_tab, "Designer")
    studio_sections_tabs.addTab(animation_studio_tab, "Animation Studio")

    studio_toolbar_box = QGroupBox("")
    studio_toolbar_box.setObjectName("designerToolbarBox")
    studio_toolbar_box.setFlat(True)
    studio_toolbar_layout = QHBoxLayout(studio_toolbar_box)

    studio_toolbar_load_btn = QPushButton("Load theme")
    studio_toolbar_save_btn = QPushButton("Save theme")
    studio_toolbar_preview_btn = QPushButton("Preview")
    studio_toolbar_apply_btn = QPushButton("Apply theme")
    studio_toolbar_reload_btn = QPushButton("JSON -> Designer")
    studio_toolbar_export_btn = QPushButton("Designer -> JSON")
    for button in (
        studio_toolbar_load_btn,
        studio_toolbar_save_btn,
        studio_toolbar_preview_btn,
        studio_toolbar_apply_btn,
        studio_toolbar_reload_btn,
        studio_toolbar_export_btn,
    ):
        button.setMinimumHeight(34)
        button.setMaximumWidth(210)
    studio_toolbar_preview_btn.setObjectName("secondaryAccentButton")
    studio_toolbar_apply_btn.setObjectName("primaryButton")
    studio_toolbar_load_btn.clicked.connect(callbacks.load_theme_doc)
    studio_toolbar_save_btn.clicked.connect(callbacks.save_theme)
    studio_toolbar_preview_btn.clicked.connect(callbacks.preview_theme)
    studio_toolbar_apply_btn.clicked.connect(callbacks.apply_theme)
    studio_toolbar_reload_btn.clicked.connect(callbacks.reload_designer_from_json)
    studio_toolbar_export_btn.clicked.connect(callbacks.write_designer_to_json)
    studio_toolbar_layout.addStretch(1)
    studio_toolbar_layout.addWidget(studio_toolbar_load_btn)
    studio_toolbar_layout.addWidget(studio_toolbar_save_btn)
    studio_toolbar_layout.addWidget(studio_toolbar_preview_btn)
    studio_toolbar_layout.addWidget(studio_toolbar_apply_btn)
    studio_toolbar_layout.addSpacing(6)
    studio_toolbar_layout.addWidget(studio_toolbar_reload_btn)
    studio_toolbar_layout.addWidget(studio_toolbar_export_btn)
    studio_toolbar_reload_btn.hide()
    studio_toolbar_export_btn.hide()
    studio_toolbar_box.hide()

    quick_preset_dashboard_btn = QPushButton("Dashboard")
    quick_preset_minimal_btn = QPushButton("Minimal")
    quick_preset_focus_btn = QPushButton("Focus")
    for button in (quick_preset_dashboard_btn, quick_preset_minimal_btn, quick_preset_focus_btn):
        button.setObjectName("quickPresetButton")
    quick_preset_dashboard_btn.clicked.connect(lambda: callbacks.apply_builtin_layout_preset("dashboard"))
    quick_preset_minimal_btn.clicked.connect(lambda: callbacks.apply_builtin_layout_preset("minimal"))
    quick_preset_focus_btn.clicked.connect(lambda: callbacks.apply_builtin_layout_preset("focus"))

    return StudioPanelControls(
        studio_sections_tabs=studio_sections_tabs,
        library_tab=library_tab,
        library_layout=library_layout,
        designer_workspace_tab=designer_workspace_tab,
        designer_workspace_layout=designer_workspace_layout,
        animation_studio_tab=animation_studio_tab,
        animation_studio_layout=animation_studio_layout,
        studio_toolbar_box=studio_toolbar_box,
        studio_toolbar_load_btn=studio_toolbar_load_btn,
        studio_toolbar_save_btn=studio_toolbar_save_btn,
        studio_toolbar_preview_btn=studio_toolbar_preview_btn,
        studio_toolbar_apply_btn=studio_toolbar_apply_btn,
        studio_toolbar_reload_btn=studio_toolbar_reload_btn,
        studio_toolbar_export_btn=studio_toolbar_export_btn,
        quick_preset_dashboard_btn=quick_preset_dashboard_btn,
        quick_preset_minimal_btn=quick_preset_minimal_btn,
        quick_preset_focus_btn=quick_preset_focus_btn,
    )
