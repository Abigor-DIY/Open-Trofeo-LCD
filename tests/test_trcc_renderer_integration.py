"""Run against an installed TRCC renderer; never discover or access USB."""
import importlib.util
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage

from scripts.display_preferences import DisplayRotation, save_display_rotation
from scripts.trcc_runtime import _Renderer, _RotatedDisplay, load_api


@unittest.skipUnless(importlib.util.find_spec("trcc"), "install trcc-linux to test the actual renderer")
class TrccRendererIntegrationTests(unittest.TestCase):
    def test_actual_legacy_encoder_does_not_reuse_a_previous_rotated_frame(self):
        if load_api()[0] != "legacy":
            self.skipTest("Legacy DeviceService identity cache")
        from trcc.adapters.render.qt import QtRenderer
        from trcc.services.device import DeviceService
        from trcc.services.image import ImageService

        service = DeviceService.__new__(DeviceService)
        service._last_encode_id = None
        service._last_encode_data = None
        service._selected = SimpleNamespace(encoding_params=("bulk", (1920, 462), 0, True))
        service.on_frame_sent = None
        received = []

        def send(data, width, height):
            received.append(data)
            return True

        def encode(image, *_args, **_kwargs):
            return image.pixelColor(0, 0).name().encode()

        service.send_rgb565 = send
        display = SimpleNamespace(send_frame=lambda image: service.send_frame(image, 1920, 462))
        output = _RotatedDisplay(display, QtRenderer(), SimpleNamespace(value=180))
        # Use a plain replacement, because a Mock retains image arguments and
        # would hide the object-id reuse that triggers TRCC's stale JPEG cache.
        with patch.object(ImageService, "encode_for_device", new=encode):
            for index in range(1000):
                image = QImage(1920, 462, QImage.Format.Format_RGB32)
                color = QColor("red" if index % 2 else "blue")
                image.fill(color)
                self.assertTrue(output.send_frame(image))
                self.assertEqual(received[-1], color.name().encode(), f"repeated stale frame {index}")

    def test_actual_renderer_sends_180_degree_frames_and_restores_zero(self):
        from trcc.adapters.render.qt import QtRenderer

        renderer = QtRenderer()
        image = QImage(1920, 462, QImage.Format.Format_RGB32)
        image.fill(QColor("black"))
        points = ((10, 10), (1900, 10), (10, 450), (1900, 450))
        for (x, y), color in zip(points, ("red", "green", "blue", "white")):
            image.setPixelColor(x, y, QColor(color))

        class CaptureDisplay:
            def send(self, frame):
                self.frame = frame.copy()
                return True

            send_frame = send

        # Legacy open_display returns the real Qt renderer; command-based
        # open_display returns our facade. Both must accept the global flip.
        for selected_renderer in (renderer, _Renderer(renderer)):
            with self.subTest(renderer=type(selected_renderer).__name__), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "display.json"
                device = CaptureDisplay()
                output = _RotatedDisplay(device, selected_renderer, DisplayRotation(path))
                for rotation in (0, 180, 0):
                    save_display_rotation(path, rotation)
                    for send in (output.send, output.send_frame):
                        self.assertTrue(send(image))
                        self.assertEqual(device.frame.size(), image.size())
                        for x, y in points:
                            target = (1919 - x, 461 - y) if rotation else (x, y)
                            self.assertEqual(device.frame.pixelColor(*target), image.pixelColor(x, y))
                # Rotating a frame must not modify the animation's cached source.
                self.assertEqual(image.pixelColor(10, 10), QColor("red"))


if __name__ == "__main__":
    unittest.main()
