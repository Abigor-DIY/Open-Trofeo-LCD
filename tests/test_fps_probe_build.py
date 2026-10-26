import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class FpsProbeBuildTests(unittest.TestCase):
    def test_forced_upgrade_replaces_the_library_atomically_and_marks_the_new_probe(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / "scripts").mkdir()
            probe = project / "native/fps_probe"
            probe.mkdir(parents=True)
            for name in ("Makefile", "open_trofeo_fps_probe.c"):
                shutil.copy2(root / "native/fps_probe" / name, probe / name)
            script = project / "scripts/build_fps_probe.sh"
            shutil.copy2(root / "scripts/build_fps_probe.sh", script)

            def build():
                return subprocess.run(["bash", str(script), "--always-make"], check=True,
                                      capture_output=True, text=True, timeout=30)

            build()
            library = probe / "libopen_trofeo_fps_probe.so"
            with library.open("rb") as original:
                before = original.read()
                inode = os.fstat(original.fileno()).st_ino
                build()
                self.assertNotEqual(library.stat().st_ino, inode)
                original.seek(0)
                self.assertEqual(original.read(), before)
            self.assertEqual(library.read_bytes()[:4], b"\x7fELF")
            manifest = json.loads((probe / "implicit_layer.d/VkLayer_OPEN_TROFEO_fps.json").read_text())
            self.assertEqual(manifest["layer"]["implementation_version"], "2")
            self.assertEqual(manifest["layer"]["library_path"], str(library))


if __name__ == "__main__":
    unittest.main()
