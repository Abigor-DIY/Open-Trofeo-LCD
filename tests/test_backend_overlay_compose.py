import unittest

from PIL import Image

from trofeo_backend import ReplayController


class OverlayComposeTests(unittest.TestCase):
    def _overlay(self) -> Image.Image:
        overlay = Image.new("RGBA", (100, 50), (0, 0, 0, 0))
        for x in range(10, 30):
            for y in range(5, 20):
                overlay.putpixel((x, y), (200, 100, 50, 128))
        return overlay

    def test_visible_bbox_tracks_alpha_region_with_padding(self) -> None:
        bbox = ReplayController._overlay_visible_bbox(self._overlay(), padding=4)
        self.assertEqual(bbox, (6, 1, 34, 24))

    def test_visible_bbox_returns_none_for_fully_transparent_image(self) -> None:
        blank = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        self.assertIsNone(ReplayController._overlay_visible_bbox(blank))

    def test_cropped_composite_matches_full_composite(self) -> None:
        base = Image.new("RGBA", (100, 50), (10, 20, 30, 255))
        overlay = self._overlay()
        crop_box = ReplayController._overlay_visible_bbox(overlay, padding=0)

        cropped = ReplayController._composite_overlay_image(base, overlay, crop_box)
        full = ReplayController._composite_overlay_image(base, overlay, None)

        self.assertEqual(cropped.tobytes(), full.tobytes())


if __name__ == "__main__":
    unittest.main()
