import json
import tempfile
import unittest
from pathlib import Path

from trofeo_backend import BackendConfig, ReplayController


def make_config(root: Path) -> BackendConfig:
    return BackendConfig(
        workdir=root, pcap_path=root / "capture.pcapng", frame_index=0,
        host="127.0.0.1", port=18777, ack_timeout_ms=120,
        inter_packet_delay=0.0005, frame_delay=0.05, connect_retries=1,
        connect_retry_delay=0.1, python_bin="python3",
        replay_script=root / "replay_from_pcap.py", trofeo_script=root / "trofeo_lcd.py",
        trcc_static_script=root / "scripts/trcc_static_image.py",
        trcc_static_overlay_script=root / "scripts/trcc_static_overlay_image.py",
        trcc_animation_script=root / "scripts/trcc_animated_image.py",
        child_log_file=root / "backend.log", themes_file=root / ".trofeo-themes.json",
        playlist_file=root / ".trofeo-playlist.json", display_backend="native", trcc_bin="trcc",
    )


class BundledThemeUpgradeTests(unittest.TestCase):
    def test_new_linux_themes_join_existing_library_without_reviving_removed_themes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            themes_dir = root / "themes"
            themes_dir.mkdir()
            for filename, name in (
                ("amber_hi_fi.json", "Amber Hi-Fi"),
                ("kernel_console.json", "Kernel Console"),
                ("penguin_circuit.json", "Penguin Circuit"),
            ):
                (themes_dir / filename).write_text(json.dumps({"meta": {"name": name}}), encoding="utf-8")
            original = {"My Theme": {"path": "custom/my_theme.json", "raw_jpeg_passthrough": True}}
            cfg = make_config(root)
            cfg.themes_file.write_text(json.dumps(original), encoding="utf-8")

            first = ReplayController(cfg)
            self.assertEqual(set(first.themes), {"My Theme", "Kernel Console", "Penguin Circuit"})
            self.assertEqual(first.themes["My Theme"], original["My Theme"])
            first.themes.pop("Kernel Console")
            first._save_themes()

            second = ReplayController(cfg)
            self.assertEqual(set(second.themes), {"My Theme", "Penguin Circuit"})

    def test_trcc_keeps_slow_frame_durations(self) -> None:
        spec = {"frame_durations_ms": [250] * 8, "fps": 4.0}
        ReplayController._tune_trcc_animation_spec(None, spec)
        self.assertEqual(spec["frame_durations_ms"], [250] * 8)
        self.assertEqual(spec["fps"], 4.0)
        self.assertNotIn("trcc_playback_tuned", spec)


if __name__ == "__main__":
    unittest.main()
