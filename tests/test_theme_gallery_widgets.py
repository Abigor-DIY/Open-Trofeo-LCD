import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QFrame, QPushButton

from theme_gallery import ThemeCardEntry
from theme_gallery_widgets import (
    AssetGalleryCardCallbacks,
    LibraryThemeCardCallbacks,
    RuntimeThemeCardCallbacks,
    build_asset_gallery_card,
    build_library_theme_card,
    build_runtime_theme_card,
)


class ThemeGalleryWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_build_library_theme_card_wires_labels_and_actions(self) -> None:
        calls: list[tuple[str, str]] = []
        entry = ThemeCardEntry(
            name="Orbital Relay",
            item={"type": "theme-doc", "path": "orbital_relay.json"},
            category="Animated",
            asset_count=2,
            animation_count=259,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "orbital_relay.json").write_text("{}", encoding="utf-8")
            callbacks = LibraryThemeCardCallbacks(
                show_menu=lambda name, _item, _anchor: calls.append(("menu", name)),
                select_theme=lambda name, _item: calls.append(("select", name)),
                preview_theme=lambda name, _item: calls.append(("preview", name)),
                apply_theme=lambda name: calls.append(("apply", name)),
                duplicate_theme=lambda name, _item: calls.append(("duplicate", name)),
                remove_theme=lambda name: calls.append(("remove", name)),
                set_startup_theme=lambda name, enabled: calls.append(("startup", f"{name}:{enabled}")),
            )

            card = build_library_theme_card(
                entry,
                card_width=440,
                card_height_base=228,
                compact_cards=False,
                current_name="Orbital Relay",
                startup_theme_name="",
                translate=lambda _en, pl: pl,
                resolve_path=lambda raw: root / raw,
                pixmap_for_item=lambda _item, size: QPixmap(size),
                card_factory=lambda _kind: QFrame(),
                callbacks=callbacks,
            )

        self.assertEqual(card.objectName(), "libraryCard")
        self.assertTrue(card.findChildren(QCheckBox))
        button_texts = [button.text() for button in card.findChildren(QPushButton)]
        self.assertIn("Edytuj", button_texts)
        self.assertIn("Podgląd", button_texts)
        self.assertIn("Zastosuj", button_texts)
        self.assertIn("Duplikuj", button_texts)
        self.assertIn("Usuń", button_texts)

    def test_build_runtime_theme_card_wires_buttons(self) -> None:
        calls: list[tuple[str, str]] = []
        callbacks = RuntimeThemeCardCallbacks(
            select_theme=lambda name: calls.append(("select", name)),
            apply_theme=lambda name: calls.append(("apply", name)),
            remove_theme=lambda name: calls.append(("remove", name)),
        )

        card = build_runtime_theme_card(
            "Heritage Duality",
            {"type": "theme-doc", "path": "heritage_duality.json"},
            current_name="Heritage Duality",
            pixmap_for_item=lambda _item, size: QPixmap(size),
            card_factory=lambda _kind: QFrame(),
            callbacks=callbacks,
        )

        buttons = {button.text(): button for button in card.findChildren(QPushButton)}
        self.assertEqual(buttons["Zastosuj"].objectName(), "primaryButton")
        buttons["Wybierz"].click()
        buttons["Zastosuj"].click()
        buttons["Usuń"].click()

        self.assertEqual(
            calls,
            [
                ("select", "Heritage Duality"),
                ("apply", "Heritage Duality"),
                ("remove", "Heritage Duality"),
            ],
        )

    def test_build_asset_gallery_card_wires_buttons(self) -> None:
        calls: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "asset.png"
            image.write_bytes(b"not a real image")
            callbacks = AssetGalleryCardCallbacks(
                use_as_background=lambda path: calls.append(("background", path.name)),
                use_as_image=lambda path: calls.append(("image", path.name)),
            )

            card = build_asset_gallery_card(
                image,
                asset_root=root,
                card_factory=lambda _kind: QFrame(),
                callbacks=callbacks,
            )

            buttons = {button.text(): button for button in card.findChildren(QPushButton)}
            buttons["Ustaw jako tło"].click()
            buttons["Dodaj jako obraz"].click()

        self.assertEqual(calls, [("background", "asset.png"), ("image", "asset.png")])


if __name__ == "__main__":
    unittest.main()
