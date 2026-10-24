import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import trcc_runtime
from trofeo_backend import ReplayController


class TrccRuntimeTests(unittest.TestCase):
    def test_current_api_is_used_when_legacy_cli_was_removed(self):
        def load(name):
            if name == "trcc.cli":
                raise ModuleNotFoundError("No module named 'trcc.cli'", name=name)
            return SimpleNamespace()
        with patch.object(trcc_runtime.importlib, "import_module", side_effect=load):
            self.assertEqual(trcc_runtime.load_api()[0], "commands")

    def test_missing_dependency_is_not_mistaken_for_an_api_migration(self):
        error = ModuleNotFoundError("No module named 'PySide6'", name="PySide6")
        with patch.object(trcc_runtime.importlib, "import_module", side_effect=error):
            with self.assertRaises(ModuleNotFoundError) as raised:
                trcc_runtime.load_api()
        self.assertEqual(raised.exception.name, "PySide6")

    def test_frame_send_is_synchronous_and_transfer_failure_is_reported(self):
        app = SimpleNamespace(dispatch=Mock(return_value=SimpleNamespace(ok=False, message="USB timeout")))
        commands = SimpleNamespace(SendImage=lambda **kwargs: SimpleNamespace(**kwargs))
        image = SimpleNamespace(save=Mock(return_value=True))
        display = trcc_runtime._CommandDisplay(app, commands, "0416:5408", Mock())
        try:
            with self.assertRaisesRegex(RuntimeError, "USB timeout"):
                display.send_frame(image)
            app.dispatch.assert_called_once()
            self.assertEqual(app.dispatch.call_args.args[0].key, "0416:5408")
            self.assertEqual(app.dispatch.call_args.args[0].path, display.frame_path)
        finally:
            display.directory.cleanup()

    def test_unwritable_staging_file_never_sends_a_stale_frame(self):
        app = SimpleNamespace(dispatch=Mock())
        display = trcc_runtime._CommandDisplay(app, Mock(), "0416:5408", Mock())
        try:
            with self.assertRaisesRegex(RuntimeError, "stage TRCC frame"):
                display.send_frame(SimpleNamespace(save=lambda *args: False))
            app.dispatch.assert_not_called()
        finally:
            display.directory.cleanup()

    def test_launcher_shebang_preserves_the_installation_interpreter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            interpreter = root / "isolated" / "python3"
            interpreter.parent.mkdir()
            interpreter.touch()
            launcher = root / "trcc"
            launcher.write_text(f"#!{interpreter}\n")
            controller = ReplayController.__new__(ReplayController)
            controller.cfg = SimpleNamespace(workdir=root, trcc_bin=str(launcher))
            self.assertEqual(controller._resolve_trcc_python(), interpreter)

    def test_venv_python_symlink_is_not_resolved_out_of_its_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "trcc").touch()
            (root / "python").symlink_to("/usr/bin/python3")
            controller = ReplayController.__new__(ReplayController)
            controller.cfg = SimpleNamespace(workdir=root, trcc_bin=str(root / "trcc"))
            self.assertEqual(controller._resolve_trcc_python(), root / "python")
