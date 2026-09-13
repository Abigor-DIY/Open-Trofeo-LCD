import os
import tempfile
import unittest
from pathlib import Path

from ui_resources import UI_LANGUAGES, UI_THEMES, detect_app_version


class UiResourcesTests(unittest.TestCase):
    def test_ui_constants_keep_expected_defaults(self) -> None:
        self.assertEqual(UI_LANGUAGES["Polski"], "pl")
        self.assertIn("Plasma Blue", UI_THEMES)

    def test_detect_app_version_prefers_local_package_marker(self) -> None:
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                Path(".package-source-version").write_text("deb-0.1.0~local\n", encoding="utf-8")
                self.assertEqual(detect_app_version(), "v0.1.0~local")
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
