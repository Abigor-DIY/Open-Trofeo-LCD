"""Cached Linux RSS ranking; never scan /proc on the render thread."""
import os
from pathlib import Path
import threading
import time


def scan_process_memory(root=Path('/proc')):
    rows = []
    page_mib = os.sysconf('SC_PAGE_SIZE') / (1024 * 1024)
    for entry in root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            rss = int((entry / 'statm').read_text().split()[1]) * page_mib
            name = (entry / 'comm').read_text().strip()
            name = ''.join(c if c.isprintable() else ' ' for c in name)
            if rss > 0:
                rows.append((rss, int(entry.name), name[:40]))
        except (OSError, ValueError, IndexError):
            continue  # Processes may exit between the directory and file reads.
    rows.sort(reverse=True)
    result = {}
    for rank in range(1, 5):
        prefix = f'process_ram_{rank}'
        if rank <= len(rows):
            rss, pid, name = rows[rank - 1]
            result.update({prefix + '_name': name, prefix + '_pid': str(pid),
                           prefix + '_mb': f'{rss:.0f}', prefix + '_gib': f'{rss / 1024:.2f}'})
        else:
            result.update({prefix + suffix: 'N/A' for suffix in ('_name', '_pid', '_mb', '_gib')})
    return result


class ProcessMemoryCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._busy = False
        self._updated = 0.0
        self._values = {}

    def snapshot(self):
        with self._lock:
            result = dict(self._values) if time.monotonic() - self._updated < 15 else {}
            if not self._busy and time.monotonic() - self._updated >= 3:
                self._busy = True
                threading.Thread(target=self._refresh, daemon=True, name='trofeo-process-ram').start()
            return result

    def _refresh(self):
        values = {}
        try:
            values = scan_process_memory()
        except OSError:
            values = {}
        finally:
            with self._lock:
                self._values = values
                self._updated = time.monotonic()
                self._busy = False
