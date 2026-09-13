"""Designer workspace shell widgets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QScrollArea, QTabWidget, QVBoxLayout, QWidget


@dataclass(frozen=True)
class DesignerWorkspaceCallbacks:
    animate_widget: Callable[[QWidget], None]


@dataclass(frozen=True)
class DesignerWorkspaceShellControls:
    studio_left_scroll: QScrollArea
    studio_left_container: QWidget
    studio_left_layout: QVBoxLayout
    studio_left_tabs: QTabWidget
    designer_tab: QWidget
    designer_tab_layout: QVBoxLayout
    json_tab: QWidget
    json_tab_layout: QVBoxLayout


def bind_designer_workspace_shell_controls(owner, controls: DesignerWorkspaceShellControls) -> None:
    owner.studio_left_scroll = controls.studio_left_scroll
    owner.studio_left_container = controls.studio_left_container
    owner.studio_left_layout = controls.studio_left_layout
    owner.studio_left_tabs = controls.studio_left_tabs
    owner.designer_tab = controls.designer_tab
    owner.designer_tab_layout = controls.designer_tab_layout
    owner.json_tab = controls.json_tab
    owner.json_tab_layout = controls.json_tab_layout
    owner.studio_splitter = None
    owner.studio_right_container = None


def build_designer_workspace_shell(
    designer_workspace_layout: QVBoxLayout,
    callbacks: DesignerWorkspaceCallbacks,
) -> DesignerWorkspaceShellControls:
    studio_left_scroll = QScrollArea()
    studio_left_scroll.setWidgetResizable(True)
    studio_left_scroll.setFrameShape(QScrollArea.NoFrame)
    studio_left_scroll.setMinimumWidth(0)

    studio_left_container = QWidget()
    studio_left_layout = QVBoxLayout(studio_left_container)
    studio_left_layout.setContentsMargins(0, 0, 0, 0)
    studio_left_layout.setSpacing(10)
    studio_left_scroll.setWidget(studio_left_container)
    designer_workspace_layout.addWidget(studio_left_scroll, 1)

    studio_left_tabs = QTabWidget()
    studio_left_tabs.setDocumentMode(True)
    studio_left_tabs.tabBar().hide()
    studio_left_tabs.setMinimumHeight(0)
    studio_left_tabs.currentChanged.connect(lambda _idx: callbacks.animate_widget(studio_left_tabs.currentWidget()))
    studio_left_layout.addWidget(studio_left_tabs, 1)

    designer_tab = QWidget()
    designer_tab_layout = QVBoxLayout(designer_tab)
    designer_tab_layout.setContentsMargins(0, 0, 0, 0)
    designer_tab_layout.setSpacing(4)

    json_tab = QWidget()
    json_tab_layout = QVBoxLayout(json_tab)
    json_tab_layout.setContentsMargins(0, 0, 0, 0)
    json_tab_layout.setSpacing(10)

    studio_left_tabs.addTab(designer_tab, "Designer")
    studio_left_tabs.addTab(json_tab, "JSON")

    return DesignerWorkspaceShellControls(
        studio_left_scroll=studio_left_scroll,
        studio_left_container=studio_left_container,
        studio_left_layout=studio_left_layout,
        studio_left_tabs=studio_left_tabs,
        designer_tab=designer_tab,
        designer_tab_layout=designer_tab_layout,
        json_tab=json_tab,
        json_tab_layout=json_tab_layout,
    )
