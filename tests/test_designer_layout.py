import unittest

from designer.layout import (
    clamp_designer_splitter_sizes,
    designer_canvas_max_height,
    designer_inspector_min_height,
    designer_splitter_limits,
    should_switch_inspector_tab,
)


class DesignerLayoutTests(unittest.TestCase):
    def test_splitter_limits_use_compact_and_tall_window_profiles(self) -> None:
        self.assertEqual(designer_splitter_limits(900), (280, 380))
        self.assertEqual(designer_splitter_limits(1200), (320, 460))

    def test_canvas_max_height_respects_window_and_content_bounds(self) -> None:
        self.assertEqual(designer_canvas_max_height(900, 0, 280), 430)
        self.assertEqual(designer_canvas_max_height(900, 300, 280), 300)
        self.assertEqual(designer_canvas_max_height(1200, 900, 320), 500)

    def test_inspector_min_height_uses_stable_window_profiles(self) -> None:
        self.assertEqual(designer_inspector_min_height(900), 340)
        self.assertEqual(designer_inspector_min_height(1200), 400)

    def test_clamp_splitter_sizes_limits_canvas_and_inspector(self) -> None:
        self.assertEqual(
            clamp_designer_splitter_sizes([900, 900], min_canvas=280, max_canvas=430, max_inspector=380),
            [430, 380],
        )
        self.assertEqual(
            clamp_designer_splitter_sizes([120, 90], min_canvas=280, max_canvas=430, max_inspector=380),
            [280, 180],
        )

    def test_clamp_splitter_sizes_respects_stable_inspector_minimum(self) -> None:
        self.assertEqual(
            clamp_designer_splitter_sizes(
                [430, 210],
                min_canvas=280,
                max_canvas=430,
                max_inspector=380,
                min_inspector=340,
            ),
            [300, 340],
        )

    def test_clamp_splitter_sizes_ignores_tiny_jitter(self) -> None:
        self.assertIsNone(
            clamp_designer_splitter_sizes([284, 184], min_canvas=280, max_canvas=430, max_inspector=380)
        )

    def test_should_switch_inspector_tab_keeps_visible_user_context(self) -> None:
        self.assertFalse(should_switch_inspector_tab(current_visible=True, preferred_visible=True))
        self.assertTrue(should_switch_inspector_tab(current_visible=False, preferred_visible=True))
        self.assertFalse(should_switch_inspector_tab(current_visible=False, preferred_visible=False))
        self.assertTrue(should_switch_inspector_tab(current_visible=True, preferred_visible=True, force=True))


if __name__ == "__main__":
    unittest.main()
