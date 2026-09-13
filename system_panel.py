"""Qt builders for the System dashboard panel."""

from __future__ import annotations

import platform
import socket
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


SYSTEM_INTRO_TEXT = (
    "This tab shows backend status, device state and basic host metrics. "
    "Quick actions use the same live API endpoints as before."
)


@dataclass(frozen=True)
class SystemPanelCallbacks:
    restart_backend: Callable[[], None]
    restart_service: Callable[[], None]
    refresh_status: Callable[[], None]
    export_logs: Callable[[], None]
    diagnostics: Callable[[], None]


@dataclass(frozen=True)
class SystemPanelControls:
    panel: QWidget
    intro_label: QLabel
    backend_status_box: QGroupBox
    system_api_status_row: QWidget
    system_api_status_title: QLabel
    system_api_status_value: QLabel
    system_ws_status_row: QWidget
    system_ws_status_title: QLabel
    system_ws_status_value: QLabel
    system_lcd_status_row: QWidget
    system_lcd_status_title: QLabel
    system_lcd_status_value: QLabel
    system_queue_status_row: QWidget
    system_queue_status_title: QLabel
    system_queue_status_value: QLabel
    system_theme_engine_row: QWidget
    system_theme_engine_title: QLabel
    system_theme_engine_value: QLabel
    system_backup_row: QWidget
    system_backup_title: QLabel
    system_backup_value: QLabel
    system_info_box: QGroupBox
    system_os_value: QLabel
    system_framework_value: QLabel
    system_app_version_value: QLabel
    system_uptime_value: QLabel
    system_hostname_value: QLabel
    system_restart_value: QLabel
    resources_box: QGroupBox
    system_cpu_title: QLabel
    system_cpu_value: QLabel
    system_cpu_detail: QLabel
    system_mem_title: QLabel
    system_mem_value: QLabel
    system_mem_detail: QLabel
    system_disk_title: QLabel
    system_disk_value: QLabel
    system_disk_detail: QLabel
    system_temp_title: QLabel
    system_temp_value: QLabel
    system_temp_detail: QLabel
    runtime_dashboard_device_box: QGroupBox
    system_connection_value: QLabel
    system_device_value: QLabel
    system_firmware_value: QLabel
    system_resolution_value: QLabel
    system_ip_value: QLabel
    system_port_value: QLabel
    system_serial_value: QLabel
    system_events_box: QGroupBox
    system_events_header_labels: list[QLabel]
    system_events_list: QListWidget
    system_quick_actions_box: QGroupBox
    system_restart_backend_btn: QPushButton
    system_restart_service_btn: QPushButton
    system_refresh_status_btn: QPushButton
    system_export_logs_btn: QPushButton
    system_diagnostic_btn: QPushButton


