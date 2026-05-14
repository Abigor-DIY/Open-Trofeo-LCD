#!/usr/bin/env python3
"""
Open Trofeo LCD — Unified Launcher
==================================
Ten skrypt automatycznie uruchamia backend i GUI, dbając o ich współpracę.
"""

import argparse
import fcntl
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

WORKDIR = Path(__file__).parent.resolve()
BACKEND_PORT = 18777
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
STATE_DIR = Path.home() / ".local/state/open-trofeo-lcd"
MANAGED_BACKEND_PID = STATE_DIR / "launcher-backend.pid"
INSTANCE_LOCK = STATE_DIR / "launcher.lock"

def is_backend_running() -> bool:
    """Sprawdza, czy backend odpowiada na /health."""
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, ConnectionRefusedError):
        return False
    except Exception:
        return False

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
    lock_handle = open(INSTANCE_LOCK, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[-] Open Trofeo LCD już działa. Zamknij istniejące okno przed uruchomieniem kolejnego.")
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
        else:
            print("[-] Backend już działa (prawdopodobnie jako usługa systemowa).")
            return None

    print("[+] Uruchamiam backend...")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_file = STATE_DIR / "backend.log"
    
    python_bin = get_venv_python(".venv-trcc")
    
    env_args = ["--autostart"]
    
    # Używamy start_new_session=True, aby backend nie zginął razem z launcherem 
    # przedwcześnie, ale będziemy go kontrolować.
    proc = subprocess.Popen(
        [python_bin, str(WORKDIR / "trofeo_backend.py")] + env_args,
        stdout=open(log_file, "a"),
        stderr=subprocess.STDOUT,
        cwd=WORKDIR,
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
    
    try:
        # Ten proces będzie trwał dopóki użytkownik nie wybierze 'Quit' z tray'a
        subprocess.run(
            [python_bin, str(WORKDIR / "trofeo_gui.py"), "--url", BACKEND_URL],
            cwd=WORKDIR,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[-] GUI zakończone błędem: {e}")
    except KeyboardInterrupt:
        pass

def main():
    parser = argparse.ArgumentParser(description="Open Trofeo LCD - Launcher")
    parser.add_argument("--cli", action="store_true", help="Uruchom narzędzie diagnostyczne CLI")
    parser.add_argument("--backend-only", action="store_true", help="Uruchom tylko backend")
    parser.add_argument("--gui-only", action="store_true", help="Uruchom tylko GUI")
    parser.add_argument("--replace-existing-backend", action="store_true", help="Wymuś restart istniejącego backendu")
    
    args, _ = parser.parse_known_args()
    
    if args.cli:
        print("[!] Tryb CLI: uruchamianie trofeo_lcd.py...")
        subprocess.run([sys.executable, str(WORKDIR / "trofeo_lcd.py")] + sys.argv[2:])
        return

    instance_lock = _acquire_instance_lock()
    if instance_lock is None:
        return

    backend_proc = None
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

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Przerwano przez użytkownika.")
