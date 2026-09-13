import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from trofeo_backend import ReplayController


class AnimationReadinessTest(unittest.TestCase):
    def run_start(self, ready):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame = root / 'frame.png'
            frame.write_bytes(b'x' * 64)
            controller = ReplayController.__new__(ReplayController)
            controller.cfg = SimpleNamespace(trcc_animation_script=frame,
                child_log_file=root / 'worker.log', workdir=root)
            controller._resolve_trcc_python = Mock(return_value=Path('/usr/bin/python3'))
            controller._runtime_temp_file = Mock(return_value=root / 'manifest.json')
            controller._preflight_trcc_display_start = Mock()
            controller._cleanup_proc_locked = Mock()
            controller._log = Mock()
            controller._stop_display_worker = Mock()
            controller._recover_trcc_usb = Mock()
            def start(cmd, **kwargs):
                if ready:
                    Path(cmd[cmd.index('--ready-file') + 1]).write_text('ready\n')
                return SimpleNamespace(pid=123, poll=lambda: None)
            with patch('trofeo_backend.subprocess.Popen', side_effect=start), \
                 patch('trofeo_backend.time.sleep'), \
                 patch('trofeo_backend.time.monotonic', side_effect=range(0, 1000, 20)):
                return controller._start_trcc_animation_worker(
                    {'frame_paths': [str(frame)], 'frame_count': 1})

    def test_first_frame_confirmation_is_required(self):
        with self.assertRaisesRegex(RuntimeError, 'first-frame readiness timeout'):
            self.run_start(False)

    def test_confirmed_first_frame_starts_worker(self):
        self.assertEqual(self.run_start(True)['pid'], 123)
