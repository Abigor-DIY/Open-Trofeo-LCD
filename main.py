#!/usr/bin/env python3
"""
Open Trofeo LCD — Unified Launcher
==================================
Ten skrypt automatycznie uruchamia backend i GUI, dbając o ich współpracę.
"""

import argparse
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

def is_backend_running() -> bool:
    """Sprawdza, czy backend odpowiada na /health."""
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, ConnectionRefusedError):
        return False
    except Exception:
        return False

def get_venv_python(venv_name: str) -> str:
    """Zwraca ścieżkę do interpretera python w danym venv."""
    path = WORKDIR / venv_name / "bin" / "python"
    if path.exists():
        return str(path)
    return sys.executable

def start_backend():
    """Uruchamia backend w tle, jeśli nie działa. Zwraca proces lub None."""
    if is_backend_running():
        print("[-] Backend już działa (prawdopodobnie jako usługa systemowa).")
        return None

    print("[+] Uruchamiam backend...")
    log_dir = Path.home() / ".local/state/open-trofeo-lcd"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"
    
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
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/v1/stop", method="POST")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                print("[+] Backend zatrzymany przez API.")
                return
    except Exception:
        pass

    if proc:
        print("[-] API nie odpowiedziało, używam terminate().")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

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
    
    args, _ = parser.parse_known_args()
    
    if args.cli:
        print("[!] Tryb CLI: uruchamianie trofeo_lcd.py...")
        subprocess.run([sys.executable, str(WORKDIR / "trofeo_lcd.py")] + sys.argv[2:])
        return

    backend_proc = None
    if not args.gui_only:
        backend_proc = start_backend()

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
