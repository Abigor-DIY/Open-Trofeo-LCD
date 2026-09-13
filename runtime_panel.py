"""Legacy runtime control panel builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class LegacyRuntimeCallbacks:
    apply_url: Callable[[], None]
    refresh_status: Callable[[], None]
    start: Callable[[], None]
    stop: Callable[[], None]
    restart: Callable[[], None]
    scan: Callable[[], None]
    hide_to_tray: Callable[[], None]
    animate_widget: Callable[[QWidget], None]
    set_frame: Callable[[], None]
    browse_image: Callable[[], None]
    prepare_image: Callable[[QLineEdit], None]
    send_image: Callable[[], None]
    apply_config: Callable[[], None]
    run_usb_recovery: Callable[[], None]
    refresh_themes: Callable[[], None]
    apply_theme: Callable[[], None]
    remove_theme: Callable[[], None]
    browse_theme_path: Callable[[], None]
    add_or_update_theme: Callable[[], None]


@dataclass(frozen=True)
class LegacyRuntimeControls:
    panel: QWidget
    endpoint_box: QGroupBox
    url_edit: QLineEdit
    apply_url_btn: QPushButton
    refresh_btn: QPushButton
    control_box: QGroupBox
    start_btn: QPushButton
    stop_btn: QPushButton
    restart_btn: QPushButton
    scan_btn: QPushButton
    hide_to_tray_btn: QPushButton
    runtime_hero_text_label: QLabel
    runtime_sections_tabs: QTabWidget
    work_box: QGroupBox
    frame_spin: QSpinBox
    set_frame_btn: QPushButton
    image_edit: QLineEdit
    browse_btn: QPushButton
    prepare_image_btn: QPushButton
    send_image_btn: QPushButton
    raw_passthrough_chk: QCheckBox
    stop_before_send_chk: QCheckBox
    resume_loop_chk: QCheckBox
    cfg_box: QGroupBox
    pcap_edit: QLineEdit
    ack_timeout_spin: QSpinBox
    inter_delay_spin: QDoubleSpinBox
    frame_delay_spin: QDoubleSpinBox
    apply_cfg_btn: QPushButton
    status_box: QGroupBox
    lbl_mode: QLabel
    lbl_running: QLabel
    lbl_pid: QLabel
    lbl_uptime: QLabel
    lbl_frame_count: QLabel
    lbl_playlist: QLabel
    lbl_playlist_uptime: QLabel
    lbl_last_error: QLabel
    lbl_pcap: QLabel
    usb_recovery_hint_label: QLabel
    usb_recovery_btn: QPushButton
    runtime_legacy_theme_box: QGroupBox
    theme_combo: QComboBox
    theme_refresh_btn: QPushButton
    theme_apply_btn: QPushButton
    theme_remove_btn: QPushButton
    theme_name_edit: QLineEdit
    theme_path_edit: QLineEdit
    theme_browse_btn: QPushButton
    theme_prepare_btn: QPushButton
    theme_add_btn: QPushButton
    theme_raw_chk: QCheckBox
    theme_stop_before_apply_chk: QCheckBox
    theme_resume_chk: QCheckBox
    runtime_theme_cards_box: QGroupBox
    runtime_theme_cards_container: QWidget
    runtime_theme_cards_layout: QVBoxLayout


def bind_legacy_runtime_controls(owner, controls: LegacyRuntimeControls) -> None:
    owner.endpoint_box = controls.endpoint_box
    owner.url_edit = controls.url_edit
    owner.apply_url_btn = controls.apply_url_btn
    owner.refresh_btn = controls.refresh_btn
    owner.control_box = controls.control_box
    owner.start_btn = controls.start_btn
    owner.stop_btn = controls.stop_btn
    owner.restart_btn = controls.restart_btn
    owner.scan_btn = controls.scan_btn
    owner.hide_to_tray_btn = controls.hide_to_tray_btn
    owner.runtime_hero_text_label = controls.runtime_hero_text_label
    owner.runtime_sections_tabs = controls.runtime_sections_tabs
    owner.work_box = controls.work_box
    owner.frame_spin = controls.frame_spin
    owner.set_frame_btn = controls.set_frame_btn
    owner.image_edit = controls.image_edit
    owner.browse_btn = controls.browse_btn
    owner.prepare_image_btn = controls.prepare_image_btn
    owner.send_image_btn = controls.send_image_btn
    owner.raw_passthrough_chk = controls.raw_passthrough_chk
    owner.stop_before_send_chk = controls.stop_before_send_chk
    owner.resume_loop_chk = controls.resume_loop_chk
    owner.cfg_box = controls.cfg_box
    owner.pcap_edit = controls.pcap_edit
    owner.ack_timeout_spin = controls.ack_timeout_spin
    owner.inter_delay_spin = controls.inter_delay_spin
    owner.frame_delay_spin = controls.frame_delay_spin
    owner.apply_cfg_btn = controls.apply_cfg_btn
    owner.status_box = controls.status_box
    owner.lbl_mode = controls.lbl_mode
    owner.lbl_running = controls.lbl_running
    owner.lbl_pid = controls.lbl_pid
    owner.lbl_uptime = controls.lbl_uptime
    owner.lbl_frame_count = controls.lbl_frame_count
    owner.lbl_playlist = controls.lbl_playlist
    owner.lbl_playlist_uptime = controls.lbl_playlist_uptime
    owner.lbl_last_error = controls.lbl_last_error
    owner.lbl_pcap = controls.lbl_pcap
    owner.usb_recovery_hint_label = controls.usb_recovery_hint_label
    owner.usb_recovery_btn = controls.usb_recovery_btn
    owner.runtime_legacy_theme_box = controls.runtime_legacy_theme_box
    owner.theme_combo = controls.theme_combo
    owner.theme_refresh_btn = controls.theme_refresh_btn
    owner.theme_apply_btn = controls.theme_apply_btn
    owner.theme_remove_btn = controls.theme_remove_btn
    owner.theme_name_edit = controls.theme_name_edit
    owner.theme_path_edit = controls.theme_path_edit
    owner.theme_browse_btn = controls.theme_browse_btn
    owner.theme_prepare_btn = controls.theme_prepare_btn
    owner.theme_add_btn = controls.theme_add_btn
    owner.theme_raw_chk = controls.theme_raw_chk
    owner.theme_stop_before_apply_chk = controls.theme_stop_before_apply_chk
    owner.theme_resume_chk = controls.theme_resume_chk
    owner.runtime_theme_cards_box = controls.runtime_theme_cards_box
    owner.runtime_theme_cards_container = controls.runtime_theme_cards_container
    owner.runtime_theme_cards_layout = controls.runtime_theme_cards_layout


def _make_status_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("color: #94a3b8; font-weight: 600;")
    return label


def _style_value_label(label: QLabel) -> None:
    label.setStyleSheet("color: #f1f5f9; font-weight: 700; background: #1a202c; border-radius: 6px; padding: 4px 8px;")


def build_legacy_runtime_panel(
    *,
    base_url: str,
    callbacks: LegacyRuntimeCallbacks,
    intro_card_factory: Callable[[str], QWidget],
) -> LegacyRuntimeControls:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(20)

    endpoint_box = QGroupBox("Backend")
    endpoint_layout = QHBoxLayout(endpoint_box)
    url_edit = QLineEdit(base_url)
    apply_url_btn = QPushButton("Set URL")
    refresh_btn = QPushButton("Refresh status")
    apply_url_btn.clicked.connect(callbacks.apply_url)
    refresh_btn.clicked.connect(callbacks.refresh_status)
    endpoint_layout.addWidget(QLabel("URL:"))
    endpoint_layout.addWidget(url_edit, 1)
    endpoint_layout.addWidget(apply_url_btn)
    endpoint_layout.addWidget(refresh_btn)
    layout.addWidget(endpoint_box)

    control_box = QGroupBox("Device control")
    control_layout = QHBoxLayout(control_box)
    control_layout.setContentsMargins(16, 20, 16, 16)
    control_layout.setSpacing(12)
    start_btn = QPushButton("▶ Start")
    start_btn.setObjectName("primaryButton")
    stop_btn = QPushButton("⏹ Stop")
    restart_btn = QPushButton("🔄 Restart")
    scan_btn = QPushButton("🔍 Scan")
    hide_to_tray_btn = QPushButton("📥 Minimize to tray")
    for button in (start_btn, stop_btn, restart_btn):
        button.setMinimumHeight(44)
    start_btn.clicked.connect(callbacks.start)
    stop_btn.clicked.connect(callbacks.stop)
    restart_btn.clicked.connect(callbacks.restart)
    scan_btn.clicked.connect(callbacks.scan)
    hide_to_tray_btn.clicked.connect(callbacks.hide_to_tray)
    for button in (start_btn, stop_btn, restart_btn, scan_btn, hide_to_tray_btn):
        control_layout.addWidget(button, 1)
    layout.addWidget(control_box)

    runtime_hero = intro_card_factory("runtimeHeroCard")
    runtime_hero_layout = QHBoxLayout(runtime_hero)
    runtime_hero_layout.setContentsMargins(18, 16, 18, 16)
    runtime_hero_text_label = QLabel(
        "Control the panel like a native Plasma app: start the runtime, push single frames "
        "and manage themes from clear cards instead of raw fields."
    )
    runtime_hero_text_label.setObjectName("studioHeroText")
    runtime_hero_text_label.setWordWrap(True)
    runtime_hero_layout.addWidget(runtime_hero_text_label, 1)
    layout.addWidget(runtime_hero)

    runtime_sections_tabs = QTabWidget()
    runtime_sections_tabs.setDocumentMode(True)
    runtime_sections_tabs.currentChanged.connect(lambda _idx: callbacks.animate_widget(runtime_sections_tabs.currentWidget()))
    layout.addWidget(runtime_sections_tabs, 1)

    runtime_device_tab = QWidget()
    runtime_device_layout = QVBoxLayout(runtime_device_tab)
    runtime_device_layout.setContentsMargins(0, 0, 0, 0)
    runtime_device_layout.setSpacing(10)
    runtime_sections_tabs.addTab(runtime_device_tab, "Device")

    runtime_image_tab = QWidget()
    runtime_image_layout = QVBoxLayout(runtime_image_tab)
    runtime_image_layout.setContentsMargins(0, 0, 0, 0)
    runtime_image_layout.setSpacing(10)
    runtime_sections_tabs.addTab(runtime_image_tab, "Image")

    runtime_theme_tab = QWidget()
    runtime_theme_layout = QVBoxLayout(runtime_theme_tab)
    runtime_theme_layout.setContentsMargins(0, 0, 0, 0)
    runtime_theme_layout.setSpacing(10)
    runtime_sections_tabs.addTab(runtime_theme_tab, "Themes")

    work_box = QGroupBox("Single image")
    work_layout = QVBoxLayout(work_box)
    work_layout.setSpacing(8)
    frame_spin = QSpinBox()
    frame_spin.setRange(0, 1_000_000)
    set_frame_btn = QPushButton("Set frame")
    set_frame_btn.clicked.connect(callbacks.set_frame)
    frame_row = QHBoxLayout()
    frame_row.addWidget(QLabel("Frame index:"))
    frame_row.addWidget(frame_spin)
    frame_row.addWidget(set_frame_btn)
    frame_row.addStretch(1)
    work_layout.addLayout(frame_row)

    image_edit = QLineEdit(str(Path("reference_frame_trcc.jpg")))
    browse_btn = QPushButton("Browse image")
    prepare_image_btn = QPushButton("Prepare image")
    send_image_btn = QPushButton("Send image")
    raw_passthrough_chk = QCheckBox("Raw JPEG passthrough")
    stop_before_send_chk = QCheckBox("Stop runtime before sending")
    resume_loop_chk = QCheckBox("Resume loop after send")
    stop_before_send_chk.setChecked(True)
    browse_btn.clicked.connect(callbacks.browse_image)
    prepare_image_btn.clicked.connect(lambda: callbacks.prepare_image(image_edit))
    send_image_btn.clicked.connect(callbacks.send_image)
    file_row = QHBoxLayout()
    file_row.addWidget(QLabel("Image file:"))
    file_row.addWidget(image_edit, 1)
    file_row.addWidget(browse_btn)
    file_row.addWidget(prepare_image_btn)
    file_row.addWidget(send_image_btn)
    work_layout.addLayout(file_row)
    options_row = QHBoxLayout()
    options_row.addWidget(raw_passthrough_chk)
    options_row.addWidget(stop_before_send_chk)
    options_row.addWidget(resume_loop_chk)
    options_row.addStretch(1)
    work_layout.addLayout(options_row)
    runtime_image_layout.addWidget(work_box)

    cfg_status_row = QHBoxLayout()
    cfg_box = QGroupBox("Playback settings")
    cfg_form = QFormLayout(cfg_box)
    pcap_edit = QLineEdit("dzis.pcapng")
    ack_timeout_spin = QSpinBox()
    ack_timeout_spin.setRange(1, 60000)
    ack_timeout_spin.setValue(500)
    inter_delay_spin = QDoubleSpinBox()
    inter_delay_spin.setRange(0.0, 5.0)
    inter_delay_spin.setSingleStep(0.005)
    inter_delay_spin.setValue(0.01)
    frame_delay_spin = QDoubleSpinBox()
    frame_delay_spin.setRange(0.0, 5.0)
    frame_delay_spin.setSingleStep(0.005)
    frame_delay_spin.setValue(0.02)
    apply_cfg_btn = QPushButton("Apply config")
    apply_cfg_btn.clicked.connect(callbacks.apply_config)
    cfg_form.addRow("PCAP file:", pcap_edit)
    cfg_form.addRow("ACK timeout (ms):", ack_timeout_spin)
    cfg_form.addRow("Inter packet delay (s):", inter_delay_spin)
    cfg_form.addRow("Frame delay (s):", frame_delay_spin)
    cfg_form.addRow("", apply_cfg_btn)
    cfg_status_row.addWidget(cfg_box, 1)

    status_box = QGroupBox("System monitor")
    status_grid = QGridLayout(status_box)
    status_grid.setContentsMargins(16, 24, 16, 16)
    status_grid.setSpacing(12)
    status_grid.setVerticalSpacing(16)
    lbl_mode = QLabel("-")
    lbl_running = QLabel("-")
    lbl_pid = QLabel("-")
    lbl_uptime = QLabel("-")
    lbl_frame_count = QLabel("-")
    lbl_playlist = QLabel("-")
    lbl_playlist_uptime = QLabel("-")
    lbl_last_error = QLabel("-")
    lbl_pcap = QLabel("-")
    for label in (lbl_mode, lbl_running, lbl_pid, lbl_uptime, lbl_frame_count, lbl_playlist, lbl_playlist_uptime, lbl_pcap):
        _style_value_label(label)
    lbl_last_error.setStyleSheet("color: #f87171; font-family: monospace; font-size: 11px;")
    status_rows = [
        ("📟 Mode:", lbl_mode, "🚦 Status:", lbl_running),
        ("🆔 PID:", lbl_pid, "⏱ Uptime:", lbl_uptime),
        ("🖼 Frames:", lbl_frame_count, "📂 PCAP:", lbl_pcap),
        ("🎵 Playlist:", lbl_playlist, "⏳ PL time:", lbl_playlist_uptime),
    ]
    for row, (label_a, value_a, label_b, value_b) in enumerate(status_rows):
        status_grid.addWidget(_make_status_label(label_a), row, 0)
        status_grid.addWidget(value_a, row, 1)
        status_grid.addWidget(_make_status_label(label_b), row, 2)
        status_grid.addWidget(value_b, row, 3)
    status_grid.addWidget(_make_status_label("⚠️ Error:"), 4, 0)
    status_grid.addWidget(lbl_last_error, 4, 1, 1, 3)
    cfg_status_row.addWidget(status_box, 1)
    runtime_device_layout.addLayout(cfg_status_row)

    recovery_box = QGroupBox("LCD USB recovery")
    recovery_layout = QHBoxLayout(recovery_box)
    recovery_layout.setContentsMargins(16, 18, 16, 14)
    recovery_layout.setSpacing(10)
    usb_recovery_hint_label = QLabel(
        "Use after deep suspend, USB timeout or frozen clock/EQ. Requires sudo and briefly resets the Trofeo LCD USB device. "
        "A full PC reboot usually helps too; if USB remains powered in standby, power off the PC for a few seconds."
    )
    usb_recovery_hint_label.setWordWrap(True)
    usb_recovery_hint_label.setStyleSheet("color: #a8b3c7;")
    usb_recovery_btn = QPushButton("Run USB recovery...")
    usb_recovery_btn.setToolTip("Runs scripts/trofeo_usb_power_cycle.sh from a terminal with sudo, then restarts the backend.")
    usb_recovery_btn.clicked.connect(callbacks.run_usb_recovery)
    recovery_layout.addWidget(usb_recovery_hint_label, 1)
    recovery_layout.addWidget(usb_recovery_btn)
    runtime_device_layout.addWidget(recovery_box)
    runtime_device_layout.addStretch(1)

    theme_box = QGroupBox("Theme library")
    theme_layout = QVBoxLayout(theme_box)
    theme_layout.setSpacing(8)
    theme_combo = QComboBox()
    theme_refresh_btn = QPushButton("Refresh list")
    theme_apply_btn = QPushButton("Apply theme")
    theme_remove_btn = QPushButton("Remove theme")
    theme_refresh_btn.clicked.connect(callbacks.refresh_themes)
    theme_apply_btn.clicked.connect(callbacks.apply_theme)
    theme_remove_btn.clicked.connect(callbacks.remove_theme)
    theme_row_1 = QHBoxLayout()
    theme_row_1.addWidget(QLabel("Theme:"))
    theme_row_1.addWidget(theme_combo, 1)
    theme_row_1.addWidget(theme_refresh_btn)
    theme_row_1.addWidget(theme_apply_btn)
    theme_row_1.addWidget(theme_remove_btn)
    theme_layout.addLayout(theme_row_1)
    theme_name_edit = QLineEdit()
    theme_path_edit = QLineEdit(str(Path("reference_frame_trcc.jpg")))
    theme_browse_btn = QPushButton("Browse file")
    theme_prepare_btn = QPushButton("Prepare image")
    theme_add_btn = QPushButton("Add / update theme")
    theme_raw_chk = QCheckBox("Raw JPEG passthrough (theme)")
    theme_stop_before_apply_chk = QCheckBox("Stop runtime before apply")
    theme_resume_chk = QCheckBox("Resume loop after apply")
    theme_stop_before_apply_chk.setChecked(True)
    theme_browse_btn.clicked.connect(callbacks.browse_theme_path)
    theme_prepare_btn.clicked.connect(lambda: callbacks.prepare_image(theme_path_edit))
    theme_add_btn.clicked.connect(callbacks.add_or_update_theme)
    theme_row_2 = QHBoxLayout()
    theme_row_2.addWidget(QLabel("Name:"))
    theme_row_2.addWidget(theme_name_edit, 1)
    theme_layout.addLayout(theme_row_2)
    theme_row_3 = QHBoxLayout()
    theme_row_3.addWidget(QLabel("File:"))
    theme_row_3.addWidget(theme_path_edit, 1)
    theme_row_3.addWidget(theme_browse_btn)
    theme_row_3.addWidget(theme_prepare_btn)
    theme_row_3.addWidget(theme_add_btn)
    theme_layout.addLayout(theme_row_3)
    theme_row_4 = QHBoxLayout()
    theme_row_4.addWidget(theme_raw_chk)
    theme_row_4.addWidget(theme_stop_before_apply_chk)
    theme_row_4.addWidget(theme_resume_chk)
    theme_row_4.addStretch(1)
    theme_layout.addLayout(theme_row_4)
    runtime_theme_layout.addWidget(theme_box)

    runtime_theme_cards_box = QGroupBox("Theme cards")
    runtime_theme_cards_layout_outer = QVBoxLayout(runtime_theme_cards_box)
    runtime_theme_cards_scroll = QScrollArea()
    runtime_theme_cards_scroll.setWidgetResizable(True)
    runtime_theme_cards_scroll.setFrameShape(QScrollArea.NoFrame)
    runtime_theme_cards_container = QWidget()
    runtime_theme_cards_layout = QVBoxLayout(runtime_theme_cards_container)
    runtime_theme_cards_layout.setContentsMargins(0, 0, 0, 0)
    runtime_theme_cards_layout.setSpacing(12)
    runtime_theme_cards_scroll.setWidget(runtime_theme_cards_container)
    runtime_theme_cards_layout_outer.addWidget(runtime_theme_cards_scroll)
    runtime_theme_layout.addWidget(runtime_theme_cards_box, 1)
    runtime_theme_layout.addStretch(1)

    return LegacyRuntimeControls(
        panel=panel,
        endpoint_box=endpoint_box,
        url_edit=url_edit,
        apply_url_btn=apply_url_btn,
        refresh_btn=refresh_btn,
        control_box=control_box,
        start_btn=start_btn,
        stop_btn=stop_btn,
        restart_btn=restart_btn,
        scan_btn=scan_btn,
        hide_to_tray_btn=hide_to_tray_btn,
        runtime_hero_text_label=runtime_hero_text_label,
        runtime_sections_tabs=runtime_sections_tabs,
        work_box=work_box,
        frame_spin=frame_spin,
        set_frame_btn=set_frame_btn,
        image_edit=image_edit,
        browse_btn=browse_btn,
        prepare_image_btn=prepare_image_btn,
        send_image_btn=send_image_btn,
        raw_passthrough_chk=raw_passthrough_chk,
        stop_before_send_chk=stop_before_send_chk,
        resume_loop_chk=resume_loop_chk,
        cfg_box=cfg_box,
        pcap_edit=pcap_edit,
        ack_timeout_spin=ack_timeout_spin,
        inter_delay_spin=inter_delay_spin,
        frame_delay_spin=frame_delay_spin,
        apply_cfg_btn=apply_cfg_btn,
        status_box=status_box,
        lbl_mode=lbl_mode,
        lbl_running=lbl_running,
        lbl_pid=lbl_pid,
        lbl_uptime=lbl_uptime,
        lbl_frame_count=lbl_frame_count,
        lbl_playlist=lbl_playlist,
        lbl_playlist_uptime=lbl_playlist_uptime,
        lbl_last_error=lbl_last_error,
        lbl_pcap=lbl_pcap,
        usb_recovery_hint_label=usb_recovery_hint_label,
        usb_recovery_btn=usb_recovery_btn,
        runtime_legacy_theme_box=theme_box,
        theme_combo=theme_combo,
        theme_refresh_btn=theme_refresh_btn,
        theme_apply_btn=theme_apply_btn,
        theme_remove_btn=theme_remove_btn,
        theme_name_edit=theme_name_edit,
        theme_path_edit=theme_path_edit,
        theme_browse_btn=theme_browse_btn,
        theme_prepare_btn=theme_prepare_btn,
        theme_add_btn=theme_add_btn,
        theme_raw_chk=theme_raw_chk,
        theme_stop_before_apply_chk=theme_stop_before_apply_chk,
        theme_resume_chk=theme_resume_chk,
        runtime_theme_cards_box=runtime_theme_cards_box,
        runtime_theme_cards_container=runtime_theme_cards_container,
        runtime_theme_cards_layout=runtime_theme_cards_layout,
    )
