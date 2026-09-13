import os
from pathlib import Path
import tempfile
import unittest
from process_memory import scan_process_memory


class ProcessMemoryTests(unittest.TestCase):
    def test_rss_ranking_ignores_exited_and_invalid_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for pid, pages, name in [(10, 100, 'small'), (20, 800, 'game.exe'), (30, 200, 'steam')]:
                entry = root / str(pid)
                entry.mkdir()
                (entry / 'statm').write_text(f'1000 {pages} 0')
                (entry / 'comm').write_text(name)
            (root / '99').mkdir()
            (root / 'self').mkdir()
            result = scan_process_memory(root)
            self.assertEqual(result['process_ram_1_name'], 'game.exe')
            self.assertEqual(result['process_ram_1_pid'], '20')
            self.assertEqual(result['process_ram_2_name'], 'steam')
            self.assertEqual(result['process_ram_4_name'], 'N/A')
            self.assertEqual(result['process_ram_1_mb'], f'{800 * os.sysconf("SC_PAGE_SIZE") / 1048576:.0f}')
