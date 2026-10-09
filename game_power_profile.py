"""Non-blocking session-scoped power-profiles-daemon hold."""
import shutil
import sys
import time
from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget


class GamePowerProfile(QObject):
    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = self.active = self.failed = self.ready = False
        self.process = None
        self.last_seen = self.started_at = 0.0
        self.inactive_since = None
        self.output = ""
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.failed = False
        if not self.enabled:
            self.release()
        self.changed.emit("CPU: oczekiwanie na grę" if enabled else "CPU: automatyczny performance wyłączony")
        self.tick()

    def observe(self, status):
        config = status.get("config", {})
        game = status.get("game", config.get("game") if isinstance(config, dict) else None)
        if not isinstance(game, dict) or "game_active" not in game:
            return
        self.last_seen = time.monotonic()
        self.active = str(game["game_active"]).lower().strip() in {"yes", "true", "1", "active"}
        if self.active:
            self.inactive_since = None
        elif self.inactive_since is None:
            self.inactive_since = self.last_seen
        self.tick()

    def tick(self):
        now = time.monotonic()
        if self.process and not self.ready and now - self.started_at > 10:
            self.failed = True
            self.release()
            self.changed.emit("CPU: timeout usługi profili; wyłącz i włącz opcję, aby ponowić")
            return
        stale = not self.last_seen or now - self.last_seen > 30
        ended = self.inactive_since is not None and now - self.inactive_since >= 12
        if stale or ended or not self.enabled:
            if self.process:
                self.release()
                self.changed.emit("CPU: zwolniono profil performance")
            if ended:
                self.failed = False
            return
        if self.active and not self.process and not self.failed:
            self.start()

    def command(self):
        executable = shutil.which("powerprofilesctl")
        if not executable:
            raise RuntimeError("brak powerprofilesctl / power-profiles-daemon")
        # Child starts after HoldProfile succeeds. EOF releases on GUI crash too.
        return executable, ["launch", "--profile", "performance", "--reason",
                            "Open Trofeo LCD: detected game", "--appid",
                            "io.github.abigordiy.open-trofeo-lcd", sys.executable,
                            "-u", "-c", "import sys; print('TROFEO_HOLD_READY'); sys.stdin.read()"]

    def start(self):
        try:
            executable, arguments = self.command()
        except RuntimeError as exc:
            self.failed = True
            self.changed.emit(f"CPU: {exc}")
            return
        process = QProcess(self)
        self.process = process
        self.started_at = time.monotonic()
        self.ready = False
        self.output = ""
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: self.read_output(process))
        process.finished.connect(lambda *_: self.finished(process))
        process.errorOccurred.connect(lambda *_: self.process_error(process))
        self.changed.emit("CPU: żądanie profilu performance…")
        process.start(executable, arguments)

    def read_output(self, process):
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if process is self.process:
            self.output = (self.output + data)[-2000:]
            if "TROFEO_HOLD_READY" in self.output:
                self.ready = True
                self.changed.emit("CPU: żądanie performance aktywne (obowiązują ograniczenia systemu)")

    def process_error(self, process):
        if process is self.process and process.state() == QProcess.NotRunning:
            self.output = process.errorString()
            self.finished(process)

    def finished(self, process):
        if process is self.process:
            self.read_output(process)
            detail = self.output.replace("TROFEO_HOLD_READY", "").strip()[-400:]
            self.process = None
            self.failed = True  # Avoid repeated authorization/error loops.
            self.changed.emit("CPU: nie udało się utrzymać performance. " + detail)
        process.deleteLater()

    def release(self):
        process, self.process = self.process, None
        self.ready = False
        if process:
            process.closeWriteChannel()
            QTimer.singleShot(2000, lambda: self.kill_if_running(process))

    @staticmethod
    def kill_if_running(process):
        try:
            if process.state() != QProcess.NotRunning:
                process.kill()
        except RuntimeError:
            pass  # Already deleted on finished.

    def shutdown(self):
        self.timer.stop()
        process = self.process
        self.release()
        if process and not process.waitForFinished(1000):
            process.kill()
            process.waitForFinished(500)


class GamePowerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = GamePowerProfile(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox("Profil CPU performance po wykryciu gry", self)
        self.checkbox.setToolTip("Tymczasowe żądanie systemowego profilu. Zwolnienie po grze lub wyjściu z aplikacji. Nie zmienia opcji Steam.")
        self.status = QLabel("CPU: automatyczny performance wyłączony", self)
        self.status.setWordWrap(True)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.status)
        self.controller.changed.connect(self.status.setText)
        self.checkbox.toggled.connect(self.controller.set_enabled)
