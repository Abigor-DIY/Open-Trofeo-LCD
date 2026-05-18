#!/usr/bin/env python3
"""
Open Trofeo LCD — Unified Launcher
==================================
Ten skrypt automatycznie uruchamia backend i GUI, dbając o ich współpracę.
"""

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from collections import deque

WORKDIR = Path(__file__).parent.resolve()
BACKEND_PORT = 18777
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
STATE_DIR = Path.home() / ".local/state/open-trofeo-lcd"
MANAGED_BACKEND_PID = STATE_DIR / "launcher-backend.pid"
INSTANCE_LOCK = STATE_DIR / "launcher.lock"
BACKEND_ENV_FILE = WORKDIR / ".trofeo-backend.env"
BACKEND_ENV_EXAMPLE = WORKDIR / ".trofeo-backend.env.example"

BACKEND_ENV_DEFAULTS = {
    "HOST": "127.0.0.1",
    "PORT": "18777",
    "PCAP_FILE": "dzis.pcapng",
    "FRAME_INDEX": "0",
    "ACK_TIMEOUT_MS": "500",
    "INTER_PACKET_DELAY": "0.01",
    "FRAME_DELAY": "0.02",
    "CONNECT_RETRIES": "20",
    "CONNECT_RETRY_DELAY": "0.5",
    "THEMES_FILE": ".trofeo-themes.json",
    "PLAYLIST_FILE": ".trofeo-playlist.json",
    "AUTOSTART": "0",
}

def is_backend_running() -> bool:
    """Sprawdza, czy backend odpowiada na /health."""
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, ConnectionRefusedError):
        return False
    except Exception:
        return False

def backend_workdir() -> str:
    """Returns backend-reported workdir, or an empty string if status is unavailable."""
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/v1/status", timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cfg = data.get("config", {}) if isinstance(data, dict) else {}
        return str(cfg.get("workdir", "")).strip() if isinstance(cfg, dict) else ""
    except Exception:
        return ""

def backend_matches_workdir() -> bool:
    reported = backend_workdir()
    if not reported:
        return False
    try:
        return Path(reported).resolve() == WORKDIR
    except Exception:
        return reported == str(WORKDIR)

def _read_managed_backend_pid() -> int | None:
    try:
        raw = MANAGED_BACKEND_PID.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except Exception:
        return None