def bind_system_panel_controls(owner, controls: SystemPanelControls) -> None:
    owner.system_intro_text_label = controls.intro_label
    owner.backend_status_box = controls.backend_status_box
    owner.system_api_status_row = controls.system_api_status_row
    owner.system_api_status_title = controls.system_api_status_title
    owner.system_api_status_value = controls.system_api_status_value
    owner.system_ws_status_row = controls.system_ws_status_row
    owner.system_ws_status_title = controls.system_ws_status_title
    owner.system_ws_status_value = controls.system_ws_status_value
    owner.system_lcd_status_row = controls.system_lcd_status_row
    owner.system_lcd_status_title = controls.system_lcd_status_title
    owner.system_lcd_status_value = controls.system_lcd_status_value
    owner.system_queue_status_row = controls.system_queue_status_row
    owner.system_queue_status_title = controls.system_queue_status_title
    owner.system_queue_status_value = controls.system_queue_status_value
    owner.system_theme_engine_row = controls.system_theme_engine_row
    owner.system_theme_engine_title = controls.system_theme_engine_title
    owner.system_theme_engine_value = controls.system_theme_engine_value
    owner.system_backup_row = controls.system_backup_row
    owner.system_backup_title = controls.system_backup_title
    owner.system_backup_value = controls.system_backup_value
    owner.system_info_box = controls.system_info_box
    owner.system_os_value = controls.system_os_value
    owner.system_framework_value = controls.system_framework_value
    owner.system_app_version_value = controls.system_app_version_value
    owner.system_uptime_value = controls.system_uptime_value
    owner.system_hostname_value = controls.system_hostname_value
    owner.system_restart_value = controls.system_restart_value
    owner.resources_box = controls.resources_box
    owner.system_cpu_title = controls.system_cpu_title
    owner.system_cpu_value = controls.system_cpu_value
    owner.system_cpu_detail = controls.system_cpu_detail
    owner.system_mem_title = controls.system_mem_title
    owner.system_mem_value = controls.system_mem_value
    owner.system_mem_detail = controls.system_mem_detail
    owner.system_disk_title = controls.system_disk_title
    owner.system_disk_value = controls.system_disk_value
    owner.system_disk_detail = controls.system_disk_detail
    owner.system_temp_title = controls.system_temp_title
    owner.system_temp_value = controls.system_temp_value
    owner.system_temp_detail = controls.system_temp_detail
    owner.runtime_dashboard_device_box = controls.runtime_dashboard_device_box
    owner.system_connection_value = controls.system_connection_value
    owner.system_device_value = controls.system_device_value
    owner.system_firmware_value = controls.system_firmware_value
    owner.system_resolution_value = controls.system_resolution_value
    owner.system_ip_value = controls.system_ip_value
    owner.system_port_value = controls.system_port_value
    owner.system_serial_value = controls.system_serial_value
    owner.system_events_box = controls.system_events_box
    owner.system_events_header_labels = controls.system_events_header_labels
    owner.system_events_list = controls.system_events_list
    owner.system_quick_actions_box = controls.system_quick_actions_box
    owner.system_restart_backend_btn = controls.system_restart_backend_btn
    owner.system_restart_service_btn = controls.system_restart_service_btn
    owner.system_refresh_status_btn = controls.system_refresh_status_btn
    owner.system_export_logs_btn = controls.system_export_logs_btn
    owner.system_diagnostic_btn = controls.system_diagnostic_btn


