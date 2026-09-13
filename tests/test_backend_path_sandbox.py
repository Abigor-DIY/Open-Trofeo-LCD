import tempfile
import unittest
from pathlib import Path

from trofeo_backend import BackendConfig, ReplayController, resolve_under_workdir, workdir_relative_path


class BackendPathSandboxTests(unittest.TestCase):
    def test_resolve_under_workdir_accepts_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = resolve_under_workdir(root, "themes/example.json")

        self.assertEqual(resolved, root / "themes" / "example.json")

    def test_resolve_under_workdir_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "escapes workdir"):
                resolve_under_workdir(Path(tmp), "../outside.json")

    def test_resolve_under_workdir_rejects_absolute_path_outside_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as outside:
                external = Path(outside) / "secret.json"
                with self.assertRaisesRegex(RuntimeError, "escapes workdir"):
                    resolve_under_workdir(Path(tmp), str(external))

    def test_resolve_under_workdir_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root.parent / f"{root.name}-outside"
            outside.mkdir()
            try:
                (outside / "secret.json").write_text("{}", encoding="utf-8")
                (root / "link").symlink_to(outside)
                with self.assertRaisesRegex(RuntimeError, "escapes workdir"):
                    resolve_under_workdir(root, "link/secret.json", must_exist=True)
            finally:
                try:
                    (outside / "secret.json").unlink()
                    outside.rmdir()
                except OSError:
                    pass

    def test_workdir_relative_path_normalizes_absolute_workdir_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "themes" / "theme.json"

            self.assertEqual(workdir_relative_path(root, target), "themes/theme.json")

    def test_bundle_save_and_load_are_sandboxed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = BackendConfig(
                workdir=root,
                pcap_path=root / "capture.pcapng",
                frame_index=0,
                host="127.0.0.1",
                port=18777,
                ack_timeout_ms=120,
                inter_packet_delay=0.0005,
                frame_delay=0.05,
                connect_retries=1,
                connect_retry_delay=0.1,
                python_bin="python3",
                replay_script=root / "replay_from_pcap.py",
                trofeo_script=root / "trofeo_lcd.py",
                trcc_static_script=root / "scripts" / "trcc_static_image.py",
                trcc_static_overlay_script=root / "scripts" / "trcc_static_overlay_image.py",
                trcc_animation_script=root / "scripts" / "trcc_animated_image.py",
                child_log_file=root / "backend.log",
                themes_file=root / "themes.json",
                playlist_file=root / "playlist.json",
                display_backend="native",
                trcc_bin="trcc",
            )
            controller = ReplayController(cfg)

            saved = controller.save_bundle("bundles/test.json")
            self.assertTrue(Path(saved["path"]).exists())
            with self.assertRaisesRegex(RuntimeError, "escapes workdir"):
                controller.save_bundle("../escape.json")
            with self.assertRaisesRegex(RuntimeError, "escapes workdir"):
                controller.load_bundle("../escape.json")


if __name__ == "__main__":
    unittest.main()
