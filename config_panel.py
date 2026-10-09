"""Qt builders for the Configuration panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


CONFIG_INTRO_TEXT = (
    "Configuration centralizes interface settings, LCD preferences and integrations in one place. "
    "App theme management now lives here instead of the top control bar."
)


@dataclass(frozen=True)
class ConfigAppearanceControls:
    box: QGroupBox
    theme_combo: QComboBox
    mode_combo: QComboBox
    scale_combo: QComboBox
    font_scale_slider: QSlider
    animations_chk: QCheckBox
    compact_layout_chk: QCheckBox


@dataclass(frozen=True)
class ConfigLcdPreferencesControls:
    box: QGroupBox
    note_label: QLabel


@dataclass(frozen=True)
class ConfigQuickActionCallbacks:
    reset_defaults: Callable[[], None]
    export_config: Callable[[], None]
    import_config: Callable[[], None]
    clear_cache: Callable[[], None]
    restart_app: Callable[[], None]
    usb_recovery: Callable[[], None]


@dataclass(frozen=True)
class ConfigGamingFpsCallbacks:
    configure_layer: Callable[[], None]
    refresh_status: Callable[[], None]
    copy_steam_command: Callable[[], None]
    auto_theme_changed: Callable[[], None]
    refresh_vrr: Callable[[], None]
    set_vrr_policy: Callable[[str], None]


@dataclass(frozen=True)
class ConfigAudioEqCallbacks:
    apply_eq: Callable[[], None]
    mark_dirty: Callable[[], None]


@dataclass(frozen=True)
class ConfigWeatherCallbacks:
    search_city: Callable[[], None]
    apply_selected_city: Callable[[int], None]
    apply_weather: Callable[[], None]
    refresh_weather: Callable[[], None]


@dataclass(frozen=True)
class ConfigAutomationCallbacks:
    add_playlist_item: Callable[[], None]
    remove_playlist_item: Callable[[], None]
    start_playlist: Callable[[], None]
    stop_playlist: Callable[[], None]
    browse_bundle_path: Callable[[], None]
    save_bundle: Callable[[], None]
    load_bundle: Callable[[], None]


@dataclass(frozen=True)
class ConfigActionCallbacks:
    cancel: Callable[[], None]
    apply: Callable[[], None]
    save: Callable[[], None]


@dataclass(frozen=True)
class ConfigAutomationControls:
    box: QGroupBox
    playlist_list: QListWidget
    playlist_duration_spin: QDoubleSpinBox
    playlist_add_btn: QPushButton
    playlist_remove_btn: QPushButton
    playlist_start_btn: QPushButton
    playlist_stop_btn: QPushButton
    bundle_path_edit: QLineEdit
    bundle_merge_chk: QCheckBox
    bundle_browse_btn: QPushButton
    bundle_save_btn: QPushButton
    bundle_load_btn: QPushButton


@dataclass(frozen=True)
class ConfigActionControls:
    row: QHBoxLayout
    cancel_btn: QPushButton
    apply_btn: QPushButton
    save_btn: QPushButton


@dataclass(frozen=True)
class ConfigWeatherControls:
    box: QGroupBox
    city_search_edit: QLineEdit
    search_btn: QPushButton
    results_combo: QComboBox
    lat_edit: QLineEdit
    lon_edit: QLineEdit
    location_edit: QLineEdit
    refresh_spin: QSpinBox
    apply_btn: QPushButton
    refresh_now_btn: QPushButton
    status_label: QLabel


@dataclass(frozen=True)
class ConfigGamingFpsControls:
    box: QGroupBox
    setup_btn: QPushButton
    refresh_btn: QPushButton
    status_label: QLabel
    metrics_label: QLabel
    log_path_edit: QLineEdit
    steam_command_edit: QLineEdit
    copy_steam_command_btn: QPushButton
    hint_label: QLabel
    auto_theme_chk: QCheckBox
    auto_theme_combo: QComboBox
    auto_theme_restore_on_fps_loss_chk: QCheckBox
    auto_theme_fps_loss_delay_spin: QSpinBox
    auto_theme_status_label: QLabel
    vrr_status_label: QLabel
    vrr_refresh_btn: QPushButton
    vrr_automatic_btn: QPushButton
    vrr_always_btn: QPushButton
    vrr_off_btn: QPushButton


@dataclass(frozen=True)
class ConfigAudioEqControls:
    box: QGroupBox
    input_combo: QComboBox
    profile_combo: QComboBox
    sensitivity_spin: QSpinBox
    apply_btn: QPushButton
    status_label: QLabel


@dataclass(frozen=True)
class ConfigQuickActionControls:
    box: QGroupBox
    reset_btn: QPushButton
    export_btn: QPushButton
    import_btn: QPushButton
    clear_cache_btn: QPushButton
    restart_app_btn: QPushButton
    usb_recovery_btn: QPushButton
    usb_recovery_note_label: QLabel


@dataclass(frozen=True)
class ConfigRuntimePathControls:
    box: QGroupBox
    app_path_edit: QLineEdit
    theme_path_edit: QLineEdit
    state_path_edit: QLineEdit
    fps_socket_path_edit: QLineEdit


@dataclass(frozen=True)
class ConfigPanelCallbacks:
    gaming_fps: ConfigGamingFpsCallbacks
    weather: ConfigWeatherCallbacks
    audio_eq: ConfigAudioEqCallbacks
    quick_actions: ConfigQuickActionCallbacks
    automation: ConfigAutomationCallbacks
    actions: ConfigActionCallbacks


@dataclass(frozen=True)
class ConfigPanelControls:
    grid: QGridLayout
    appearance: ConfigAppearanceControls
    lcd: ConfigLcdPreferencesControls
    gaming_fps: ConfigGamingFpsControls
    weather: ConfigWeatherControls
    audio_eq: ConfigAudioEqControls
    quick_actions: ConfigQuickActionControls
    runtime_paths: ConfigRuntimePathControls
    automation: ConfigAutomationControls
    actions: ConfigActionControls


def bind_config_panel_controls(owner: Any, controls: ConfigPanelControls) -> None:
    owner.appearance_box = controls.appearance.box
    owner.cfg_ui_theme_combo = controls.appearance.theme_combo
    owner.cfg_ui_mode_combo = controls.appearance.mode_combo
    owner.cfg_ui_scale_combo = controls.appearance.scale_combo
    owner.cfg_font_scale_slider = controls.appearance.font_scale_slider
    owner.cfg_animations_chk = controls.appearance.animations_chk
    owner.cfg_compact_layout_chk = controls.appearance.compact_layout_chk
    owner.lcd_preferences_box = controls.lcd.box
    owner.cfg_lcd_note_label = controls.lcd.note_label
    owner.gaming_fps_box = controls.gaming_fps.box
    owner.cfg_fps_setup_btn = controls.gaming_fps.setup_btn
    owner.cfg_fps_refresh_btn = controls.gaming_fps.refresh_btn
    owner.cfg_fps_layer_status_label = controls.gaming_fps.status_label
    owner.cfg_fps_metrics_label = controls.gaming_fps.metrics_label
    owner.cfg_fps_log_path_edit = controls.gaming_fps.log_path_edit
    owner.cfg_fps_steam_command_edit = controls.gaming_fps.steam_command_edit
    owner.cfg_fps_copy_steam_command_btn = controls.gaming_fps.copy_steam_command_btn
    owner.cfg_fps_hint_label = controls.gaming_fps.hint_label
    owner.cfg_game_auto_theme_chk = controls.gaming_fps.auto_theme_chk
    owner.cfg_game_auto_theme_combo = controls.gaming_fps.auto_theme_combo
    owner.cfg_game_auto_theme_restore_on_fps_loss_chk = controls.gaming_fps.auto_theme_restore_on_fps_loss_chk
    owner.cfg_game_auto_theme_fps_loss_delay_spin = controls.gaming_fps.auto_theme_fps_loss_delay_spin
    owner.cfg_game_auto_theme_status_label = controls.gaming_fps.auto_theme_status_label
    owner.cfg_vrr_status_label = controls.gaming_fps.vrr_status_label
    owner.cfg_vrr_refresh_btn = controls.gaming_fps.vrr_refresh_btn
    owner.cfg_vrr_automatic_btn = controls.gaming_fps.vrr_automatic_btn
    owner.cfg_vrr_always_btn = controls.gaming_fps.vrr_always_btn
    owner.cfg_vrr_off_btn = controls.gaming_fps.vrr_off_btn
    owner.weather_box = controls.weather.box
    owner.cfg_weather_city_search_edit = controls.weather.city_search_edit
    owner.cfg_weather_search_btn = controls.weather.search_btn
    owner.cfg_weather_results_combo = controls.weather.results_combo
    owner.cfg_weather_lat_edit = controls.weather.lat_edit
    owner.cfg_weather_lon_edit = controls.weather.lon_edit
    owner.cfg_weather_location_edit = controls.weather.location_edit
    owner.cfg_weather_refresh_spin = controls.weather.refresh_spin
    owner.cfg_weather_apply_btn = controls.weather.apply_btn
    owner.cfg_weather_refresh_now_btn = controls.weather.refresh_now_btn
    owner.cfg_weather_status_label = controls.weather.status_label
    owner.audio_eq_box = controls.audio_eq.box
    owner.cfg_audio_eq_input_combo = controls.audio_eq.input_combo
    owner.cfg_audio_eq_profile_combo = controls.audio_eq.profile_combo
    owner.cfg_audio_eq_sensitivity_spin = controls.audio_eq.sensitivity_spin
    owner.cfg_audio_eq_apply_btn = controls.audio_eq.apply_btn
    owner.cfg_audio_eq_status_label = controls.audio_eq.status_label
    owner.quick_cfg_box = controls.quick_actions.box
    owner.cfg_reset_btn = controls.quick_actions.reset_btn
    owner.cfg_export_btn = controls.quick_actions.export_btn
    owner.cfg_import_btn = controls.quick_actions.import_btn
    owner.cfg_clear_cache_btn = controls.quick_actions.clear_cache_btn
    owner.cfg_restart_app_btn = controls.quick_actions.restart_app_btn
    owner.cfg_usb_recovery_btn = controls.quick_actions.usb_recovery_btn
    owner.cfg_usb_recovery_note_label = controls.quick_actions.usb_recovery_note_label
    owner.runtime_paths_box = controls.runtime_paths.box
    owner.runtime_app_path_edit = controls.runtime_paths.app_path_edit
    owner.runtime_theme_path_edit = controls.runtime_paths.theme_path_edit
    owner.runtime_state_path_edit = controls.runtime_paths.state_path_edit
    owner.runtime_fps_socket_path_edit = controls.runtime_paths.fps_socket_path_edit
    owner.automation_tools_box = controls.automation.box
    owner.playlist_list = controls.automation.playlist_list
    owner.playlist_duration_spin = controls.automation.playlist_duration_spin
    owner.playlist_add_btn = controls.automation.playlist_add_btn
    owner.playlist_remove_btn = controls.automation.playlist_remove_btn
    owner.playlist_start_btn = controls.automation.playlist_start_btn
    owner.playlist_stop_btn = controls.automation.playlist_stop_btn
    owner.bundle_path_edit = controls.automation.bundle_path_edit
    owner.bundle_merge_chk = controls.automation.bundle_merge_chk
    owner.bundle_browse_btn = controls.automation.bundle_browse_btn
    owner.bundle_save_btn = controls.automation.bundle_save_btn
    owner.bundle_load_btn = controls.automation.bundle_load_btn
    owner.cfg_cancel_btn = controls.actions.cancel_btn
    owner.cfg_apply_btn = controls.actions.apply_btn
    owner.cfg_save_btn = controls.actions.save_btn


def build_config_panel_callbacks(owner: Any) -> ConfigPanelCallbacks:
    return ConfigPanelCallbacks(
        gaming_fps=ConfigGamingFpsCallbacks(
            configure_layer=owner.configure_fps_layer_user,
            refresh_status=owner.refresh_fps_layer_status,
            copy_steam_command=owner.copy_steam_fps_launch_options,
            auto_theme_changed=owner.update_gaming_auto_theme_config,
            refresh_vrr=owner.refresh_vrr_status,
            set_vrr_policy=owner.set_vrr_policy,
        ),
        weather=ConfigWeatherCallbacks(
            search_city=owner.search_weather_city,
            apply_selected_city=owner._apply_selected_weather_city,
            apply_weather=owner.apply_weather_config,
            refresh_weather=owner.refresh_weather_now,
        ),
        audio_eq=ConfigAudioEqCallbacks(
            apply_eq=owner.apply_audio_eq_config,
            mark_dirty=lambda: setattr(owner, "_audio_eq_config_dirty", True),
        ),
        quick_actions=ConfigQuickActionCallbacks(
            reset_defaults=owner.config_preferences.reset_defaults,
            export_config=owner.config_preferences.export_file,
            import_config=owner.config_preferences.import_file,
            clear_cache=owner.config_preferences.clear_cache,
            restart_app=owner.config_preferences.restart_application,
            usb_recovery=owner.run_usb_recovery,
        ),
        automation=ConfigAutomationCallbacks(
            add_playlist_item=owner.add_playlist_item,
            remove_playlist_item=owner.remove_playlist_item,
            start_playlist=owner.start_playlist,
            stop_playlist=owner.stop_playlist,
            browse_bundle_path=owner.browse_bundle_path,
            save_bundle=owner.save_bundle,
            load_bundle=owner.load_bundle,
        ),
        actions=ConfigActionCallbacks(
            cancel=owner.config_preferences.sync_ui_controls_from_header,
            apply=owner.config_preferences.apply_preferences,
            save=lambda: (
                owner.config_preferences.apply_preferences(),
                owner._save_ui_state(),
                owner.append_log("[config] Zapisano ustawienia."),
            ),
        ),
    )


def build_config_appearance_box(theme_names: list[str]) -> ConfigAppearanceControls:
    box = QGroupBox("App Appearance")
    box.setObjectName("configCardBox")
    form = QFormLayout(box)
    theme_combo = QComboBox()
    theme_combo.addItems(theme_names)
    mode_combo = QComboBox()
    mode_combo.addItems(["Dark", "Light", "System"])
    mode_combo.setToolTip("Application theme: Dark, Light, or follow the desktop (System).")
    scale_combo = QComboBox()
    for value in (70, 80, 90, 100, 110, 125, 140):
        scale_combo.addItem(f"{value}%", value)
    font_scale_slider = QSlider(Qt.Horizontal)
    font_scale_slider.setRange(80, 140)
    font_scale_slider.setValue(100)
    animations_chk = QCheckBox("Animation effects")
    animations_chk.setChecked(True)
    compact_layout_chk = QCheckBox("Compact layout")
    form.addRow("App theme:", theme_combo)
    form.addRow("Mode:", mode_combo)
    form.addRow("Interface scale:", scale_combo)
    form.addRow("Font size:", font_scale_slider)
    form.addRow("Animation effects:", animations_chk)
    form.addRow("Compact layout:", compact_layout_chk)
    return ConfigAppearanceControls(
        box=box,
        theme_combo=theme_combo,
        mode_combo=mode_combo,
        scale_combo=scale_combo,
        font_scale_slider=font_scale_slider,
        animations_chk=animations_chk,
        compact_layout_chk=compact_layout_chk,
    )


def build_config_lcd_preferences_box() -> ConfigLcdPreferencesControls:
    box = QGroupBox("LCD Preferences")
    box.setObjectName("configCardBox")
    form = QFormLayout(box)
    note = QLabel(
        "Brightness control is disabled for now. The previous rendered brightness path resent full themes and could freeze the LCD. "
        "Hardware backlight control will be restored only after the USB command is decoded from captures."
    )
    note.setWordWrap(True)
    note.setObjectName("selectionSummaryLabel")
    note.setMinimumHeight(72)
    note.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    form.addRow(note)
    return ConfigLcdPreferencesControls(box=box, note_label=note)


def build_config_gaming_fps_box(
    *,
    steam_launch_options: str,
    callbacks: ConfigGamingFpsCallbacks,
) -> ConfigGamingFpsControls:
    box = QGroupBox("Gaming FPS")
    box.setObjectName("configCardBox")
    layout = QVBoxLayout(box)
    setup_btn = QPushButton("Configure FPS layer")
    refresh_btn = QPushButton("Refresh FPS status")
    status_label = QLabel("FPS layer: not checked")
    status_label.setWordWrap(True)
    status_label.setObjectName("selectionSummaryLabel")
    status_label.setMinimumHeight(74)
    status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    metrics_label = QLabel("No FPS session data yet")
    metrics_label.setWordWrap(True)
    metrics_label.setObjectName("selectionSummaryLabel")
    metrics_label.setMinimumHeight(92)
    metrics_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    log_path_edit = QLineEdit()
    log_path_edit.setReadOnly(True)
    log_path_edit.setPlaceholderText("FPS session CSV will appear here")
    log_path_edit.setToolTip("Each FPS session is logged as CSV under the Open Trofeo LCD state directory.")
    steam_command_edit = QLineEdit(steam_launch_options)
    steam_command_edit.setReadOnly(True)
    steam_command_edit.setToolTip("Paste this into Steam game Properties > Launch Options. Replace Game Name with the real game title.")
    copy_steam_command_btn = QPushButton("Copy Steam Launch Options")
    copy_steam_command_btn.setObjectName("quickActionButton")
    copy_steam_command_btn.setMinimumHeight(32)
    hint_label = QLabel(
        "For Steam Flatpak this installs the user Vulkan layer and grants only xdg-run/open-trofeo-lcd. "
        "Steam from DEB/native does not need the Flatpak override. In Steam game Properties > Launch Options, paste the command below and replace Game Name."
    )
    hint_label.setWordWrap(True)
    hint_label.setObjectName("selectionSummaryLabel")
    hint_label.setMinimumHeight(72)
    hint_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    auto_theme_chk = QCheckBox("Switch to selected theme when a game is detected")
    auto_theme_combo = QComboBox()
    auto_theme_combo.setEditable(False)
    auto_theme_restore_on_fps_loss_chk = QCheckBox("Experimental: restore previous theme when FPS disappears")
    auto_theme_restore_on_fps_loss_chk.setToolTip(
        "Test option for minimized games: if the game process is still visible but FPS/frametime disappears, "
        "Open Trofeo LCD restores the previous theme after the delay below. When FPS returns, the gaming theme is applied again."
    )
    auto_theme_fps_loss_delay_spin = QSpinBox()
    auto_theme_fps_loss_delay_spin.setRange(5, 120)
    auto_theme_fps_loss_delay_spin.setValue(12)
    auto_theme_fps_loss_delay_spin.setSuffix(" s")
    auto_theme_fps_loss_delay_spin.setToolTip("Delay before restoring the previous theme after FPS data disappears.")
    fps_loss_row = QHBoxLayout()
    fps_loss_row.addWidget(QLabel("FPS loss delay"))
    fps_loss_row.addWidget(auto_theme_fps_loss_delay_spin)
    fps_loss_row.addStretch(1)
    auto_theme_status_label = QLabel("Game auto-theme: disabled")
    auto_theme_status_label.setWordWrap(True)
    auto_theme_status_label.setObjectName("selectionSummaryLabel")
    auto_theme_status_label.setMinimumHeight(44)
    auto_theme_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    vrr_status_label = QLabel("VRR: not checked")
    vrr_status_label.setWordWrap(True)
    vrr_status_label.setObjectName("selectionSummaryLabel")
    vrr_status_label.setMinimumHeight(44)
    vrr_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    vrr_refresh_btn = QPushButton("Refresh VRR")
    vrr_automatic_btn = QPushButton("VRR Automatic (recommended)")
    vrr_always_btn = QPushButton("VRR Always")
    vrr_off_btn = QPushButton("VRR Off")
    vrr_automatic_btn.setToolTip("Use VRR for suitable full-screen games without forcing it on the KDE desktop.")
    vrr_always_btn.setToolTip("Force VRR continuously. This can make some KDE desktops or OLED/VA panels flicker.")
    vrr_off_btn.setToolTip("Disable VRR on all connected VRR-capable outputs.")
    vrr_row = QGridLayout()
    vrr_row.addWidget(vrr_automatic_btn, 0, 0, 1, 2)
    vrr_row.addWidget(vrr_always_btn, 1, 0)
    vrr_row.addWidget(vrr_off_btn, 1, 1)
    vrr_row.addWidget(vrr_refresh_btn, 2, 0, 1, 2)
    setup_btn.clicked.connect(callbacks.configure_layer)
    refresh_btn.clicked.connect(callbacks.refresh_status)
    copy_steam_command_btn.clicked.connect(callbacks.copy_steam_command)
    auto_theme_chk.toggled.connect(lambda _checked: callbacks.auto_theme_changed())
    auto_theme_combo.currentTextChanged.connect(lambda _text: callbacks.auto_theme_changed())
    auto_theme_restore_on_fps_loss_chk.toggled.connect(lambda _checked: callbacks.auto_theme_changed())
    auto_theme_fps_loss_delay_spin.valueChanged.connect(lambda _value: callbacks.auto_theme_changed())
    vrr_refresh_btn.clicked.connect(callbacks.refresh_vrr)
    vrr_automatic_btn.clicked.connect(lambda: callbacks.set_vrr_policy("automatic"))
    vrr_always_btn.clicked.connect(lambda: callbacks.set_vrr_policy("always"))
    vrr_off_btn.clicked.connect(lambda: callbacks.set_vrr_policy("never"))
    for button in (setup_btn, refresh_btn):
        button.setMinimumHeight(36)
        button.setObjectName("quickActionButton")
        layout.addWidget(button)
    layout.addWidget(status_label)
    layout.addWidget(metrics_label)
    layout.addWidget(log_path_edit)
    layout.addWidget(steam_command_edit)
    layout.addWidget(copy_steam_command_btn)
    layout.addWidget(auto_theme_chk)
    layout.addWidget(auto_theme_combo)
    layout.addWidget(auto_theme_restore_on_fps_loss_chk)
    layout.addLayout(fps_loss_row)
    layout.addWidget(auto_theme_status_label)
    layout.addWidget(vrr_status_label)
    layout.addLayout(vrr_row)
    layout.addWidget(hint_label)
    layout.addStretch(1)
    return ConfigGamingFpsControls(
        box=box,
        setup_btn=setup_btn,
        refresh_btn=refresh_btn,
        status_label=status_label,
        metrics_label=metrics_label,
        log_path_edit=log_path_edit,
        steam_command_edit=steam_command_edit,
        copy_steam_command_btn=copy_steam_command_btn,
        hint_label=hint_label,
        auto_theme_chk=auto_theme_chk,
        auto_theme_combo=auto_theme_combo,
        auto_theme_restore_on_fps_loss_chk=auto_theme_restore_on_fps_loss_chk,
        auto_theme_fps_loss_delay_spin=auto_theme_fps_loss_delay_spin,
        auto_theme_status_label=auto_theme_status_label,
        vrr_status_label=vrr_status_label,
        vrr_refresh_btn=vrr_refresh_btn,
        vrr_automatic_btn=vrr_automatic_btn,
        vrr_always_btn=vrr_always_btn,
        vrr_off_btn=vrr_off_btn,
    )


def build_config_audio_eq_box(callbacks: ConfigAudioEqCallbacks) -> ConfigAudioEqControls:
    box = QGroupBox("Audio EQ")
    box.setObjectName("configCardBox")
    form = QFormLayout(box)
    input_combo = QComboBox()
    input_combo.addItem("Auto: PipeWire -> Pulse -> ALSA", "auto")
    input_combo.addItem("PulseAudio / PipeWire Pulse", "pulse")
    input_combo.addItem("PipeWire native", "pipewire")
    input_combo.addItem("ALSA", "alsa")
    input_combo.activated.connect(lambda _idx: callbacks.mark_dirty())
    profile_combo = QComboBox()
    profile_combo.addItem("Responsive", "responsive")
    profile_combo.addItem("Balanced", "balanced")
    profile_combo.addItem("Smooth", "smooth")
    profile_combo.activated.connect(lambda _idx: callbacks.mark_dirty())
    sensitivity_spin = QSpinBox()
    sensitivity_spin.setRange(35, 250)
    sensitivity_spin.setSingleStep(5)
    sensitivity_spin.setSuffix("%")
    sensitivity_spin.setValue(100)
    sensitivity_spin.valueChanged.connect(lambda _value: callbacks.mark_dirty())
    apply_btn = QPushButton("Apply EQ")
    status_label = QLabel("EQ: waiting for backend status")
    status_label.setWordWrap(True)
    status_label.setObjectName("selectionSummaryLabel")
    status_label.setMinimumHeight(86)
    status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
    apply_btn.clicked.connect(callbacks.apply_eq)
    form.addRow("CAVA input:", input_combo)
    form.addRow("Response:", profile_combo)
    form.addRow("Sensitivity:", sensitivity_spin)
    form.addRow("", apply_btn)
    form.addRow(status_label)
    return ConfigAudioEqControls(
        box=box,
        input_combo=input_combo,
        profile_combo=profile_combo,
        sensitivity_spin=sensitivity_spin,
        apply_btn=apply_btn,
        status_label=status_label,
    )


def build_config_weather_box(callbacks: ConfigWeatherCallbacks) -> ConfigWeatherControls:
    box = QGroupBox("Weather")
    box.setObjectName("configCardBox")
    form = QFormLayout(box)
    city_search_edit = QLineEdit()
    city_search_edit.setPlaceholderText("Search city, e.g. Warsaw")
    search_btn = QPushButton("Search")
    results_combo = QComboBox()
    results_combo.addItem("No city selected", None)
    lat_edit = QLineEdit()
    lon_edit = QLineEdit()
    location_edit = QLineEdit()
    refresh_spin = QSpinBox()
    refresh_spin.setRange(300, 86400)
    refresh_spin.setSingleStep(300)
    refresh_spin.setValue(900)
    apply_btn = QPushButton("Apply weather")
    refresh_now_btn = QPushButton("Refresh weather")
    status_label = QLabel("Weather: not configured")
    status_label.setWordWrap(True)
    status_label.setObjectName("selectionSummaryLabel")
    status_label.setMinimumHeight(64)
    status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

    search_row = QWidget()
    search_layout = QHBoxLayout(search_row)
    search_layout.setContentsMargins(0, 0, 0, 0)
    search_layout.setSpacing(6)
    search_layout.addWidget(city_search_edit, 1)
    search_layout.addWidget(search_btn)
    search_btn.clicked.connect(callbacks.search_city)
    city_search_edit.returnPressed.connect(callbacks.search_city)
    results_combo.currentIndexChanged.connect(callbacks.apply_selected_city)
    apply_btn.clicked.connect(callbacks.apply_weather)
    refresh_now_btn.clicked.connect(callbacks.refresh_weather)

    actions_row = QWidget()
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    actions_layout.addWidget(apply_btn)
    actions_layout.addWidget(refresh_now_btn)
    form.addRow("City search:", search_row)
    form.addRow("Results:", results_combo)
    form.addRow("Latitude:", lat_edit)
    form.addRow("Longitude:", lon_edit)
    form.addRow("Location label:", location_edit)
    form.addRow("Refresh (s):", refresh_spin)
    form.addRow("", actions_row)
    form.addRow(status_label)
    return ConfigWeatherControls(
        box=box,
        city_search_edit=city_search_edit,
        search_btn=search_btn,
        results_combo=results_combo,
        lat_edit=lat_edit,
        lon_edit=lon_edit,
        location_edit=location_edit,
        refresh_spin=refresh_spin,
        apply_btn=apply_btn,
        refresh_now_btn=refresh_now_btn,
        status_label=status_label,
    )


def build_config_quick_actions_box(callbacks: ConfigQuickActionCallbacks) -> ConfigQuickActionControls:
    box = QGroupBox("Quick Actions")
    box.setObjectName("configCardBox")
    layout = QVBoxLayout(box)
    reset_btn = QPushButton("Restore Defaults")
    export_btn = QPushButton("Export Configuration")
    import_btn = QPushButton("Import Configuration")
    clear_cache_btn = QPushButton("Clear Cache")
    restart_app_btn = QPushButton("Restart Application")
    usb_recovery_btn = QPushButton("LCD USB Recovery (sudo)")
    note = QLabel(
        "For a frozen LCD after deep sleep: this runs safe USB recovery by default. "
        "If it still shows an old frame, reboot usually helps; full power-off is stronger than a warm reboot."
    )
    note.setWordWrap(True)
    note.setObjectName("selectionSummaryLabel")
    note.setMinimumHeight(118)
    note.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

    reset_btn.clicked.connect(callbacks.reset_defaults)
    export_btn.clicked.connect(callbacks.export_config)
    import_btn.clicked.connect(callbacks.import_config)
    clear_cache_btn.clicked.connect(callbacks.clear_cache)
    restart_app_btn.clicked.connect(callbacks.restart_app)
    usb_recovery_btn.clicked.connect(callbacks.usb_recovery)
    for button in (usb_recovery_btn, reset_btn, export_btn, import_btn, clear_cache_btn, restart_app_btn):
        button.setMinimumHeight(44)
        button.setObjectName("quickActionButton")
        layout.addWidget(button)
    layout.addWidget(note)
    layout.addStretch(1)
    return ConfigQuickActionControls(
        box=box,
        reset_btn=reset_btn,
        export_btn=export_btn,
        import_btn=import_btn,
        clear_cache_btn=clear_cache_btn,
        restart_app_btn=restart_app_btn,
        usb_recovery_btn=usb_recovery_btn,
        usb_recovery_note_label=note,
    )


def build_config_runtime_paths_box(
    *,
    app_path: str,
    theme_path: str,
    state_path: str,
    fps_socket_path: str,
) -> ConfigRuntimePathControls:
    box = QGroupBox("Runtime Paths")
    box.setObjectName("configCardBox")
    form = QFormLayout(box)
    app_path_edit = QLineEdit(app_path)
    theme_path_edit = QLineEdit(theme_path)
    state_path_edit = QLineEdit(state_path)
    fps_socket_path_edit = QLineEdit(fps_socket_path)
    for edit in (app_path_edit, theme_path_edit, state_path_edit, fps_socket_path_edit):
        edit.setReadOnly(True)
        edit.setObjectName("readonlyPathEdit")
    form.addRow("Application:", app_path_edit)
    form.addRow("Bundled themes:", theme_path_edit)
    form.addRow("State:", state_path_edit)
    form.addRow("FPS socket:", fps_socket_path_edit)
    return ConfigRuntimePathControls(
        box=box,
        app_path_edit=app_path_edit,
        theme_path_edit=theme_path_edit,
        state_path_edit=state_path_edit,
        fps_socket_path_edit=fps_socket_path_edit,
    )


def build_config_automation_box(callbacks: ConfigAutomationCallbacks) -> ConfigAutomationControls:
    playlist_list = QListWidget()
    bundle_path_edit = QLineEdit(".trofeo-bundle.json")
    box = QGroupBox("Automation and Bundles")
    box.setObjectName("configCardBox")
    layout = QGridLayout(box)
    playlist_duration_spin = QDoubleSpinBox()
    playlist_duration_spin.setRange(0.5, 3600.0)
    playlist_duration_spin.setSingleStep(0.5)
    playlist_duration_spin.setValue(15.0)
    playlist_add_btn = QPushButton("Add selected theme to playlist")
    playlist_remove_btn = QPushButton("Remove from playlist")
    playlist_start_btn = QPushButton("Start playlist")
    playlist_stop_btn = QPushButton("Stop playlist")
    playlist_add_btn.clicked.connect(callbacks.add_playlist_item)
    playlist_remove_btn.clicked.connect(callbacks.remove_playlist_item)
    playlist_start_btn.clicked.connect(callbacks.start_playlist)
    playlist_stop_btn.clicked.connect(callbacks.stop_playlist)
    bundle_merge_chk = QCheckBox("Merge on import")
    bundle_browse_btn = QPushButton("Choose bundle")
    bundle_save_btn = QPushButton("Save bundle")
    bundle_load_btn = QPushButton("Load bundle")
    bundle_browse_btn.clicked.connect(callbacks.browse_bundle_path)
    bundle_save_btn.clicked.connect(callbacks.save_bundle)
    bundle_load_btn.clicked.connect(callbacks.load_bundle)
    layout.addWidget(QLabel("Playlist"), 0, 0)
    layout.addWidget(playlist_list, 1, 0, 4, 2)
    layout.addWidget(QLabel("Item duration (s)"), 0, 2)
    layout.addWidget(playlist_duration_spin, 0, 3)
    layout.addWidget(playlist_add_btn, 1, 2, 1, 2)
    layout.addWidget(playlist_remove_btn, 2, 2, 1, 2)
    layout.addWidget(playlist_start_btn, 3, 2, 1, 2)
    layout.addWidget(playlist_stop_btn, 4, 2, 1, 2)
    layout.addWidget(QLabel("Bundle"), 5, 0)
    layout.addWidget(bundle_path_edit, 5, 1, 1, 2)
    layout.addWidget(bundle_browse_btn, 5, 3)
    layout.addWidget(bundle_merge_chk, 6, 1)
    layout.addWidget(bundle_save_btn, 6, 2)
    layout.addWidget(bundle_load_btn, 6, 3)
    return ConfigAutomationControls(
        box=box,
        playlist_list=playlist_list,
        playlist_duration_spin=playlist_duration_spin,
        playlist_add_btn=playlist_add_btn,
        playlist_remove_btn=playlist_remove_btn,
        playlist_start_btn=playlist_start_btn,
        playlist_stop_btn=playlist_stop_btn,
        bundle_path_edit=bundle_path_edit,
        bundle_merge_chk=bundle_merge_chk,
        bundle_browse_btn=bundle_browse_btn,
        bundle_save_btn=bundle_save_btn,
        bundle_load_btn=bundle_load_btn,
    )


def build_config_action_row(callbacks: ConfigActionCallbacks) -> ConfigActionControls:
    row = QHBoxLayout()
    row.addStretch(1)
    cancel_btn = QPushButton("Cancel")
    apply_btn = QPushButton("Apply")
    save_btn = QPushButton("Save Settings")
    apply_btn.setObjectName("secondaryAccentButton")
    save_btn.setObjectName("primaryButton")
    cancel_btn.clicked.connect(callbacks.cancel)
    apply_btn.clicked.connect(callbacks.apply)
    save_btn.clicked.connect(callbacks.save)
    row.addWidget(cancel_btn)
    row.addWidget(apply_btn)
    row.addWidget(save_btn)
    return ConfigActionControls(row=row, cancel_btn=cancel_btn, apply_btn=apply_btn, save_btn=save_btn)


def build_config_panel_controls(
    *,
    theme_names: list[str],
    steam_launch_options: str,
    app_path: str,
    theme_path: str,
    state_path: str,
    fps_socket_path: str,
    callbacks: ConfigPanelCallbacks,
) -> ConfigPanelControls:
    grid = QGridLayout()
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(14)

    appearance = build_config_appearance_box(theme_names)
    lcd = build_config_lcd_preferences_box()
    gaming_fps = build_config_gaming_fps_box(
        steam_launch_options=steam_launch_options,
        callbacks=callbacks.gaming_fps,
    )
    weather = build_config_weather_box(callbacks.weather)
    audio_eq = build_config_audio_eq_box(callbacks.audio_eq)
    quick_actions = build_config_quick_actions_box(callbacks.quick_actions)
    runtime_paths = build_config_runtime_paths_box(
        app_path=app_path,
        theme_path=theme_path,
        state_path=state_path,
        fps_socket_path=fps_socket_path,
    )
    automation = build_config_automation_box(callbacks.automation)
    actions = build_config_action_row(callbacks.actions)

    grid.addWidget(appearance.box, 0, 0)
    grid.addWidget(lcd.box, 0, 1)
    grid.addWidget(gaming_fps.box, 0, 2)
    grid.addWidget(weather.box, 1, 0, 1, 2)
    grid.addWidget(audio_eq.box, 1, 2)
    grid.addWidget(quick_actions.box, 0, 3, 2, 1)
    grid.addWidget(runtime_paths.box, 2, 0, 1, 4)

    return ConfigPanelControls(
        grid=grid,
        appearance=appearance,
        lcd=lcd,
        gaming_fps=gaming_fps,
        weather=weather,
        audio_eq=audio_eq,
        quick_actions=quick_actions,
        runtime_paths=runtime_paths,
        automation=automation,
        actions=actions,
    )


class ConfigurationPanel(QWidget):
    def __init__(
        self,
        *,
        theme_names: list[str],
        steam_launch_options: str,
        app_path: str,
        theme_path: str,
        state_path: str,
        fps_socket_path: str,
        callbacks: ConfigPanelCallbacks,
        intro_card_factory: Callable[[str], QWidget] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("configurationPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.intro_card = intro_card_factory("runtimeHeroCard") if intro_card_factory else QFrame()
        self.intro_card.setObjectName("runtimeHeroCard")
        intro_layout = QHBoxLayout(self.intro_card)
        intro_layout.setContentsMargins(18, 16, 18, 16)
        self.intro_label = QLabel(CONFIG_INTRO_TEXT)
        self.intro_label.setObjectName("studioHeroText")
        self.intro_label.setWordWrap(True)
        intro_layout.addWidget(self.intro_label)
        layout.addWidget(self.intro_card)

        self.controls = build_config_panel_controls(
            theme_names=theme_names,
            steam_launch_options=steam_launch_options,
            app_path=app_path,
            theme_path=theme_path,
            state_path=state_path,
            fps_socket_path=fps_socket_path,
            callbacks=callbacks,
        )
        layout.addLayout(self.controls.grid)
        layout.addWidget(self.controls.automation.box)
        layout.addLayout(self.controls.actions.row)
        layout.addStretch(1)
