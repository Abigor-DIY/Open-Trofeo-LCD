import contextlib
import io
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from scripts.display_preferences import (
    DisplayRotation, read_display_rotation, save_display_rotation, validate_display_rotation,
)
from scripts.trcc_runtime import _RotatedDisplay
from trofeo_backend import ReplayController
import trofeo_lcd


class DisplayRotationTests(unittest.TestCase):
    def test_rotation_is_persistent_and_existing_worker_sees_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "display.json"
            worker = DisplayRotation(path)
            self.assertEqual(worker.value, 0)
            save_display_rotation(path, 180)
            self.assertEqual(worker.value, 180)
            self.assertEqual(DisplayRotation(path).value, 180)
            save_display_rotation(path, 0)
            self.assertEqual(worker.value, 0)
            self.assertEqual(read_display_rotation(path), 0)

    def test_invalid_rotation_is_rejected_and_does_not_replace_saved_value(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "display.json"
            save_display_rotation(path, 180)
            for value in (90, 270, -180, 360, True, 180.0, {}, None):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    save_display_rotation(path, value)
            self.assertEqual(read_display_rotation(path), 180)
            self.assertEqual(validate_display_rotation("180"), 180)

    def test_corrupt_preferences_do_not_flip_a_running_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "display.json"
            save_display_rotation(path, 180)
            worker = DisplayRotation(path)
            self.assertEqual(worker.value, 180)
            path.write_text("{broken")
            self.assertEqual(worker.value, 180)
            self.assertEqual(DisplayRotation(path).value, 0)

    def test_trcc_rotation_applies_only_on_send_and_updates_without_reconnect(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "display.json"
            frame, flipped = object(), object()
            device = Mock()
            renderer = SimpleNamespace(rotate=Mock(return_value=flipped))
            output = _RotatedDisplay(device, renderer, DisplayRotation(path))
            output.load_image("theme.png")
            renderer.rotate.assert_not_called()
            output.send_frame(frame)
            device.send_frame.assert_called_once_with(frame)
            save_display_rotation(path, 180)
            output.send_frame(frame)
            device.send_frame.assert_called_with(flipped)
            output.send(frame)
            device.send.assert_called_once_with(flipped)
            save_display_rotation(path, 0)
            output.send(frame)
            device.send.assert_called_with(frame)
            self.assertEqual(renderer.rotate.call_count, 2)

    def test_backend_saves_global_rotation_without_restart_or_theme_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = ReplayController.__new__(ReplayController)
            controller.cfg = SimpleNamespace(workdir=Path(folder), display_rotation=0)
            controller.cfg.as_json = lambda: {"display_rotation": controller.cfg.display_rotation}
            controller.lock = threading.RLock()
            controller.proc = SimpleNamespace(poll=lambda: None)
            controller._log = Mock()
            controller.stats_provider = SimpleNamespace(**{
                name: lambda: {} for name in ("weather_status", "read_volume_stats", "audio_eq_status",
                                             "fps_probe_status", "game_status")
            })
            controller.restart_loop = Mock()
            controller.scan_capture = Mock()
            result = controller.set_config({"display_rotation": 180})
            self.assertTrue(result["running"])
            self.assertEqual(result["config"]["display_rotation"], 180)
            self.assertEqual(read_display_rotation(Path(folder) / ".trofeo-display.json"), 180)
            controller.restart_loop.assert_not_called()
            controller.scan_capture.assert_not_called()
            with self.assertRaises(ValueError):
                controller.set_config({"display_rotation": 90})
            self.assertEqual(controller.cfg.display_rotation, 180)

    def test_legacy_renderer_uses_apply_rotation_when_rotate_is_absent(self):
        image, flipped = object(), object()
        renderer = SimpleNamespace(apply_rotation=Mock(return_value=flipped))
        device = Mock()
        output = _RotatedDisplay(device, renderer, SimpleNamespace(value=180))
        self.assertTrue(output.send_frame(image))
        renderer.apply_rotation.assert_called_once_with(image, 180)
        device.send_frame.assert_called_once_with(flipped)

    def test_native_static_loop_rotates_cached_jpeg_and_back_without_usb_reconnect(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "display.json"
            image_path = Path(folder) / "theme.jpg"
            image = Image.new("RGB", (1920, 462), "red")
            image.paste("blue", (960, 0, 1920, 462))
            image.save(image_path)
            lcd = trofeo_lcd.TrofeoLCD()
            lcd._display_rotation = DisplayRotation(path)
            frames = []

            def send(jpeg, **_kwargs):
                with Image.open(io.BytesIO(jpeg)) as decoded:
                    frames.append((decoded.getpixel((50, 50)), decoded.getpixel((1870, 412))))
                save_display_rotation(path, 180 if len(frames) == 1 else 0)
                return True

            lcd.connect = Mock(return_value=True)
            lcd.disconnect = Mock()
            lcd.send_jpeg = send
            arguments = ["trofeo_lcd.py", str(image_path), "--loop", "--max-frames", "3",
                         "--skip-unchanged", "--raw-jpeg-passthrough", "--interval", "0"]
            with patch("sys.argv", arguments), patch.object(trofeo_lcd, "TrofeoLCD", return_value=lcd), \
                    patch.object(trofeo_lcd.signal, "signal"), contextlib.redirect_stdout(io.StringIO()):
                trofeo_lcd.main()
            self.assertEqual(len(frames), 3)
            self.assertGreater(frames[0][0][0], 240)
            self.assertGreater(frames[1][0][2], 240)
            self.assertGreater(frames[2][0][0], 240)
            lcd.connect.assert_called_once()
            lcd.disconnect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
