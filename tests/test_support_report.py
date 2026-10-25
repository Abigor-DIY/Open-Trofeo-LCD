import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import trofeo_support_report as report


class SupportReportTests(unittest.TestCase):
    def test_status_excludes_weather_coordinates_and_unrelated_configuration(self):
        payload = {"running": True, "config": {"weather": {"latitude": 12.34567, "longitude": 34.56789},
                   "private_token": "secret-value", "fps_probe": {"active": "no", "source": "waiting"},
                   "game": {"game_name": "Enshrouded"}}}
        response = Mock()
        response.read.return_value = json.dumps(payload).encode()
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch.object(report.urllib.request, "build_opener", return_value=opener):
            data = report.backend_state("http://127.0.0.1:18777")
        self.assertEqual(data["fps_probe"]["active"], "no")
        self.assertEqual(data["game"]["game_name"], "Enshrouded")
        text = json.dumps(data)
        for forbidden in ("latitude", "longitude", "12.34567", "secret-value"):
            self.assertNotIn(forbidden, text)

    def test_only_local_backend_origins_are_allowed(self):
        for url in ("http://example.com", "http://user:pass@localhost", "http://localhost/other"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                report.backend_state(url)

    def test_report_redacts_home_and_runtime_paths(self):
        text = report.redact({"path": "/home/test/.local/data", "socket": "/run/user/1000/fps.sock"},
                             Path("/home/test"), "/run/user/1000")
        self.assertNotIn("/home/test", text)
        self.assertNotIn("/run/user/1000", text)
        self.assertIn("$HOME", text)
        self.assertIn("$RUNTIME", text)

    def test_manifest_identifies_missing_library_and_elf_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "layer.json"
            manifest.write_text(json.dumps({"layer": {"name": "test", "library_path": "probe.so"}}))
            self.assertFalse(report.manifest_state(manifest)["library"]["exists"])
            (root / "probe.so").write_bytes(b"\x7fELF\x02" + b"\x00" * 20)
            self.assertEqual(report.manifest_state(manifest)["library"]["elf_bits"], 64)

    def test_game_environment_is_whitelisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "1234"
            proc.mkdir()
            (proc / "comm").write_text("enshrouded.exe\n")
            (proc / "environ").write_bytes(b"OPEN_TROFEO_FPS_LAYER=1\0PRIVATE_TOKEN=hidden\0")
            (proc / "maps").write_text("libopen_trofeo_fps_probe.so\nMangoHud.so\n")
            result = report.game_processes("Enshrouded", "/tmp/fps.sock", root)
            self.assertEqual(result[0]["env"], {"OPEN_TROFEO_FPS_LAYER": "1"})
            self.assertTrue(result[0]["probe_library_loaded"])
            self.assertTrue(result[0]["mangohud_loaded"])
            self.assertNotIn("hidden", json.dumps(result))
