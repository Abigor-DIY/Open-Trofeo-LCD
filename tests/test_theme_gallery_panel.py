import os
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from theme_gallery_panel import (
    ThemeAssetGalleryPanel,
    ThemeGalleryActionCallbacks,
    ThemeGalleryBrowserPanel,
    ThemeGalleryRefreshCoordinator,
    bind_theme_gallery_panel_controls,
    build_theme_gallery_panel,
    build_theme_gallery_action_bar,
)
from theme_gallery_widgets import AssetGalleryCardCallbacks, LibraryThemeCardCallbacks


class ThemeGalleryPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_panel(self, *, search: str = "", type_filter: str = "All") -> ThemeGalleryBrowserPanel:
        container = QWidget()
        layout = QGridLayout(container)
        layout.setHorizontalSpacing(12)
        browser_scroll = QScrollArea()
        browser_scroll.setWidget(container)
        type_combo = QComboBox()
        type_combo.addItems(["All", "Theme", "Image", "Local", "TTCR", "Animated"])
        type_combo.setCurrentText(type_filter)
        sort_combo = QComboBox()
        sort_combo.addItems(["Name A-Z", "Name Z-A", "Newest", "Oldest"])
        filter_edit = QLineEdit(search)
        callbacks = LibraryThemeCardCallbacks(
            show_menu=lambda _name, _item, _anchor: None,
            select_theme=lambda _name, _item: None,
            preview_theme=lambda _name, _item: None,
            apply_theme=lambda _name: None,
            duplicate_theme=lambda _name, _item: None,
            remove_theme=lambda _name: None,
            set_startup_theme=lambda _name, _enabled: None,
        )
        return ThemeGalleryBrowserPanel(
            cards_layout=layout,
            cards_container=container,
            browser_scroll=browser_scroll,
            browser_box=QGroupBox("Themes"),
            filter_edit=filter_edit,
            type_combo=type_combo,
            sort_combo=sort_combo,
            current_theme_label=QLabel(),
            translate=lambda _en, pl: pl,
            resolve_path=lambda raw: Path(raw),
            pixmap_for_item=lambda _item, size: QPixmap(size),
            card_factory=lambda _kind: QWidget(),
            callbacks=callbacks,
        )

    def test_rebuild_renders_filtered_cards(self) -> None:
        panel = self._make_panel(search="orbital")

        panel.rebuild(
            theme_items={
                "Heritage Duality": {"type": "theme-doc", "path": "heritage.json"},
                "Orbital Relay": {"type": "theme-doc", "path": "orbital.json"},
            },
            current_name="Orbital Relay",
            startup_theme_name="",
        )

        self.assertEqual(panel.cards_layout.count(), 1)
        self.assertIn("Orbital Relay", panel.current_theme_label.text())

    def test_rebuild_shows_empty_state(self) -> None:
        panel = self._make_panel(search="missing")

        panel.rebuild(
            theme_items={"Heritage Duality": {"type": "theme-doc", "path": "heritage.json"}},
            current_name="",
            startup_theme_name="",
        )

        self.assertEqual(panel.cards_layout.count(), 1)
        widget = panel.cards_layout.itemAt(0).widget()
        self.assertIsInstance(widget, QLabel)
        self.assertIn("Brak motywów", widget.text())

    def test_asset_gallery_panel_renders_image_assets(self) -> None:
        container = QWidget()
        layout = QGridLayout(container)
        panel = ThemeAssetGalleryPanel(
            asset_layout=layout,
            asset_container=container,
            card_factory=lambda _kind: QWidget(),
            callbacks=AssetGalleryCardCallbacks(
                use_as_background=lambda _path: None,
                use_as_image=lambda _path: None,
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.png").write_bytes(b"")
            (root / "ignored.txt").write_text("x", encoding="utf-8")

            panel.rebuild(root)

        self.assertEqual(layout.count(), 1)

    def test_asset_gallery_panel_shows_empty_state(self) -> None:
        container = QWidget()
        layout = QGridLayout(container)
        panel = ThemeAssetGalleryPanel(
            asset_layout=layout,
            asset_container=container,
            card_factory=lambda _kind: QWidget(),
            callbacks=AssetGalleryCardCallbacks(
                use_as_background=lambda _path: None,
                use_as_image=lambda _path: None,
            ),
        )

        panel.rebuild(Path("/definitely/missing/open-trofeo-assets"))

        self.assertEqual(layout.count(), 1)
        widget = layout.itemAt(0).widget()
        self.assertIsInstance(widget, QLabel)
        self.assertIn("Brak assetów", widget.text())

    def test_theme_gallery_action_bar_builds_controls_and_wires_actions(self) -> None:
        calls: list[str] = []
        action_bar = build_theme_gallery_action_bar(
            template_catalog=[{"title": "Dashboard", "path": "themes/dashboard.json"}],
            callbacks=ThemeGalleryActionCallbacks(
                refresh_themes=lambda: calls.append("refresh"),
                import_ttcr=lambda: calls.append("import"),
                browse_new_theme_path=lambda: calls.append("browse"),
                create_new_theme=lambda: calls.append("create"),
                suggest_new_theme_path=lambda *_args: calls.append("suggest"),
                mark_new_theme_path_customized=lambda text: calls.append(f"mark:{text}"),
                toggle_new_theme_advanced=lambda checked: calls.append(f"toggle:{checked}"),
            ),
            default_path="themes/new.json",
        )

        self.assertEqual(action_bar.template_combo.itemText(0), "Dashboard")
        self.assertEqual(action_bar.path_edit.text(), "themes/new.json")
        self.assertFalse(action_bar.path_row.isVisible())
        action_bar.refresh_btn.click()
        action_bar.import_ttcr_btn.click()
        action_bar.browse_btn.click()
        action_bar.create_btn.click()
        action_bar.advanced_btn.setChecked(True)
        action_bar.path_edit.textEdited.emit("custom.json")

        self.assertIn("refresh", calls)
        self.assertIn("import", calls)
        self.assertIn("browse", calls)
        self.assertIn("create", calls)
        self.assertIn("toggle:True", calls)
        self.assertIn("mark:custom.json", calls)
        self.assertTrue(action_bar.root.findChildren(QPushButton))

    def test_build_theme_gallery_panel_composes_browser_assets_and_aliases(self) -> None:
        calls: list[str] = []
        root = QWidget()
        layout = QVBoxLayout(root)
        controls = build_theme_gallery_panel(
            library_layout=layout,
            template_catalog=[{"title": "Dashboard", "path": "themes/dashboard.json"}],
            default_path="themes/new.json",
            action_callbacks=ThemeGalleryActionCallbacks(
                refresh_themes=lambda: calls.append("refresh"),
                import_ttcr=lambda: calls.append("import"),
                browse_new_theme_path=lambda: calls.append("browse"),
                create_new_theme=lambda: calls.append("create"),
                suggest_new_theme_path=lambda *_args: calls.append("suggest"),
                mark_new_theme_path_customized=lambda text: calls.append(f"mark:{text}"),
                toggle_new_theme_advanced=lambda checked: calls.append(f"toggle:{checked}"),
            ),
            browser_callbacks=LibraryThemeCardCallbacks(
                show_menu=lambda _name, _item, _anchor: calls.append("menu"),
                select_theme=lambda _name, _item: calls.append("select"),
                preview_theme=lambda _name, _item: calls.append("preview"),
                apply_theme=lambda _name: calls.append("apply"),
                duplicate_theme=lambda _name, _item: calls.append("duplicate"),
                remove_theme=lambda _name: calls.append("remove"),
                set_startup_theme=lambda _name, _enabled: calls.append("startup"),
            ),
            asset_callbacks=AssetGalleryCardCallbacks(
                use_as_background=lambda _path: calls.append("background"),
                use_as_image=lambda _path: calls.append("image"),
            ),
            translate=lambda en, _pl: en,
            resolve_path=lambda raw: Path(raw),
            pixmap_for_item=lambda _item, size: QPixmap(size),
            card_factory=lambda _kind: QWidget(),
        )
        owner = SimpleNamespace()
        bind_theme_gallery_panel_controls(owner, controls)

        self.assertEqual(layout.count(), 3)
        self.assertIs(owner.theme_gallery_browser, controls.browser_panel)
        self.assertIs(owner.theme_asset_gallery_panel, controls.asset_gallery_panel)
        self.assertEqual(owner.library_theme_type_combo.count(), 6)
        self.assertEqual(owner.new_theme_path_edit.text(), "themes/new.json")
        self.assertFalse(owner.asset_gallery_box.isVisible())

    def test_theme_gallery_refresh_coordinator_defers_until_visible_and_debounces_width(self) -> None:
        calls: list[str] = []
        visible = {"value": False}
        width = {"value": 900}
        coordinator = ThemeGalleryRefreshCoordinator(
            is_visible=lambda: visible["value"],
            browser_width=lambda: width["value"],
            rebuild=lambda: calls.append("rebuild"),
        )

        coordinator.schedule_for_resize()
        QApplication.processEvents()
        self.assertEqual(calls, [])
        self.assertTrue(coordinator.dirty)

        visible["value"] = True
        coordinator.maybe_rebuild_visible()
        self.assertEqual(calls, ["rebuild"])
        self.assertFalse(coordinator.dirty)

        coordinator.schedule_for_resize()
        QApplication.processEvents()
        self.assertEqual(calls, ["rebuild", "rebuild"])

        coordinator.schedule_for_resize()
        QApplication.processEvents()
        self.assertEqual(calls, ["rebuild", "rebuild"])

        width["value"] = 1100
        coordinator.schedule_for_resize()
        QApplication.processEvents()
        self.assertEqual(calls, ["rebuild", "rebuild", "rebuild"])


if __name__ == "__main__":
    unittest.main()