def _write_managed_backend_pid(pid: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MANAGED_BACKEND_PID.write_text(f"{pid}\n", encoding="utf-8")

def _clear_managed_backend_pid() -> None:
    try:
        MANAGED_BACKEND_PID.unlink(missing_ok=True)
    except Exception:
        pass

def _acquire_instance_lock():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_handle = open(INSTANCE_LOCK, "a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_handle.seek(0)
        raw_pid = lock_handle.read().strip()
        try:
            pid = int(raw_pid) if raw_pid else None
        except Exception:
            pid = None
        if pid:
            cmdline = _process_cmdline(pid)
            print(f"[-] Open Trofeo LCD już działa albo launcher trzyma lock (PID: {pid}).")
            if cmdline:
                print(f"[-] Proces: {cmdline}")
        else:
            print("[-] Open Trofeo LCD już działa albo launcher trzyma lock bez zapisanego PID.")
        print("[-] Jeśli użyłeś nuke i to nadal występuje, sprawdź: scripts/trofeo_status.sh albo scripts/trofeo_nuke.sh")
        lock_handle.close()
        return None
    lock_handle.seek(0)
    lock_handle.truncate()
    lock_handle.write(f"{os.getpid()}\n")
    lock_handle.flush()
    return lock_handle

def _pid_is_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def _process_cmdline(pid: int | None) -> str:
    if not pid:
        return ""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return raw.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
    except Exception:
        return ""

def _read_backend_env() -> dict[str, str]:
    values = dict(BACKEND_ENV_DEFAULTS)
    if BACKEND_ENV_FILE.exists():
        for line in BACKEND_ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values

def _ensure_backend_env() -> None:
    if BACKEND_ENV_FILE.exists():
        return
    if BACKEND_ENV_EXAMPLE.exists():
        BACKEND_ENV_FILE.write_text(BACKEND_ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[+] Utworzono domyślny plik konfiguracji: {BACKEND_ENV_FILE}")

def _env_bool(value: str | None, default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _runtime_check() -> list[tuple[str, bool, str]]:
    checks = [
        ("python3", bool(shutil.which("python3")), "wymagany do uruchomienia launchera/backendu"),
        ("playerctl", bool(shutil.which("playerctl")), "Now Playing przez MPRIS"),
        ("ffmpeg", bool(shutil.which("ffmpeg")), "import wideo MP4 i klatki video dla Now Playing"),
        ("cava", bool(shutil.which("cava")), "realny EQ/audio spectrum"),
        ("trcc", bool(shutil.which("trcc") or (WORKDIR / ".venv-trcc/bin/trcc").exists()), "szybsza komunikacja z LCD przez TRCC"),
    ]
    gui_python = Path(get_venv_python(".venv-gui"))
    trcc_python = Path(get_venv_python(".venv-trcc"))
    checks.append((".venv-gui", gui_python.exists(), "venv GUI/PySide6"))
    checks.append((".venv-trcc", trcc_python.exists(), "venv backend/TRCC"))
    return checks

def print_runtime_status() -> None:
    env = _read_backend_env()
    print("Open Trofeo LCD runtime")
    print(f"workdir: {WORKDIR}")
    print(f"backend env: {BACKEND_ENV_FILE} ({'OK' if BACKEND_ENV_FILE.exists() else 'missing, will be created from example'})")
    print(f"backend url: http://{env.get('HOST', '127.0.0.1')}:{env.get('PORT', '18777')}")
    print(f"backend running: {'yes' if is_backend_running() else 'no'}")
    reported = backend_workdir()
    if reported:
        print(f"backend workdir: {reported}")
    pid = _read_managed_backend_pid()
    if pid:
        print(f"managed backend pid: {pid} ({'alive' if _pid_is_alive(pid) else 'stale'})")
    print("dependencies:")
    for name, ok, note in _runtime_check():
        print(f"  {'OK' if ok else 'MISS'} {name}: {note}")

def _backend_args_from_env(env: dict[str, str]) -> list[str]:
    host = env.get("HOST", "127.0.0.1")
    port = env.get("PORT", "18777")
    args = [
        "--workdir", str(WORKDIR),
        "--host", host,
        "--port", port,
        "--pcap", env.get("PCAP_FILE", "dzis.pcapng"),
        "--frame-index", env.get("FRAME_INDEX", "0"),
        "--ack-timeout-ms", env.get("ACK_TIMEOUT_MS", "500"),
        "--inter-packet-delay", env.get("INTER_PACKET_DELAY", "0.01"),
        "--frame-delay", env.get("FRAME_DELAY", "0.02"),
        "--connect-retries", env.get("CONNECT_RETRIES", "20"),
        "--connect-retry-delay", env.get("CONNECT_RETRY_DELAY", "0.5"),
        "--themes-file", env.get("THEMES_FILE", ".trofeo-themes.json"),
        "--playlist-file", env.get("PLAYLIST_FILE", ".trofeo-playlist.json"),
    ]
    if _env_bool(env.get("AUTOSTART"), default=False) or _env_bool(os.environ.get("OPEN_TROFEO_BACKEND_AUTOSTART"), default=False):
        args.append("--autostart")
    display_backend = env.get("DISPLAY_BACKEND", "").strip()
    if display_backend:
        args.extend(["--display-backend", display_backend])
    trcc_bin = env.get("TRCC_BIN", "").strip()
    if trcc_bin:
        args.extend(["--trcc-bin", trcc_bin])
    return args

def _shutdown_backend_api(timeout: float = 5.0) -> bool:
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/v1/shutdown", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def get_venv_python(venv_name: str) -> str:
    """Zwraca ścieżkę do interpretera python w danym venv."""
    path = WORKDIR / venv_name / "bin" / "python"
    if path.exists():
        return str(path)
    return sys.executable

def start_backend(force_replace: bool = False):
    """Uruchamia backend w tle, jeśli nie działa. Zwraca proces lub None."""
    _ensure_backend_env()
    backend_env = _read_backend_env()
    managed_pid = _read_managed_backend_pid()
    if is_backend_running():
        if force_replace:
            print("[+] Wymuszony restart istniejącego backendu.")
            stop_backend()
            time.sleep(0.8)
            if is_backend_running():
                print("[-] Nie udało się wyłączyć istniejącego backendu, pozostawiam aktywny proces.")
                return None
        elif _pid_is_alive(managed_pid):
            print(f"[-] Wykryto stary backend launchera (PID: {managed_pid}), restartuję go.")
            stop_backend()
            time.sleep(0.6)
            if is_backend_running():
                print("[-] Nie udało się wyłączyć starego backendu launchera.")
                return None
        elif not backend_matches_workdir():
            reported = backend_workdir() or "nieznany"
            print(f"[-] Backend działa z innego katalogu: {reported}")
            print("[+] Zamykam obcy backend i uruchamiam lokalny z workspace.")
            stop_backend()
            time.sleep(0.8)
            if is_backend_running() and not backend_matches_workdir():
                print("[-] Nie udało się wyłączyć obcego backendu. Zamknij Flatpaka/usługę i uruchom ponownie.")
                return None
        else:
            print("[-] Backend już działa dla tego workspace.")
            return None

    print("[+] Uruchamiam backend...")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_file = STATE_DIR / "backend.log"
    
    python_bin = get_venv_python(".venv-trcc")
    env = os.environ.copy()
    env.update({key: str(value) for key, value in backend_env.items()})
    env.setdefault("PYTHON_BIN", python_bin)
    backend_args = _backend_args_from_env(backend_env)
    
    # Używamy start_new_session=True, aby backend nie zginął razem z launcherem 
    # przedwcześnie, ale będziemy go kontrolować.
    proc = subprocess.Popen(
        [python_bin, str(WORKDIR / "trofeo_backend.py")] + backend_args,
        stdout=open(log_file, "a"),
        stderr=subprocess.STDOUT,
        cwd=WORKDIR,
        env=env,
        start_new_session=True 
    )
    _write_managed_backend_pid(proc.pid)
    
    # Czekaj na gotowość
    for _ in range(20):
        if is_backend_running():
            print(f"[+] Backend gotowy (PID: {proc.pid})")
            return proc
        time.sleep(0.5)
    
    print("[-] OSTRZEŻENIE: Backend startuje powoli. Sprawdź logi w ~/.local/state/open-trofeo-lcd/backend.log")
    return proc

def stop_backend(proc=None):
    """Zatrzymuje backend wysyłając żądanie API, a potem kill jeśli trzeba."""
    print("[+] Zamykanie backendu...")
    managed_pid = _read_managed_backend_pid()

    if is_backend_running() and _shutdown_backend_api(timeout=5.0):
        for _ in range(30):
            if not is_backend_running():
                _clear_managed_backend_pid()
                print("[+] Backend zamknięty przez API.")
                return
            time.sleep(0.2)

    if proc:
        print("[-] API nie odpowiedziało, używam terminate() na procesie launchera.")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        _clear_managed_backend_pid()
        return

    if _pid_is_alive(managed_pid):
        print(f"[-] API nie odpowiedziało, kończę zapisany backend PID={managed_pid}.")
        try:
            os.kill(managed_pid, 15)
        except Exception:
            pass
        for _ in range(20):
            if not _pid_is_alive(managed_pid):
                _clear_managed_backend_pid()
                return
            time.sleep(0.2)
        try:
            os.kill(managed_pid, 9)
        except Exception:
            pass
        _clear_managed_backend_pid()

def run_gui():
    """Uruchamia GUI i czeka na jego zakończenie."""
    print("[+] Uruchamiam GUI...")
    python_bin = get_venv_python(".venv-gui")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    gui_log = STATE_DIR / "gui.log"
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    
    try:
        # Ten proces będzie trwał dopóki użytkownik nie wybierze 'Quit' z tray'a
        with open(gui_log, "a", encoding="utf-8") as log:
            log.write(f"\n[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] start GUI\n")
            log.flush()
            subprocess.run(
                [python_bin, str(WORKDIR / "trofeo_gui.py"), "--url", BACKEND_URL],
                cwd=WORKDIR,
                check=True,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
    except subprocess.CalledProcessError as e:
        print(f"[-] GUI zakończone błędem: {e}")
        print(f"[-] Log GUI: {gui_log}")
        try:
            with open(gui_log, "r", encoding="utf-8", errors="replace") as log:
                tail = deque(log, maxlen=80)
            print("[-] Ostatnie linie GUI:")
            print("".join(tail).rstrip())
        except Exception:
            pass
    except KeyboardInterrupt:
        pass

def main():
    parser = argparse.ArgumentParser(description="Open Trofeo LCD - Launcher")
    parser.add_argument("--cli", action="store_true", help="Uruchom narzędzie diagnostyczne CLI")
    parser.add_argument("--backend-only", action="store_true", help="Uruchom tylko backend")
    parser.add_argument("--gui-only", action="store_true", help="Uruchom tylko GUI")
    parser.add_argument("--replace-existing-backend", action="store_true", help="Wymuś restart istniejącego backendu")
    parser.add_argument("--status", action="store_true", help="Pokaż status runtime i zależności")
    parser.add_argument("--check-runtime", action="store_true", help="Sprawdź zależności runtime i zakończ")
    
    args, _ = parser.parse_known_args()

    if args.status or args.check_runtime:
        print_runtime_status()
        if args.check_runtime and any(not ok for _name, ok, _note in _runtime_check()):
            raise SystemExit(1)
        return
    
    if args.cli:
        print("[!] Tryb CLI: uruchamianie trofeo_lcd.py...")
        subprocess.run([sys.executable, str(WORKDIR / "trofeo_lcd.py")] + sys.argv[2:])
        return

    instance_lock = _acquire_instance_lock()
    if instance_lock is None:
        return

    backend_proc = None
    try:
        if not args.gui_only:
            backend_proc = start_backend(force_replace=bool(args.replace_existing_backend))

        if not args.backend_only:
            run_gui()
            # Wykonuje się dopiero gdy GUI faktycznie kończy proces (np. Quit w tray)
            if backend_proc:
                stop_backend(backend_proc)
            else:
                # Nawet jeśli nie my go odpaliliśmy, możemy spróbować go zamknąć
                # jeśli użytkownik tego oczekuje przy pełnym wyjściu z aplikacji.
                # Ale bezpieczniej zatrzymać tylko "nasz" proces.
                print("[-] Backend nie był uruchomiony przez ten launcher, pozostawiam go w tle.")
    finally:
        try:
            fcntl.flock(instance_lock.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            instance_lock.close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Przerwano przez użytkownika.")
