import json
import csv
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from fps_transport import FpsProbeServer, abstract_socket_name

ROOT = Path(__file__).resolve().parents[1]


class FpsTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.build.cleanup)
        source = Path(cls.build.name) / "sender.c"
        source.write_text(r'''
#define _GNU_SOURCE
#include <sys/socket.h>
#include <unistd.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
static int deny_peer = 0;
static int test_getsockopt(int fd, int level, int option, void *value, socklen_t *length) {
    int result = getsockopt(fd, level, option, value, length);
    if (result == 0 && deny_peer && level == SOL_SOCKET && option == SO_PEERCRED)
        ((struct ucred *)value)->uid = getuid() + 1;
    return result;
}
#define getsockopt test_getsockopt
#include "''' + str(ROOT / "native/fps_probe/open_trofeo_fps_probe.c") + r'''"
#undef getsockopt
static int descriptors(void) {
    DIR *dir = opendir("/proc/self/fd");
    int count = 0;
    while (readdir(dir)) ++count;
    closedir(dir);
    return count;
}
int main(int argc, char **argv) {
    if (argc < 3) return 2;
    setenv("OPEN_TROFEO_FPS_SOCKET", argv[1], 1);
    setenv("OPEN_TROFEO_FPS_LAYER", "1", 1);
    g_last_fps = 120.0;
    g_last_frametime_ms = 1000.0 / 120.0;
    if (strcmp(argv[2], "persistent") == 0) {
        for (int index = 0; index < 3; ++index) {
            if (index && getchar() == EOF) return 2;
            send_sample_locked(UINT64_C(1000000000) + (uint64_t)index * UINT64_C(200000000));
            printf("transport=%d\n", g_transport);
            fflush(stdout);
        }
        return 0;
    }
    if (strcmp(argv[2], "stalled") == 0) {
        for (int index = 0; index < 5000; ++index)
            send_sample_locked(UINT64_C(1000000000) + (uint64_t)index * UINT64_C(200000000));
        return g_transport != 2;
    }
    if (strcmp(argv[2], "missing") == 0) {
        int before = descriptors();
        for (int index = 0; index < 3000; ++index)
            send_sample_locked(UINT64_C(1000000000) + (uint64_t)index * UINT64_C(200000000));
        int after = descriptors();
        printf("descriptor_growth=%d\n", after - before);
        return after - before > 1;
    }
    deny_peer = strcmp(argv[2], "deny") == 0;
    send_sample_locked(UINT64_C(1000000000));
    printf("transport=%d\n", g_transport);
    int expected = deny_peer ? 0 : (strcmp(argv[2], "file") == 0 ? 1 : 2);
    close_stream_locked();
    if (g_sock >= 0) close(g_sock);
    return g_transport != expected;
}
''')
        cls.sender = Path(cls.build.name) / "sender"
        subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-o", str(cls.sender), str(source), "-pthread", "-ldl"],
                       check=True, capture_output=True, text=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "socket" / "fps.sock")
        self.received = []
        self.server = FpsProbeServer(self.path, lambda raw, transport:
                                     self.received.append((json.loads(raw), transport)) if raw else None)
        self.server.start()
        self.addCleanup(self.server.close)
        self.wait(lambda: self.server.abstract_bound)

    def wait(self, condition):
        for _ in range(100):
            if condition():
                return
            time.sleep(0.01)
        self.fail("FPS receiver did not become ready: " + self.server.error)

    def run_sender(self, mode, command=None):
        env = dict(os.environ, OPEN_TROFEO_STATE_HOME=self.temp.name)
        result = subprocess.run(command or [str(self.sender), self.path, mode], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def test_legacy_datagram_is_preferred_and_keeps_private_permissions(self):
        self.run_sender("file")
        self.wait(lambda: len(self.received) == 1)
        self.assertEqual(self.received[0][1], "filesystem")
        self.assertEqual(self.received[0][0]["fps"], 120)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_native_sender_falls_back_when_the_socket_path_is_missing(self):
        os.unlink(self.path)
        self.run_sender("stream")
        self.wait(lambda: len(self.received) == 1)
        self.assertEqual(self.received[0][1], "abstract-stream")
        self.assertEqual(self.received[0][0]["fps"], 120)

    def test_sender_authenticates_the_receiver_before_sending_telemetry(self):
        os.unlink(self.path)
        self.run_sender("deny")
        time.sleep(0.05)
        self.assertEqual(self.received, [])

    def test_receiver_checks_kernel_user_credentials(self):
        self.server.owner_uid = os.getuid() + 1
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(abstract_socket_name(self.path))
            client.sendall(b'{"fps":120}\n')
            try:
                self.assertEqual(client.recv(1), b"")
            except ConnectionResetError:
                pass
        self.assertEqual(self.received, [])

    def test_stream_handles_fragmented_and_multiple_samples(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(self.server.name)
            client.sendall(b'{"fps":')
            client.sendall(b'90}\n{"fps":120}\n')
            self.wait(lambda: len(self.received) == 2)
        self.assertEqual([sample[0]["fps"] for sample in self.received], [90, 120])

    def test_second_receiver_cannot_steal_either_endpoint(self):
        second = FpsProbeServer(self.path, lambda *_args: self.fail("socket stolen"))
        second.start()
        self.addCleanup(second.close)
        time.sleep(0.05)
        self.assertFalse(second.filesystem_bound or second.abstract_bound)
        self.run_sender("file")
        self.wait(lambda: len(self.received) == 1)

    def test_unavailable_receiver_does_not_leak_native_socket_descriptors(self):
        self.server.close()
        result = self.run_sender("missing")
        self.assertIn("descriptor_growth=1", result.stdout)

    def test_sender_survives_backend_restart(self):
        os.unlink(self.path)
        process = subprocess.Popen([str(self.sender), self.path, "persistent"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=dict(os.environ, OPEN_TROFEO_STATE_HOME=self.temp.name))
        try:
            self.wait(lambda: len(self.received) == 1)
            self.server.close()
            replacement = FpsProbeServer(self.path, self.server.on_sample)
            replacement.start()
            self.addCleanup(replacement.close)
            self.wait(lambda: replacement.abstract_bound)
            os.unlink(self.path)
            process.stdin.write(b"x")
            process.stdin.flush()
            self.wait(lambda: len(self.received) == 2)
            process.stdin.write(b"x")
            process.stdin.flush()
            self.assertEqual(process.wait(timeout=3), 0)
            self.wait(lambda: len(self.received) == 3)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def test_slow_receiver_does_not_block_the_native_present_thread(self):
        self.server.close()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(self.server.name)
            listener.listen(1)
            self.run_sender("stalled")

    def test_native_container_samples_reach_stats_and_csv(self):
        from stats_sources import StatsProvider
        from unittest.mock import patch
        self.server.close()
        with patch.dict(os.environ, {"OPEN_TROFEO_FPS_SOCKET": self.path,
                                    "XDG_STATE_HOME": self.temp.name, "OPEN_TROFEO_AUDIO_EQ": "0"}):
            provider = StatsProvider(enable_fps_probe=True)
        try:
            self.wait(lambda: provider._fps_probe_server.abstract_bound)
            command = ["bwrap", "--unshare-user", "--ro-bind", "/", "/", "--tmpfs", str(Path(self.path).parent),
                       "--die-with-parent", "--", str(self.sender), self.path, "stream"]
            self.run_sender("stream", command)
            self.wait(lambda: provider.fps_probe_status()["active"] == "yes")
            status = provider.fps_probe_status()
            self.assertEqual(status["transport"], "abstract-stream")
            self.assertEqual(status["session"]["game_fps"], "120")
            self.wait(lambda: bool(provider._fps_log_path) and Path(provider._fps_log_path).is_file())
            self.assertTrue(Path(provider._fps_log_path).is_relative_to(self.temp.name))
            provider.close_fps_logging()
            with Path(provider._fps_log_path).open() as saved:
                rows = list(csv.DictReader(saved))
            self.assertEqual(float(rows[-1]["fps"]), 120)
            self.assertAlmostEqual(float(rows[-1]["frametime_ms"]), 1000 / 120, places=2)
        finally:
            provider._fps_probe_server.close()
            provider.close_fps_logging()

    @unittest.skipUnless(shutil.which("bwrap"), "bubblewrap is needed for a mount-namespace test")
    def test_real_mount_namespace_hides_the_file_but_fps_still_arrives(self):
        command = ["bwrap", "--unshare-user", "--ro-bind", "/", "/", "--tmpfs", str(Path(self.path).parent),
                   "--die-with-parent", "--", str(self.sender), self.path, "stream"]
        self.run_sender("stream", command)
        self.wait(lambda: len(self.received) == 1)
        self.assertEqual(self.received[0][1], "abstract-stream")
        self.assertTrue(Path(self.path).is_socket(), "the host socket must stay intact")


if __name__ == "__main__":
    unittest.main()
