"""Qt shell layout builders for the main Open Trofeo LCD window."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flow_layout import FlowLayout


@dataclass(frozen=True)
class ShellCallbacks:
    apply_ui_chrome: Callable[[], None]
    apply_language_selection: Callable[[str], None]
    open_donate: Callable[[], None]
    main_tab_changed: Callable[[QWidget], None]
    go_system: Callable[[], None]
    go_logs: Callable[[], None]
    go_config: Callable[[], None]


@dataclass(frozen=True)
class ShellControls:
    root: QWidget
    sidebar_layout: QVBoxLayout
    brand_label: QLabel
    brand_sub: QLabel
    sidebar_toggle_btn: QPushButton
    nav_library_btn: QPushButton
    nav_designer_btn: QPushButton
    nav_animation_studio_btn: QPushButton
    nav_system_btn: QPushButton
    nav_logs_btn: QPushButton
    nav_config_btn: QPushButton
    nav_button_meta: dict[QPushButton, tuple[str, str]]
    shell_nav_buttons: list[QPushButton]
    sidebar_footer: QFrame
    sidebar_version_label: QLabel
    sidebar_footer_note: QLabel
    sidebar_frame: QFrame
    chrome_box: QGroupBox
    shell_title_sub: QLabel
    ui_mode_combo: QComboBox
    ui_theme_combo: QComboBox
    ui_scale_combo: QComboBox
    header_connection_label: QLabel
    header_device_combo: QComboBox
    header_ready_label: QLabel
    header_language_combo: QComboBox
    header_donate_btn: QPushButton
    header_mode_label: QLabel
    header_scale_label: QLabel
    header_conn_label: QLabel
    header_device_label: QLabel
    header_language_label: QLabel
    main_tabs: QTabWidget
    runtime_layout: QVBoxLayout
    studio_layout: QVBoxLayout
    automation_layout: QVBoxLayout
    logs_layout: QVBoxLayout


def bind_shell_controls(owner, controls: ShellControls) -> None:
    owner.sidebar_layout = controls.sidebar_layout
    owner.brand_label = controls.brand_label
    owner.brand_sub = controls.brand_sub
    owner.sidebar_toggle_btn = controls.sidebar_toggle_btn
    owner.nav_library_btn = controls.nav_library_btn
    owner.nav_designer_btn = controls.nav_designer_btn
    owner.nav_animation_studio_btn = controls.nav_animation_studio_btn
    owner.nav_system_btn = controls.nav_system_btn
    owner.nav_logs_btn = controls.nav_logs_btn
    owner.nav_config_btn = controls.nav_config_btn
    owner._nav_button_meta = controls.nav_button_meta
    owner._shell_nav_buttons = controls.shell_nav_buttons
    owner.sidebar_footer = controls.sidebar_footer
    owner.sidebar_version_label = controls.sidebar_version_label
    owner.sidebar_footer_note = controls.sidebar_footer_note
    owner.sidebar_frame = controls.sidebar_frame
    owner.sidebar_collapsed = False
    owner.chrome_box = controls.chrome_box
    owner.shell_title_sub = controls.shell_title_sub
    owner.ui_mode_combo = controls.ui_mode_combo
    owner.ui_theme_combo = controls.ui_theme_combo
    owner.ui_scale_combo = controls.ui_scale_combo
    owner.header_connection_label = controls.header_connection_label
    owner.header_device_combo = controls.header_device_combo
    owner.header_ready_label = controls.header_ready_label
    owner.header_language_combo = controls.header_language_combo
    owner.header_donate_btn = controls.header_donate_btn
    owner.header_mode_label = controls.header_mode_label
    owner.header_scale_label = controls.header_scale_label
    owner.header_conn_label = controls.header_conn_label
    owner.header_device_label = controls.header_device_label
    owner.header_language_label = controls.header_language_label
    owner.main_tabs = controls.main_tabs


def _make_scroll_tab() -> tuple[QWidget, QVBoxLayout]:
    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(8, 8, 8, 8)
    container_layout.setSpacing(20)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setWidget(container)
    return scroll, container_layout


def build_shell(
    *,
    app_version_text: str,
    ui_theme_names: list[str],
    ui_languages: dict[str, str],
    callbacks: ShellCallbacks,
) -> ShellControls:
    root = QWidget()
    shell_layout = QHBoxLayout(root)
    shell_layout.setContentsMargins(16, 16, 16, 16)
    shell_layout.setSpacing(16)

    sidebar = QFrame()
    sidebar.setObjectName("shellSidebar")
    sidebar.setFixedWidth(248)
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.setContentsMargins(14, 16, 14, 16)
    sidebar_layout.setSpacing(10)

    brand_row = QHBoxLayout()
    brand_row.setSpacing(8)
    brand_icon = QLabel("⟡")
    brand_icon.setObjectName("shellBrandIcon")
    brand_label = QLabel("THERMALRIGHT")
    brand_label.setObjectName("shellBrandLabel")
    brand_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    brand_label.setMinimumWidth(0)
    brand_sub = QLabel("TROFEO LCD")
    brand_sub.setObjectName("shellBrandSubLabel")
    sidebar_toggle_btn = QPushButton("⟨")
    sidebar_toggle_btn.setObjectName("secondaryAccentButton")
    sidebar_toggle_btn.setMinimumSize(30, 30)
    sidebar_toggle_btn.setMaximumWidth(30)
    brand_row.addWidget(brand_icon)
    brand_row.addWidget(brand_label)
    brand_row.addStretch(1)
    brand_row.addWidget(sidebar_toggle_btn)
    sidebar_layout.addLayout(brand_row)
    sidebar_layout.addWidget(brand_sub)

    nav_library_btn = QPushButton("🗂  Theme\nGallery")
    nav_designer_btn = QPushButton("✎  Theme\nDesigner")
    nav_animation_studio_btn = QPushButton("🎞  Animation\nStudio")
    nav_system_btn = QPushButton("◉  System")
    nav_logs_btn = QPushButton("☰  Logs")
    nav_config_btn = QPushButton("⚙  Configuration")
    nav_button_meta = {
        nav_library_btn: ("🗂", "Theme Gallery"),
        nav_designer_btn: ("✎", "Theme Designer"),
        nav_animation_studio_btn: ("🎞", "Animation Studio"),
        nav_system_btn: ("◉", "System"),
        nav_logs_btn: ("☰", "Logs"),
        nav_config_btn: ("⚙", "Configuration"),
    }
    shell_nav_buttons = [
        nav_library_btn,
        nav_designer_btn,
        nav_animation_studio_btn,
        nav_system_btn,
        nav_logs_btn,
        nav_config_btn,
    ]
    for button in shell_nav_buttons:
        button.setCheckable(True)
        button.setObjectName("shellNavButton")
        button.setMinimumHeight(64)
        sidebar_layout.addWidget(button)
    sidebar_layout.addStretch(1)

    sidebar_footer = QFrame()
    sidebar_footer.setObjectName("sidebarFooterCard")
    sidebar_footer_layout = QVBoxLayout(sidebar_footer)
    sidebar_footer_layout.setContentsMargins(14, 14, 14, 14)
    sidebar_footer_layout.setSpacing(4)
    sidebar_version_label = QLabel(app_version_text)
    sidebar_version_label.setObjectName("sidebarFooterTitle")
    sidebar_footer_note = QLabel("Open Trofeo LCD\nLinux Open Driver")
    sidebar_footer_note.setObjectName("sidebarFooterMeta")
    sidebar_footer_layout.addWidget(sidebar_version_label)
    sidebar_footer_layout.addWidget(sidebar_footer_note)
    sidebar_layout.addWidget(sidebar_footer)
    shell_layout.addWidget(sidebar)

    content = QWidget()
    outer = QVBoxLayout(content)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(12)
    shell_layout.addWidget(content, 1)

    chrome_box = QGroupBox("Control")
    chrome_box.setObjectName("shellHeader")
    chrome_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    chrome_policy.setHeightForWidth(True)
    chrome_box.setSizePolicy(chrome_policy)
    chrome_layout = FlowLayout(chrome_box, h_spacing=9, v_spacing=6)
    chrome_layout.setContentsMargins(16, 8, 16, 8)
    title_label = QLabel("Open Trofeo LCD")
    title_label.setObjectName("shellTitleLabel")
    shell_title_sub = QLabel("LCD control and themes.")
    shell_title_sub.setObjectName("shellTitleMeta")
    title_stack = QVBoxLayout()
    title_stack.setContentsMargins(0, 0, 0, 0)
    title_stack.setSpacing(1)
    title_stack.addWidget(title_label)
    title_stack.addWidget(shell_title_sub)
    title_widget = QWidget()
    title_widget.setLayout(title_stack)

    ui_mode_combo = QComboBox()
    ui_mode_combo.addItems(["Dark", "Light", "System"])
    ui_mode_combo.setToolTip("Application theme: Dark, Light, or follow the desktop (System).")
    ui_theme_combo = QComboBox()
    ui_theme_combo.addItems(ui_theme_names)
    ui_theme_combo.hide()
    ui_scale_combo = QComboBox()
    for value in (70, 80, 90, 100, 110, 125, 140):
        ui_scale_combo.addItem(f"{value}%", value)
    ui_scale_combo.setCurrentText("100%")
    for combo in (ui_mode_combo, ui_scale_combo):
        combo.setMinimumHeight(34)
        combo.setMaxVisibleItems(8)

    header_connection_label = QLabel("● Disconnected")
    header_connection_label.setObjectName("headerStatusBadge")
    header_device_combo = QComboBox()
    header_device_combo.addItem("Trofeo LCD")
    header_device_combo.setMinimumHeight(34)
    header_ready_label = QLabel("Ready")
    header_ready_label.setObjectName("headerReadyBadge")
    header_language_combo = QComboBox()
    for label, code in ui_languages.items():
        header_language_combo.addItem(label, code)
    header_language_combo.setMinimumHeight(34)
    header_donate_btn = QPushButton("Donate")
    header_donate_btn.setObjectName("primaryButton")
    header_donate_btn.setMinimumHeight(34)
    header_donate_btn.clicked.connect(callbacks.open_donate)
    header_donate_btn.setToolTip("Open GitHub Sponsors for Open Trofeo LCD")

    chrome_layout.addWidget(title_widget)
    header_mode_label = QLabel("Mode")
    header_mode_label.setObjectName("headerFieldLabel")
    header_scale_label = QLabel("Scale")
    header_scale_label.setObjectName("headerFieldLabel")
    header_conn_label = QLabel("Connection")
    header_conn_label.setObjectName("headerFieldLabel")
    header_device_label = QLabel("Device")
    header_device_label.setObjectName("headerFieldLabel")
    header_language_label = QLabel("Language")
    header_language_label.setObjectName("headerFieldLabel")
    for widget in (
        header_mode_label,
        ui_mode_combo,
        header_scale_label,
        ui_scale_combo,
    ):
        chrome_layout.addWidget(widget)
    chrome_layout.addSpacing(6)
    for widget in (
        header_conn_label,
        header_connection_label,
        header_device_label,
        header_device_combo,
        header_language_label,
        header_language_combo,
        header_ready_label,
    ):
        chrome_layout.addWidget(widget)
    chrome_layout.addSpacing(8)
    chrome_layout.addWidget(header_donate_btn)
    outer.addWidget(chrome_box)

    tabs = QTabWidget()
    tabs.setObjectName("mainSectionTabs")
    tabs.setDocumentMode(True)
    outer.addWidget(tabs, 1)
    runtime_tab, runtime_layout = _make_scroll_tab()
    studio_tab, studio_layout = _make_scroll_tab()
    automation_tab = QWidget()
    automation_layout = QVBoxLayout(automation_tab)
    automation_layout.setContentsMargins(8, 8, 8, 8)
    logs_tab = QWidget()
    logs_layout = QVBoxLayout(logs_tab)
    logs_layout.setContentsMargins(0, 0, 0, 0)
    tabs.addTab(runtime_tab, "System")
    tabs.addTab(studio_tab, "Theme Designer")
    tabs.addTab(automation_tab, "Configuration")
    tabs.addTab(logs_tab, "Logs")
    tabs.tabBar().hide()

    ui_mode_combo.currentTextChanged.connect(lambda _text: callbacks.apply_ui_chrome())
    ui_scale_combo.currentIndexChanged.connect(lambda _index: callbacks.apply_ui_chrome())
    header_language_combo.currentTextChanged.connect(callbacks.apply_language_selection)
    tabs.currentChanged.connect(lambda _idx: callbacks.main_tab_changed(tabs.currentWidget()))
    nav_system_btn.clicked.connect(callbacks.go_system)
    nav_logs_btn.clicked.connect(callbacks.go_logs)
    nav_config_btn.clicked.connect(callbacks.go_config)

    return ShellControls(
        root=root,
        sidebar_layout=sidebar_layout,
        brand_label=brand_label,
        brand_sub=brand_sub,
        sidebar_toggle_btn=sidebar_toggle_btn,
        nav_library_btn=nav_library_btn,
        nav_designer_btn=nav_designer_btn,
        nav_animation_studio_btn=nav_animation_studio_btn,
        nav_system_btn=nav_system_btn,
        nav_logs_btn=nav_logs_btn,
        nav_config_btn=nav_config_btn,
        nav_button_meta=nav_button_meta,
        shell_nav_buttons=shell_nav_buttons,
        sidebar_footer=sidebar_footer,
        sidebar_version_label=sidebar_version_label,
        sidebar_footer_note=sidebar_footer_note,
        sidebar_frame=sidebar,
        chrome_box=chrome_box,
        shell_title_sub=shell_title_sub,
        ui_mode_combo=ui_mode_combo,
        ui_theme_combo=ui_theme_combo,
        ui_scale_combo=ui_scale_combo,
        header_connection_label=header_connection_label,
        header_device_combo=header_device_combo,
        header_ready_label=header_ready_label,
        header_language_combo=header_language_combo,
        header_donate_btn=header_donate_btn,
        header_mode_label=header_mode_label,
        header_scale_label=header_scale_label,
        header_conn_label=header_conn_label,
        header_device_label=header_device_label,
        header_language_label=header_language_label,
        main_tabs=tabs,
        runtime_layout=runtime_layout,
        studio_layout=studio_layout,
        automation_layout=automation_layout,
        logs_layout=logs_layout,
    )
