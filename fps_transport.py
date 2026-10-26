"""Local FPS receivers, including an authenticated Steam-container fallback."""
from __future__ import annotations

import errno
import fcntl
import os
import selectors
import socket
import struct
import threading


def abstract_socket_name(path: str) -> str:
    """Match the native probe's FNV-1a name without depending on mount paths."""
    value = 14695981039346656037
    for byte in os.fsencode(path):
        value = ((value ^ byte) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"\0open-trofeo-fps-v1-{value:016x}"


def socket_is_live(path: str) -> bool:
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as probe:
        try:
            probe.settimeout(0.2)
            probe.connect(path)
            probe.send(b"")
            return True
        except OSError:
            return False


class FpsProbeServer:
    """Keep the legacy datagram path and receive streams across mount namespaces.

    The abstract stream is Linux-only and authenticates the peer with kernel
    credentials. It shares no filesystem directories and opens no IP port.
    """
    def __init__(self, path: str, on_sample):
        self.path = path
        self.on_sample = on_sample
        self.name = abstract_socket_name(path)
        self.owner_uid = os.getuid()
        self.filesystem_bound = False
        self.abstract_bound = False
        self.error = ""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="trofeo-fps-probe", daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self):
        selector = selectors.DefaultSelector()
        clients = {}
        inode = None
        lock_fd = None

        def remove(client):
            clients.pop(client, None)
            try:
                selector.unregister(client)
            except KeyError:
                pass
            client.close()

        try:
            os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
            lock_fd = os.open(self.path + ".lock", os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            # A second StatsProvider must never steal either receiver from
            # the backend that already owns the legacy socket.
            if os.path.exists(self.path) and socket_is_live(self.path):
                return
            legacy = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            try:
                os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
                try:
                    os.unlink(self.path)
                except FileNotFoundError:
                    pass
                legacy.bind(self.path)
                inode = os.stat(self.path).st_ino
                os.chmod(self.path, 0o600)
                legacy.setblocking(False)
                selector.register(legacy, selectors.EVENT_READ, "filesystem")
                self.filesystem_bound = True
            except OSError as exc:
                legacy.close()
                self.error = f"filesystem: {exc}"
                if exc.errno == errno.EADDRINUSE:
                    return

            if hasattr(socket, "SO_PEERCRED"):
                listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    listener.bind(self.name)
                    listener.listen(16)
                    listener.setblocking(False)
                    selector.register(listener, selectors.EVENT_READ, "listener")
                    self.abstract_bound = True
                except OSError as exc:
                    listener.close()
                    self.error = f"abstract-stream: {exc}"

            while selector.get_map() and not self._stop.is_set():
                for key, _events in selector.select(timeout=0.5):
                    connection = key.fileobj
                    if key.data == "filesystem":
                        try:
                            raw, _address = connection.recvfrom(4096)
                        except BlockingIOError:
                            continue
                        self.on_sample(raw, "filesystem")
                    elif key.data == "listener":
                        try:
                            client, _address = connection.accept()
                        except BlockingIOError:
                            continue
                        try:
                            _pid, uid, _gid = struct.unpack("iII", client.getsockopt(
                                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("iII")))
                            if uid != self.owner_uid or len(clients) >= 16:
                                client.close()
                                continue
                            client.setblocking(False)
                            clients[client] = bytearray()
                            selector.register(client, selectors.EVENT_READ, "stream")
                        except OSError:
                            client.close()
                    else:
                        try:
                            raw = connection.recv(4096)
                        except BlockingIOError:
                            continue
                        except OSError:
                            raw = b""
                        if not raw:
                            remove(connection)
                            continue
                        buffer = clients[connection]
                        buffer.extend(raw)
                        while b"\n" in buffer:
                            line, _, rest = buffer.partition(b"\n")
                            buffer[:] = rest
                            if len(line) <= 4096:
                                self.on_sample(bytes(line), "abstract-stream")
                        if len(buffer) > 4096:
                            remove(connection)
        except OSError as exc:
            self.error = str(exc)
        finally:
            for key in list(selector.get_map().values()):
                key.fileobj.close()
            selector.close()
            self.filesystem_bound = False
            self.abstract_bound = False
            if inode is not None:
                try:
                    if os.stat(self.path).st_ino == inode:
                        os.unlink(self.path)
                except OSError:
                    pass
            if lock_fd is not None:
                os.close(lock_fd)
