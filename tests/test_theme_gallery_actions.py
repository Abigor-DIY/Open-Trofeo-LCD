import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from theme_gallery_actions import ThemeGalleryActionController


class _TextBox:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, value: str) -> None:
        self.value = value

    def text(self) -> str:
        return self.value


class _ComboBox:
    def __init__(self) -> None:
        self.value = ""

    def setCurrentText(self, value: str) -> None:
        self.value = value


class ThemeGalleryActionControllerTests(unittest.TestCase):
    def test_select_theme_loads_editable_theme_doc_and_goes_to_designer(self) -> None:
        calls: list[str] = []
        owner = SimpleNamespace(
            theme_combo=_ComboBox(),
            theme_doc_path_edit=_TextBox(),
            load_theme_doc=lambda: calls.append("load"),
            _go_designer=lambda: calls.append("designer"),
        )
        controller = ThemeGalleryActionController(owner)

        controller.select_theme("Orbital Relay", {"type": "theme-doc", "path": "themes/orbital.json"})

        self.assertEqual(owner.theme_combo.value, "Orbital Relay")
        self.assertEqual(owner.theme_doc_path_edit.text(), "themes/orbital.json")
        self.assertEqual(calls, ["load", "designer"])

    def test_startup_theme_preference_updates_state_and_rebuilds(self) -> None:
        calls: list[str] = []
        owner = SimpleNamespace(
            _startup_theme_name="",
            _startup_theme_applied=True,
            _save_ui_state=lambda: calls.append("save"),
            _rebuild_library_theme_browser=lambda: calls.append("rebuild"),
            append_log=lambda message: calls.append(message),
        )
        controller = ThemeGalleryActionController(owner)

        controller.set_startup_theme_preference("Daily", True)

        self.assertEqual(owner._startup_theme_name, "Daily")
        self.assertFalse(owner._startup_theme_applied)
        self.assertIn("save", calls)
        self.assertIn("rebuild", calls)
        self.assertTrue(any("Ustawiono motyw startowy" in call for call in calls))

        controller.set_startup_theme_preference("Daily", False)

        self.assertEqual(owner._startup_theme_name, "")
        self.assertTrue(any("Wyczyszczono motyw startowy" in call for call in calls))

    def test_apply_startup_theme_applies_once_when_theme_exists(self) -> None:
        applied: list[str] = []
        owner = SimpleNamespace(
            _startup_theme_applied=False,
            _startup_theme_name="Daily",
            theme_items={"Daily": {"type": "theme-doc"}},
            _apply_runtime_theme_card=lambda name: applied.append(name),
        )
        controller = ThemeGalleryActionController(owner)

        controller.apply_startup_theme_if_needed()
        controller.apply_startup_theme_if_needed()

        self.assertEqual(applied, ["Daily"])
        self.assertTrue(owner._startup_theme_applied)

    def test_duplicate_theme_card_writes_copy_and_registers_theme(self) -> None:
        calls: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "daily.json"
            source.write_text(json.dumps({"meta": {"name": "Daily"}, "canvas": {}}), encoding="utf-8")
            owner = SimpleNamespace(
                _tr=lambda en, _pl: en,
                _resolve_theme_asset_path=lambda raw: Path(raw),
                api_call=lambda *args, **kwargs: calls.append({"args": args, "kwargs": kwargs}),
            )
            controller = ThemeGalleryActionController(owner)

            controller.duplicate_theme_card("Daily", {"type": "theme-doc", "path": str(source)})

            copy_path = root / "daily_kopia.json"
            self.assertTrue(copy_path.exists())
            copied = json.loads(copy_path.read_text(encoding="utf-8"))
            self.assertEqual(copied["meta"]["name"], "Daily Kopia")
            self.assertEqual(calls[0]["args"][0], "theme-add")


if __name__ == "__main__":
    unittest.main()
