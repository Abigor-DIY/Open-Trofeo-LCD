import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QWidget

from system_panel import SystemPanelCallbacks, bind_system_panel_controls, build_system_panel


class SystemPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_build_system_panel_creates_dashboard_sections_and_wires_actions(self) -> None:
        calls: list[str] = []

        def intro_card(name: str) -> QFrame:
            frame = QFrame()
            frame.setObjectName(name)
            return frame

        def status_row(title: str, value: str) -> tuple[QWidget, QLabel, QLabel]:
            row = QWidget()
            layout = QHBoxLayout(row)
            title_label = QLabel(title)
            value_label = QLabel(value)
            layout.addWidget(title_label)
            layout.addWidget(value_label)
            return row, title_label, value_label

        def metric_card(title: str) -> tuple[QFrame, QLabel, QLabel, QLabel]:
            frame = QFrame()
            title_label = QLabel(title)
            value_label = QLabel("-")
            detail_label = QLabel("-")
            return frame, title_label, value_label, detail_label

        controls = build_system_panel(
            app_version_text="v-test",
            intro_card_factory=intro_card,
            status_row_factory=status_row,
            metric_card_factory=metric_card,
            callbacks=SystemPanelCallbacks(
                restart_backend=lambda: calls.append("restart-backend"),
                restart_service=lambda: calls.append("restart-service"),
                refresh_status=lambda: calls.append("refresh"),
                export_logs=lambda: calls.append("export"),
                diagnostics=lambda: calls.append("diagnostics"),
            ),
        )

        controls.system_restart_backend_btn.click()
        controls.system_restart_service_btn.click()
        controls.system_refresh_status_btn.click()
        controls.system_export_logs_btn.click()
        controls.system_diagnostic_btn.click()

        self.assertEqual(controls.backend_status_box.title(), "Backend status")
        self.assertEqual(controls.system_app_version_value.text(), "v-test")
        self.assertEqual(controls.system_resolution_value.text(), "1920 x 462")
        self.assertEqual(len(controls.system_events_header_labels), 4)
        self.assertEqual(calls, ["restart-backend", "restart-service", "refresh", "export", "diagnostics"])

    def test_bind_system_panel_controls_exposes_legacy_owner_aliases(self) -> None:
        controls = build_system_panel(
            app_version_text="v-test",
            intro_card_factory=lambda name: QFrame(),
            status_row_factory=lambda title, value: (QWidget(), QLabel(title), QLabel(value)),
            metric_card_factory=lambda title: (QFrame(), QLabel(title), QLabel("-"), QLabel("-")),
            callbacks=SystemPanelCallbacks(
                restart_backend=lambda: None,
                restart_service=lambda: None,
                refresh_status=lambda: None,
                export_logs=lambda: None,
                diagnostics=lambda: None,
            ),
        )
        owner = SimpleNamespace()

        bind_system_panel_controls(owner, controls)

        self.assertIs(owner.system_intro_text_label, controls.intro_label)
        self.assertIs(owner.system_api_status_value, controls.system_api_status_value)
        self.assertIs(owner.system_cpu_value, controls.system_cpu_value)
        self.assertIs(owner.system_events_list, controls.system_events_list)
        self.assertIs(owner.system_diagnostic_btn, controls.system_diagnostic_btn)


if __name__ == "__main__":
    unittest.main()