def build_system_panel(
    *,
    app_version_text: str,
    callbacks: SystemPanelCallbacks,
    intro_card_factory: Callable[[str], QWidget],
    status_row_factory: Callable[[str, str], tuple[QWidget, QLabel, QLabel]],
    metric_card_factory: Callable[[str], tuple[QFrame, QLabel, QLabel, QLabel]],
) -> SystemPanelControls:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    system_intro = intro_card_factory("runtimeHeroCard")
    system_intro_layout = QHBoxLayout(system_intro)
    system_intro_layout.setContentsMargins(18, 16, 18, 16)
    intro_label = QLabel(SYSTEM_INTRO_TEXT)
    intro_label.setObjectName("studioHeroText")
    intro_label.setWordWrap(True)
    system_intro_layout.addWidget(intro_label)
    layout.addWidget(system_intro)

    top_row = QHBoxLayout()
    top_row.setSpacing(10)

    backend_status_box = QGroupBox("Backend status")
    backend_status_box.setObjectName("dashboardCardBox")
    backend_status_layout = QVBoxLayout(backend_status_box)
    backend_status_layout.setSpacing(10)
    system_api_status_row, system_api_status_title, system_api_status_value = status_row_factory("API Server", "Offline")
    system_ws_status_row, system_ws_status_title, system_ws_status_value = status_row_factory("WebSocket", "Offline")
    system_lcd_status_row, system_lcd_status_title, system_lcd_status_value = status_row_factory("LCD Daemon", "Idle")
    system_queue_status_row, system_queue_status_title, system_queue_status_value = status_row_factory("Queue Worker", "Idle")
    system_theme_engine_row, system_theme_engine_title, system_theme_engine_value = status_row_factory("Theme Engine", "Ready")
    system_backup_row, system_backup_title, system_backup_value = status_row_factory("Auto Backup", "Idle")
    for row in (
        system_api_status_row,
        system_ws_status_row,
        system_lcd_status_row,
        system_queue_status_row,
        system_theme_engine_row,
        system_backup_row,
    ):
        backend_status_layout.addWidget(row)
    backend_status_layout.addStretch(1)
    top_row.addWidget(backend_status_box, 1)

    system_info_box = QGroupBox("System information")
    system_info_box.setObjectName("dashboardCardBox")
    system_info_grid = QGridLayout(system_info_box)
    system_info_grid.setColumnStretch(1, 1)
    system_os_value = QLabel(platform.system())
    system_framework_value = QLabel("Qt 6 / PySide6")
    system_app_version_value = QLabel(app_version_text)
    system_uptime_value = QLabel("-")
    system_hostname_value = QLabel(socket.gethostname())
    system_restart_value = QLabel("-")
    for idx, (label_text, value_lbl) in enumerate(
        [
            ("Operating system:", system_os_value),
            ("Framework:", system_framework_value),
            ("App version:", system_app_version_value),
            ("Uptime:", system_uptime_value),
            ("Hostname:", system_hostname_value),
            ("Last restart:", system_restart_value),
        ]
    ):
        system_info_grid.addWidget(QLabel(label_text), idx, 0)
        system_info_grid.addWidget(value_lbl, idx, 1)
    top_row.addWidget(system_info_box, 1)

    resources_box = QGroupBox("System resources")
    resources_box.setObjectName("dashboardCardBox")
    resources_layout = QHBoxLayout(resources_box)
    resources_layout.setSpacing(10)
    cpu_card, system_cpu_title, system_cpu_value, system_cpu_detail = metric_card_factory("CPU")
    mem_card, system_mem_title, system_mem_value, system_mem_detail = metric_card_factory("RAM")
    disk_card, system_disk_title, system_disk_value, system_disk_detail = metric_card_factory("DISK")
    temp_card, system_temp_title, system_temp_value, system_temp_detail = metric_card_factory("TEMP")
    for card in (cpu_card, mem_card, disk_card, temp_card):
        resources_layout.addWidget(card, 1)
    top_row.addWidget(resources_box, 1)
    layout.addLayout(top_row)

    bottom_row = QHBoxLayout()
    bottom_row.setSpacing(14)

    device_box = QGroupBox("Network & device")
    device_box.setObjectName("dashboardCardBox")
    device_grid = QGridLayout(device_box)
    device_grid.setColumnStretch(1, 1)
    system_connection_value = QLabel("-")
    system_device_value = QLabel("Trofeo LCD")
    system_firmware_value = QLabel("-")
    system_resolution_value = QLabel("1920 x 462")
    system_ip_value = QLabel("127.0.0.1")
    system_port_value = QLabel("18777")
    system_serial_value = QLabel("-")
    for idx, (label_text, value_lbl) in enumerate(
        [
            ("Connection:", system_connection_value),
            ("Device:", system_device_value),
            ("Firmware:", system_firmware_value),
            ("Resolution:", system_resolution_value),
            ("IP address:", system_ip_value),
            ("API port:", system_port_value),
            ("USB/Serial:", system_serial_value),
        ]
    ):
        device_grid.addWidget(QLabel(label_text), idx, 0)
        device_grid.addWidget(value_lbl, idx, 1)
    bottom_row.addWidget(device_box, 1)

    events_box = QGroupBox("System events")
    events_box.setObjectName("dashboardCardBox")
    events_layout = QVBoxLayout(events_box)
    events_header = QHBoxLayout()
    system_events_header_labels: list[QLabel] = []
    for title, stretch in (("Time", 1), ("Level", 1), ("Source", 2), ("Message", 4)):
        label = QLabel(title)
        label.setObjectName("eventHeaderLabel")
        system_events_header_labels.append(label)
        events_header.addWidget(label, stretch)
    events_layout.addLayout(events_header)
    system_events_list = QListWidget()
    system_events_list.setMinimumHeight(260)
    system_events_list.setObjectName("systemEventsList")
    events_layout.addWidget(system_events_list)
    bottom_row.addWidget(events_box, 2)

    quick_actions_box = QGroupBox("Quick actions")
    quick_actions_box.setObjectName("dashboardCardBox")
    quick_actions_layout = QVBoxLayout(quick_actions_box)
    system_restart_backend_btn = QPushButton("Restart backend")
    system_restart_service_btn = QPushButton("Restart service")
    system_refresh_status_btn = QPushButton("Refresh status")
    system_export_logs_btn = QPushButton("Export logs")
    system_diagnostic_btn = QPushButton("Diagnostics")
    system_restart_backend_btn.clicked.connect(callbacks.restart_backend)
    system_restart_service_btn.clicked.connect(callbacks.restart_service)
    system_refresh_status_btn.clicked.connect(callbacks.refresh_status)
    system_export_logs_btn.clicked.connect(callbacks.export_logs)
    system_diagnostic_btn.clicked.connect(callbacks.diagnostics)
    for button in (
        system_restart_backend_btn,
        system_restart_service_btn,
        system_refresh_status_btn,
        system_export_logs_btn,
        system_diagnostic_btn,
    ):
        button.setMinimumHeight(44)
        button.setObjectName("quickActionButton")
        quick_actions_layout.addWidget(button)
    quick_actions_layout.addStretch(1)
    bottom_row.addWidget(quick_actions_box, 1)
    layout.addLayout(bottom_row)
    layout.addStretch(1)

    return SystemPanelControls(
        panel=panel,
        intro_label=intro_label,
        backend_status_box=backend_status_box,
        system_api_status_row=system_api_status_row,
        system_api_status_title=system_api_status_title,
        system_api_status_value=system_api_status_value,
        system_ws_status_row=system_ws_status_row,
        system_ws_status_title=system_ws_status_title,
        system_ws_status_value=system_ws_status_value,
        system_lcd_status_row=system_lcd_status_row,
        system_lcd_status_title=system_lcd_status_title,
        system_lcd_status_value=system_lcd_status_value,
        system_queue_status_row=system_queue_status_row,
        system_queue_status_title=system_queue_status_title,
        system_queue_status_value=system_queue_status_value,
        system_theme_engine_row=system_theme_engine_row,
        system_theme_engine_title=system_theme_engine_title,
        system_theme_engine_value=system_theme_engine_value,
        system_backup_row=system_backup_row,
        system_backup_title=system_backup_title,
        system_backup_value=system_backup_value,
        system_info_box=system_info_box,
        system_os_value=system_os_value,
        system_framework_value=system_framework_value,
        system_app_version_value=system_app_version_value,
        system_uptime_value=system_uptime_value,
        system_hostname_value=system_hostname_value,
        system_restart_value=system_restart_value,
        resources_box=resources_box,
        system_cpu_title=system_cpu_title,
        system_cpu_value=system_cpu_value,
        system_cpu_detail=system_cpu_detail,
        system_mem_title=system_mem_title,
        system_mem_value=system_mem_value,
        system_mem_detail=system_mem_detail,
        system_disk_title=system_disk_title,
        system_disk_value=system_disk_value,
        system_disk_detail=system_disk_detail,
        system_temp_title=system_temp_title,
        system_temp_value=system_temp_value,
        system_temp_detail=system_temp_detail,
        runtime_dashboard_device_box=device_box,
        system_connection_value=system_connection_value,
        system_device_value=system_device_value,
        system_firmware_value=system_firmware_value,
        system_resolution_value=system_resolution_value,
        system_ip_value=system_ip_value,
        system_port_value=system_port_value,
        system_serial_value=system_serial_value,
        system_events_box=events_box,
        system_events_header_labels=system_events_header_labels,
        system_events_list=system_events_list,
        system_quick_actions_box=quick_actions_box,
        system_restart_backend_btn=system_restart_backend_btn,
        system_restart_service_btn=system_restart_service_btn,
        system_refresh_status_btn=system_refresh_status_btn,
        system_export_logs_btn=system_export_logs_btn,
        system_diagnostic_btn=system_diagnostic_btn,
    )
