"""Theme Gallery panel controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from theme_gallery import ResolvePathFn, filtered_theme_card_entries, read_theme_document_for_card, theme_card_grid_metrics
from theme_gallery_widgets import (
    AssetGalleryCardCallbacks,
    CardFactory,
    LibraryThemeCardCallbacks,
    PixmapFactory,
    build_asset_gallery_card,
    build_library_theme_card,
)

TranslateFn = Callable[[str, str], str]
ASSET_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass(frozen=True)
class ThemeGalleryActionCallbacks:
    refresh_themes: Callable[[], None]
    import_ttcr: Callable[[], None]
    browse_new_theme_path: Callable[[], None]
    create_new_theme: Callable[[], None]
    suggest_new_theme_path: Callable[..., None]
    mark_new_theme_path_customized: Callable[[str], None]
    toggle_new_theme_advanced: Callable[[bool], None]


@dataclass(frozen=True)
class ThemeGalleryActionBar:
    root: QFrame
    summary_label: QLabel
    name_edit: QLineEdit
    template_combo: QComboBox
    create_btn: QPushButton
    advanced_btn: QPushButton
    refresh_btn: QPushButton
    import_ttcr_btn: QPushButton
    path_edit: QLineEdit
    browse_btn: QPushButton
    path_row: QWidget
    hint_label: QLabel


@dataclass(frozen=True)
class ThemeGalleryPanelControls:
    action_bar: ThemeGalleryActionBar
    browser_box: QGroupBox
    browser_scroll: QScrollArea
    filter_edit: QLineEdit
    type_combo: QComboBox
    sort_combo: QComboBox
    controls_search_label: QLabel
    controls_type_label: QLabel
    controls_sort_label: QLabel
    current_theme_label: QLabel
    cards_container: QWidget
    cards_layout: QGridLayout
    browser_panel: "ThemeGalleryBrowserPanel"
    asset_gallery_box: QGroupBox
    asset_gallery_container: QWidget
    asset_gallery_layout: QGridLayout
    asset_gallery_panel: "ThemeAssetGalleryPanel"


def build_theme_gallery_action_bar(
    *,
    template_catalog: list[dict[str, str]],
    callbacks: ThemeGalleryActionCallbacks,
    default_path: str,
) -> ThemeGalleryActionBar:
    root = QFrame()
    root.setObjectName("libraryActionBar")
    root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(14, 12, 14, 12)
    root_layout.setSpacing(6)

    summary_label = QLabel("Theme gallery quick actions")
    summary_label.setObjectName("selectionSummaryLabel")
    summary_label.setWordWrap(False)
    root_layout.addWidget(summary_label)

    name_edit = QLineEdit("New Theme")
    name_edit.setObjectName("newThemeNameEdit")
    name_edit.setPlaceholderText("e.g. My Dashboard")
    template_combo = QComboBox()
    template_combo.setObjectName("newThemeTemplateCombo")
    for template in template_catalog:
        template_combo.addItem(template["title"], template["path"])
    create_btn = QPushButton("Create Theme")
    create_btn.setObjectName("newThemeCreateButton")
    advanced_btn = QPushButton("File Settings")
    advanced_btn.setCheckable(True)
    refresh_btn = QPushButton("Refresh")
    import_ttcr_btn = QPushButton("Import TTCR")
    refresh_btn.clicked.connect(callbacks.refresh_themes)
    import_ttcr_btn.clicked.connect(callbacks.import_ttcr)

    path_edit = QLineEdit(default_path)
    path_edit.setObjectName("newThemePathEdit")
    browse_btn = QPushButton("Choose File")

    action_row = QHBoxLayout()
    action_row.setSpacing(8)
    action_row.addWidget(import_ttcr_btn)
    action_row.addWidget(refresh_btn)
    action_row.addWidget(QLabel("Name"))
    action_row.addWidget(name_edit, 2)
    action_row.addWidget(QLabel("Style"))
    action_row.addWidget(template_combo, 1)
    action_row.addWidget(create_btn)
    action_row.addWidget(advanced_btn)
    root_layout.addLayout(action_row)

    path_row = QWidget()
    path_row_layout = QHBoxLayout(path_row)
    path_row_layout.setContentsMargins(0, 0, 0, 0)
    path_row_layout.setSpacing(8)
    path_row_layout.addWidget(QLabel("File"))
    path_row_layout.addWidget(path_edit, 1)
    path_row_layout.addWidget(browse_btn)
    root_layout.addWidget(path_row)
    path_row.hide()

    hint_label = QLabel("Enter a name and style. The theme file path will be suggested automatically.")
    hint_label.setObjectName("selectionSummaryLabel")
    hint_label.setWordWrap(False)
    root_layout.addWidget(hint_label)

    browse_btn.clicked.connect(callbacks.browse_new_theme_path)
    create_btn.clicked.connect(callbacks.create_new_theme)
    template_combo.currentIndexChanged.connect(callbacks.suggest_new_theme_path)
    name_edit.textChanged.connect(callbacks.suggest_new_theme_path)
    path_edit.textEdited.connect(callbacks.mark_new_theme_path_customized)
    advanced_btn.toggled.connect(callbacks.toggle_new_theme_advanced)

    return ThemeGalleryActionBar(
        root=root,
        summary_label=summary_label,
        name_edit=name_edit,
        template_combo=template_combo,
        create_btn=create_btn,
        advanced_btn=advanced_btn,
        refresh_btn=refresh_btn,
        import_ttcr_btn=import_ttcr_btn,
        path_edit=path_edit,
        browse_btn=browse_btn,
        path_row=path_row,
        hint_label=hint_label,
    )


def bind_theme_gallery_panel_controls(owner, controls: ThemeGalleryPanelControls) -> None:
    owner.new_theme_options_box = controls.action_bar.root
    owner.library_summary_label = controls.action_bar.summary_label
    owner.new_theme_name_edit = controls.action_bar.name_edit
    owner.new_theme_template_combo = controls.action_bar.template_combo
    owner.new_theme_create_btn = controls.action_bar.create_btn
    owner.new_theme_advanced_btn = controls.action_bar.advanced_btn
    owner.library_refresh_btn = controls.action_bar.refresh_btn
    owner.library_import_ttcr_btn = controls.action_bar.import_ttcr_btn
    owner.new_theme_path_edit = controls.action_bar.path_edit
    owner.new_theme_browse_btn = controls.action_bar.browse_btn
    owner.new_theme_path_row = controls.action_bar.path_row
    owner.new_theme_hint_label = controls.action_bar.hint_label
    owner.theme_browser_box = controls.browser_box
    owner.theme_browser_scroll = controls.browser_scroll
    owner.library_theme_filter_edit = controls.filter_edit
    owner.library_theme_type_combo = controls.type_combo
    owner.library_theme_sort_combo = controls.sort_combo
    owner.theme_browser_controls_search_label = controls.controls_search_label
    owner.theme_browser_controls_type_label = controls.controls_type_label
    owner.theme_browser_controls_sort_label = controls.controls_sort_label
    owner.library_current_theme_label = controls.current_theme_label
    owner.library_theme_cards_container = controls.cards_container
    owner.library_theme_cards_layout = controls.cards_layout
    owner.theme_gallery_browser = controls.browser_panel
    owner.asset_gallery_box = controls.asset_gallery_box
    owner.asset_gallery_container = controls.asset_gallery_container
    owner.asset_gallery_layout = controls.asset_gallery_layout
    owner.theme_asset_gallery_panel = controls.asset_gallery_panel


def build_theme_gallery_panel(
    *,
    library_layout: QVBoxLayout,
    template_catalog: list[dict[str, str]],
    default_path: str,
    action_callbacks: ThemeGalleryActionCallbacks,
    browser_callbacks: LibraryThemeCardCallbacks,
    asset_callbacks: AssetGalleryCardCallbacks,
    translate: TranslateFn,
    resolve_path: ResolvePathFn,
    pixmap_for_item: PixmapFactory,
    card_factory: CardFactory,
    event_filter: Any | None = None,
) -> ThemeGalleryPanelControls:
    action_bar = build_theme_gallery_action_bar(
        template_catalog=template_catalog,
        callbacks=action_callbacks,
        default_path=default_path,
    )
    library_layout.addWidget(action_bar.root)

    browser_box = QGroupBox("Themes")
    browser_box.setObjectName("librarySectionBox")
    browser_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
    browser_layout = QVBoxLayout(browser_box)
    browser_controls = QHBoxLayout()
    browser_controls.setSpacing(6)
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText("Search by theme name...")
    type_combo = QComboBox()
    type_combo.addItems(["All", "Theme", "Image", "Local", "TTCR", "Animated"])
    sort_combo = QComboBox()
    sort_combo.addItems(["Name A-Z", "Name Z-A", "Newest", "Oldest"])
    controls_search_label = QLabel("Search")
    controls_type_label = QLabel("Type")
    controls_sort_label = QLabel("Sort")
    browser_controls.addWidget(controls_search_label)
    browser_controls.addWidget(filter_edit, 1)
    browser_controls.addWidget(controls_type_label)
    browser_controls.addWidget(type_combo)
    browser_controls.addWidget(controls_sort_label)
    browser_controls.addWidget(sort_combo)
    browser_layout.addLayout(browser_controls)

    current_theme_label = QLabel("No active theme.")
    current_theme_label.setObjectName("selectionSummaryLabel")
    current_theme_label.setWordWrap(True)
    browser_layout.addWidget(current_theme_label)

    browser_scroll = QScrollArea()
    browser_scroll.setWidgetResizable(True)
    browser_scroll.setFrameShape(QScrollArea.NoFrame)
    browser_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    browser_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    browser_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
    if event_filter is not None:
        browser_scroll.viewport().installEventFilter(event_filter)
    cards_container = QWidget()
    cards_layout = QGridLayout(cards_container)
    cards_layout.setContentsMargins(0, 0, 0, 0)
    cards_layout.setHorizontalSpacing(12)
    cards_layout.setVerticalSpacing(12)
    cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    browser_scroll.setWidget(cards_container)
    browser_layout.addWidget(browser_scroll)
    library_layout.addWidget(browser_box, 0)

    browser_panel = ThemeGalleryBrowserPanel(
        cards_layout=cards_layout,
        cards_container=cards_container,
        browser_scroll=browser_scroll,
        browser_box=browser_box,
        filter_edit=filter_edit,
        type_combo=type_combo,
        sort_combo=sort_combo,
        current_theme_label=current_theme_label,
        translate=translate,
        resolve_path=resolve_path,
        pixmap_for_item=pixmap_for_item,
        card_factory=card_factory,
        callbacks=browser_callbacks,
    )

    asset_gallery_box = QGroupBox("Theme Assets")
    asset_gallery_box.setObjectName("librarySectionBox")
    asset_gallery_layout_root = QVBoxLayout(asset_gallery_box)
    asset_gallery_scroll = QScrollArea()
    asset_gallery_scroll.setWidgetResizable(True)
    asset_gallery_scroll.setFrameShape(QScrollArea.NoFrame)
    asset_gallery_container = QWidget()
    asset_gallery_layout = QGridLayout(asset_gallery_container)
    asset_gallery_layout.setContentsMargins(0, 0, 0, 0)
    asset_gallery_layout.setHorizontalSpacing(10)
    asset_gallery_layout.setVerticalSpacing(10)
    asset_gallery_scroll.setWidget(asset_gallery_container)
    asset_gallery_layout_root.addWidget(asset_gallery_scroll)
    asset_gallery_panel = ThemeAssetGalleryPanel(
        asset_layout=asset_gallery_layout,
        asset_container=asset_gallery_container,
        card_factory=card_factory,
        callbacks=asset_callbacks,
    )
    asset_gallery_box.hide()
    library_layout.addStretch(1)

    return ThemeGalleryPanelControls(
        action_bar=action_bar,
        browser_box=browser_box,
        browser_scroll=browser_scroll,
        filter_edit=filter_edit,
        type_combo=type_combo,
        sort_combo=sort_combo,
        controls_search_label=controls_search_label,
        controls_type_label=controls_type_label,
        controls_sort_label=controls_sort_label,
        current_theme_label=current_theme_label,
        cards_container=cards_container,
        cards_layout=cards_layout,
        browser_panel=browser_panel,
        asset_gallery_box=asset_gallery_box,
        asset_gallery_container=asset_gallery_container,
        asset_gallery_layout=asset_gallery_layout,
        asset_gallery_panel=asset_gallery_panel,
    )


class ThemeGalleryBrowserPanel:
    def __init__(
        self,
        *,
        cards_layout: QGridLayout,
        cards_container: QWidget,
        browser_scroll: QScrollArea,
        browser_box: QGroupBox,
        filter_edit: QLineEdit,
        type_combo: QComboBox,
        sort_combo: QComboBox,
        current_theme_label: QLabel,
        translate: TranslateFn,
        resolve_path: ResolvePathFn,
        pixmap_for_item: PixmapFactory,
        card_factory: CardFactory,
        callbacks: LibraryThemeCardCallbacks,
    ) -> None:
        self.cards_layout = cards_layout
        self.cards_container = cards_container
        self.browser_scroll = browser_scroll
        self.browser_box = browser_box
        self.filter_edit = filter_edit
        self.type_combo = type_combo
        self.sort_combo = sort_combo
        self.current_theme_label = current_theme_label
        self.translate = translate
        self.resolve_path = resolve_path
        self.pixmap_for_item = pixmap_for_item
        self.card_factory = card_factory
        self.callbacks = callbacks

    def browser_width(self) -> int:
        viewport_width = 0
        try:
            viewport_width = self.browser_scroll.viewport().width()
        except Exception:
            viewport_width = 0
        if viewport_width <= 0:
            viewport_width = self.cards_container.width()
        return max(260, int(viewport_width or 960))

    def rebuild(
        self,
        *,
        theme_items: dict[str, dict[str, Any]],
        current_name: str,
        startup_theme_name: str,
    ) -> None:
        self._clear_cards()
        entries = filtered_theme_card_entries(
            theme_items,
            needle=self.filter_edit.text().strip().lower(),
            type_filter=self.type_combo.currentText().strip(),
            sort_mode=self.sort_combo.currentText().strip(),
            resolve_path=self.resolve_path,
            document_loader=lambda item: read_theme_document_for_card(item, self.resolve_path),
        )
        self.current_theme_label.setText(
            self.translate(f"Currently selected: {current_name}", f"Aktualnie wybrany: {current_name}")
            if current_name
            else self.translate("No active theme.", "Brak aktywnego motywu.")
        )
        if not entries:
            self._show_empty_state()
            return

        viewport_width = self.browser_width()
        spacing = self.cards_layout.horizontalSpacing()
        grid_metrics = theme_card_grid_metrics(
            viewport_width=viewport_width,
            spacing=spacing,
            entry_names=[entry.name for entry in entries],
            current_name=current_name,
        )
        self.cards_container.setMinimumWidth(0)
        self.cards_container.setMaximumWidth(viewport_width)

        for idx, entry in enumerate(entries):
            card = build_library_theme_card(
                entry,
                card_width=grid_metrics.card_width,
                card_height_base=grid_metrics.card_height_base,
                compact_cards=grid_metrics.compact_cards,
                current_name=current_name,
                startup_theme_name=startup_theme_name,
                translate=self.translate,
                resolve_path=self.resolve_path,
                pixmap_for_item=self.pixmap_for_item,
                card_factory=self.card_factory,
                callbacks=self.callbacks,
            )
            row = idx // grid_metrics.columns
            col = idx % grid_metrics.columns
            self.cards_layout.addWidget(card, row, col)

        for col in range(4):
            self.cards_layout.setColumnStretch(col, 0)
        for col in range(grid_metrics.columns):
            self.cards_layout.setColumnStretch(col, 1)
        self.browser_scroll.setMinimumHeight(grid_metrics.viewport_height)
        self.browser_scroll.setMaximumHeight(grid_metrics.scroll_max_height)
        self.browser_box.setMinimumHeight(grid_metrics.box_height)
        self.browser_box.setMaximumHeight(grid_metrics.box_max_height)

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_empty_state(self) -> None:
        empty = QLabel(self.translate("No themes match the current filter.", "Brak motywów pasujących do filtra."))
        empty.setObjectName("selectionSummaryLabel")
        empty.setWordWrap(True)
        self.cards_layout.addWidget(empty, 0, 0)
        self.browser_scroll.setMinimumHeight(96)
        self.browser_scroll.setMaximumHeight(96)
        self.browser_box.setMinimumHeight(212)
        self.browser_box.setMaximumHeight(212)
        self.cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)


class ThemeAssetGalleryPanel:
    def __init__(
        self,
        *,
        asset_layout: QGridLayout,
        asset_container: QWidget,
        card_factory: CardFactory,
        callbacks: AssetGalleryCardCallbacks,
    ) -> None:
        self.asset_layout = asset_layout
        self.asset_container = asset_container
        self.card_factory = card_factory
        self.callbacks = callbacks

    def rebuild(self, asset_root: Path) -> None:
        self._clear_cards()
        if not asset_root.exists():
            self._show_empty("Brak assetów dla bieżącego motywu. Zaimportuj tło albo obraz do motywu, aby zbudować bibliotekę.")
            return
        files = sorted(
            [path for path in asset_root.rglob("*") if path.suffix.lower() in ASSET_IMAGE_SUFFIXES],
            key=lambda path: str(path),
        )
        if not files:
            self._show_empty("Brak obrazów w katalogu assetów tego motywu.")
            return

        container_width = max(720, self.asset_container.width() or 960)
        columns = max(1, min(4, container_width // 320))
        for idx, path in enumerate(files[:40]):
            card = build_asset_gallery_card(
                path,
                asset_root=asset_root,
                card_factory=self.card_factory,
                callbacks=self.callbacks,
            )
            self.asset_layout.addWidget(card, idx // columns, idx % columns)
        for col in range(columns):
            self.asset_layout.setColumnStretch(col, 1)

    def _clear_cards(self) -> None:
        while self.asset_layout.count():
            child = self.asset_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_empty(self, text: str) -> None:
        empty = QLabel(text)
        empty.setObjectName("selectionSummaryLabel")
        empty.setWordWrap(True)
        self.asset_layout.addWidget(empty, 0, 0)


class ThemeGalleryRefreshCoordinator:
    """Debounce and visibility-gate expensive gallery card rebuilds."""

    def __init__(
        self,
        *,
        is_visible: Callable[[], bool],
        browser_width: Callable[[], int],
        rebuild: Callable[[], None],
    ) -> None:
        self._is_visible = is_visible
        self._browser_width = browser_width
        self._rebuild = rebuild
        self.dirty = True
        self._last_width = 0
        self._pending = False

    def mark_dirty(self) -> None:
        self.dirty = True

    def rebuild_now(self) -> None:
        self.dirty = False
        self._rebuild()

    def maybe_rebuild_visible(self) -> None:
        if self.dirty and self._is_visible():
            self.rebuild_now()

    def schedule_for_resize(self) -> None:
        if not self._is_visible():
            self.dirty = True
            return
        width = int(self._browser_width())
        if width == self._last_width:
            return
        self._last_width = width
        if self._pending:
            return
        self._pending = True

        def _run() -> None:
            self._pending = False
            self.rebuild_now()

        QTimer.singleShot(0, _run)
