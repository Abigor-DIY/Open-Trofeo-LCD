"""Qt widgets for the Theme Gallery panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from theme_gallery import ResolvePathFn, ThemeCardEntry, TranslateFn, theme_modified_label, theme_type_badge

CardFactory = Callable[[str], QWidget]
PixmapFactory = Callable[[dict[str, Any], QSize], QPixmap]


@dataclass(frozen=True)
class LibraryThemeCardCallbacks:
    show_menu: Callable[[str, dict[str, Any], QWidget], None]
    select_theme: Callable[[str, dict[str, Any]], None]
    preview_theme: Callable[[str, dict[str, Any]], None]
    apply_theme: Callable[[str], None]
    duplicate_theme: Callable[[str, dict[str, Any]], None]
    remove_theme: Callable[[str], None]
    set_startup_theme: Callable[[str, bool], None]


@dataclass(frozen=True)
class RuntimeThemeCardCallbacks:
    select_theme: Callable[[str], None]
    apply_theme: Callable[[str], None]
    remove_theme: Callable[[str], None]


@dataclass(frozen=True)
class AssetGalleryCardCallbacks:
    use_as_background: Callable[[Path], None]
    use_as_image: Callable[[Path], None]


def build_asset_gallery_card(
    path: Path,
    *,
    asset_root: Path,
    card_factory: CardFactory,
    callbacks: AssetGalleryCardCallbacks,
) -> QWidget:
    card = card_factory("assetCard")
    card.setObjectName("assetCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    thumb = QLabel()
    thumb.setObjectName("templateCardThumb")
    thumb.setMinimumSize(240, 92)
    thumb.setMaximumHeight(92)
    thumb.setAlignment(Qt.AlignCenter)
    pixmap = QPixmap(str(path))
    if not pixmap.isNull():
        thumb.setPixmap(pixmap.scaled(thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    layout.addWidget(thumb)

    title = QLabel(path.name)
    title.setObjectName("libraryCardTitle")
    title.setWordWrap(True)
    meta = QLabel(str(path.relative_to(asset_root)))
    meta.setObjectName("libraryCardMeta")
    meta.setWordWrap(True)
    desc = QLabel("Zasób gotowy do użycia jako tło albo warstwa obrazu.")
    desc.setObjectName("libraryCardDesc")
    desc.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(meta)
    layout.addWidget(desc)
    layout.addStretch(1)

    actions = QHBoxLayout()
    actions.setSpacing(8)
    bg_btn = QPushButton("Ustaw jako tło")
    img_btn = QPushButton("Dodaj jako obraz")
    bg_btn.setObjectName("secondaryAccentButton")
    bg_btn.clicked.connect(lambda _checked=False: callbacks.use_as_background(path))
    img_btn.clicked.connect(lambda _checked=False: callbacks.use_as_image(path))
    actions.addWidget(bg_btn)
    actions.addWidget(img_btn)
    layout.addLayout(actions)
    return card


def build_runtime_theme_card(
    name: str,
    item: dict[str, Any],
    *,
    current_name: str,
    pixmap_for_item: PixmapFactory,
    card_factory: CardFactory,
    callbacks: RuntimeThemeCardCallbacks,
) -> QWidget:
    card = card_factory("templateCard")
    layout = QHBoxLayout(card)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(14)

    thumb = QLabel()
    thumb.setObjectName("templateCardThumb")
    thumb.setFixedSize(180, 72)
    thumb.setPixmap(pixmap_for_item(item, thumb.size()))
    layout.addWidget(thumb)

    text_col = QVBoxLayout()
    title = QLabel(name)
    title.setObjectName("templateCardTitle")
    meta = QLabel(f"{item.get('type', 'image')} | {Path(str(item.get('path', ''))).name}")
    meta.setObjectName("templateCardMeta")
    meta.setWordWrap(True)
    text_col.addWidget(title)
    text_col.addWidget(meta)
    text_col.addStretch(1)
    layout.addLayout(text_col, 1)

    actions = QVBoxLayout()
    select_btn = QPushButton("Wybierz")
    apply_btn = QPushButton("Zastosuj")
    remove_btn = QPushButton("Usuń")
    if name == current_name:
        apply_btn.setObjectName("primaryButton")
    for btn in (select_btn, apply_btn, remove_btn):
        btn.setMinimumHeight(36)
    select_btn.clicked.connect(lambda _checked=False: callbacks.select_theme(name))
    apply_btn.clicked.connect(lambda _checked=False: callbacks.apply_theme(name))
    remove_btn.clicked.connect(lambda _checked=False: callbacks.remove_theme(name))
    actions.addWidget(select_btn)
    actions.addWidget(apply_btn)
    actions.addWidget(remove_btn)
    actions.addStretch(1)
    layout.addLayout(actions)
    return card


def build_library_theme_card(
    entry: ThemeCardEntry,
    *,
    card_width: int,
    card_height_base: int,
    compact_cards: bool,
    current_name: str,
    startup_theme_name: str,
    translate: TranslateFn,
    resolve_path: ResolvePathFn,
    pixmap_for_item: PixmapFactory,
    card_factory: CardFactory,
    callbacks: LibraryThemeCardCallbacks,
) -> QWidget:
    name = entry.name
    item = entry.item
    is_current = name == current_name
    card_height = card_height_base + (24 if compact_cards and is_current else 0)
    card = card_factory("libraryCard")
    card.setObjectName("libraryCard")
    card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    card.setFixedWidth(card_width)
    card.setMinimumHeight(card_height)
    card.setMaximumHeight(card_height)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(6)

    thumb = QLabel()
    thumb.setObjectName("templateCardThumb")
    thumb.setMinimumSize(0, 92)
    thumb.setMaximumHeight(92)
    thumb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    thumb.setAlignment(Qt.AlignCenter)
    thumb_size = QSize(max(1, card_width - 20), 92)
    thumb.setPixmap(pixmap_for_item(item, thumb_size).scaled(thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    layout.addWidget(thumb)

    top_meta_row = QHBoxLayout()
    top_meta_row.setSpacing(8)
    badge = QLabel(theme_type_badge(item, translate))
    badge.setObjectName("layerBadgeLabel")
    category_badge = QLabel(entry.category)
    category_badge.setObjectName("layerBadgeLabel")
    modified = QLabel(theme_modified_label(item, resolve_path))
    modified.setObjectName("libraryCardMeta")
    modified.setMinimumWidth(0)
    menu_btn = QPushButton("...")
    menu_btn.setMinimumSize(34, 28)
    menu_btn.clicked.connect(lambda _checked=False, btn=menu_btn: callbacks.show_menu(name, item, btn))
    top_meta_row.addWidget(badge, 0)
    top_meta_row.addWidget(category_badge, 0)
    top_meta_row.addWidget(modified, 1)
    top_meta_row.addWidget(menu_btn, 0)
    layout.addLayout(top_meta_row)

    title = QLabel(name)
    title.setObjectName("libraryCardTitle")
    title.setWordWrap(True)
    meta = QLabel(Path(str(item.get("path", ""))).name)
    meta.setObjectName("libraryCardMeta")
    meta.setWordWrap(True)
    desc_parts = []
    if entry.asset_count:
        desc_parts.append(f"Assety: {entry.asset_count}")
    if entry.animation_count:
        desc_parts.append(f"Klatki: {entry.animation_count}")
    desc_text = " • ".join(desc_parts) if desc_parts else (
        "Gotowy do edycji." if str(item.get("type", "")) == "theme-doc" else "Gotowy do użycia."
    )
    desc = QLabel(desc_text)
    desc.setObjectName("libraryCardDesc")
    desc.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(meta)
    layout.addWidget(desc)

    if is_current:
        active_label = QLabel(translate("Currently selected", "Aktualnie wybrany"))
        active_label.setObjectName("layerBadgeLabel")
        layout.addWidget(active_label)

    startup_row = QHBoxLayout()
    startup_chk = QCheckBox(translate("Apply on startup", "Zastosuj przy uruchomieniu"))
    startup_chk.setChecked(name == startup_theme_name)
    startup_chk.toggled.connect(lambda checked: callbacks.set_startup_theme(name, checked))
    startup_row.addWidget(startup_chk)
    startup_row.addStretch(1)
    layout.addLayout(startup_row)

    select_btn = QPushButton(translate("Edit", "Edytuj") if str(item.get("type", "")) == "theme-doc" else translate("Select", "Wybierz"))
    preview_btn = QPushButton(translate("Preview", "Podgląd"))
    apply_btn = QPushButton(translate("Apply", "Zastosuj"))
    duplicate_btn = QPushButton(translate("Duplicate", "Duplikuj"))
    remove_btn = QPushButton(translate("Remove", "Usuń"))
    apply_btn.setObjectName("primaryButton" if is_current else "secondaryAccentButton")
    for btn in (select_btn, preview_btn, apply_btn, duplicate_btn, remove_btn):
        btn.setMinimumHeight(28)
        btn.setMinimumWidth(0)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    select_btn.clicked.connect(lambda _checked=False: callbacks.select_theme(name, item))
    preview_btn.clicked.connect(lambda _checked=False: callbacks.preview_theme(name, item))
    apply_btn.clicked.connect(lambda _checked=False: callbacks.apply_theme(name))
    duplicate_btn.clicked.connect(lambda _checked=False: callbacks.duplicate_theme(name, item))
    remove_btn.clicked.connect(lambda _checked=False: callbacks.remove_theme(name))

    if compact_cards:
        compact_actions = QGridLayout()
        compact_actions.setHorizontalSpacing(6)
        compact_actions.setVerticalSpacing(6)
        compact_actions.addWidget(select_btn, 0, 0)
        compact_actions.addWidget(preview_btn, 0, 1)
        compact_actions.addWidget(apply_btn, 0, 2)
        compact_actions.addWidget(duplicate_btn, 1, 0, 1, 2)
        compact_actions.addWidget(remove_btn, 1, 2)
        for action_col in range(3):
            compact_actions.setColumnStretch(action_col, 1)
        layout.addLayout(compact_actions)
    else:
        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(select_btn, 2)
        actions.addWidget(preview_btn, 1)
        actions.addWidget(apply_btn, 2)
        actions.addWidget(duplicate_btn, 1)
        actions.addWidget(remove_btn, 1)
        layout.addLayout(actions)

    return card
