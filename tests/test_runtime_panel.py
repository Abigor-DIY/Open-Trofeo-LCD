import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame

from runtime_panel import LegacyRuntimeCallbacks, bind_legacy_runtime_controls, build_legacy_runtime_panel


class RuntimePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _callbacks(self, calls: list[str]) -> LegacyRuntimeCallbacks:
        return LegacyRuntimeCallbacks(
            apply_url=lambda: calls.append("apply-url"),
            refresh_status=lambda: calls.append("refresh"),
            start=lambda: calls.append("start"),
            stop=lambda: calls.append("stop"),
            restart=lambda: calls.append("restart"),
            scan=lambda: calls.append("scan"),
            hide_to_tray=lambda: calls.append("hide"),
            animate_widget=lambda _widget: calls.append("animate"),
            set_frame=lambda: calls.append("set-frame"),
            browse_image=lambda: calls.append("browse-image"),
            prepare_image=lambda edit: calls.append(f"prepare:{edit.text()}"),
            send_image=lambda: calls.append("send-image"),
            apply_config=lambda: calls.append("apply-config"),
            run_usb_recovery=lambda: calls.append("usb"),
            refresh_themes=lambda: calls.append("themes"),
            apply_theme=lambda: calls.append("apply-theme"),
            remove_theme=lambda: calls.append("remove-theme"),
            browse_theme_path=lambda: calls.append("browse-theme"),
            add_or_update_theme=lambda: calls.append("add-theme"),
        )

    def test_build_legacy_runtime_panel_wires_controls(self) -> None:
        calls: list[str] = []
        controls = build_legacy_runtime_panel(
            base_url="http://127.0.0.1:18777",
            intro_card_factory=lambda name: QFrame(),
            callbacks=self._callbacks(calls),
        )
        calls.clear()

        controls.apply_url_btn.click()
        controls.start_btn.click()
        controls.stop_btn.click()
        controls.prepare_image_btn.click()
        controls.usb_recovery_btn.click()
        controls.theme_add_btn.click()

        self.assertEqual(controls.url_edit.text(), "http://127.0.0.1:18777")
        self.assertEqual(controls.runtime_sections_tabs.count(), 3)
        self.assertEqual(controls.pcap_edit.text(), "dzis.pcapng")
        self.assertEqual(controls.lbl_mode.text(), "-")
        self.assertEqual(controls.theme_path_edit.text(), "reference_frame_trcc.jpg")
        self.assertEqual(calls, ["apply-url", "start", "stop", "prepare:reference_frame_trcc.jpg", "usb", "add-theme"])

    def test_bind_legacy_runtime_controls_exposes_owner_aliases(self) -> None:
        controls = build_legacy_runtime_panel(
            base_url="http://127.0.0.1:18777",
            intro_card_factory=lambda name: QFrame(),
            callbacks=self._callbacks([]),
        )
        owner = SimpleNamespace()

        bind_legacy_runtime_controls(owner, controls)

        self.assertIs(owner.url_edit, controls.url_edit)
        self.assertIs(owner.runtime_sections_tabs, controls.runtime_sections_tabs)
        self.assertIs(owner.lbl_running, controls.lbl_running)
        self.assertIs(owner.usb_recovery_btn, controls.usb_recovery_btn)
        self.assertIs(owner.runtime_theme_cards_layout, controls.runtime_theme_cards_layout)


if __name__ == "__main__":
    unittest.main()
