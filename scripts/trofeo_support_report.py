#!/usr/bin/env python3
"""Collect bounded FPS/display diagnostics without changing the running app."""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=4)
        return (result.stdout or result.stderr).strip()[:4000]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return type(exc).__name__


def file_state(path):
    path = Path(path)
    try:
        item = path.stat()
        return {"path": str(path), "exists": True, "socket": stat.S_ISSOCK(item.st_mode),
                "mode": oct(stat.S_IMODE(item.st_mode)), "uid": item.st_uid}
    except OSError as exc:
        return {"path": str(path), "exists": False, "error": type(exc).__name__}


def manifest_state(path):
    result = file_state(path)
    if not result["exists"]:
        return result
    try:
        if Path(path).stat().st_size > 65536:
            raise ValueError("oversized manifest")
        layer = json.loads(Path(path).read_text())["layer"]
        result["layer"] = {k: layer.get(k) for k in ("name", "api_version", "enable_environment", "disable_environment")}
        library = Path(layer["library_path"])
        if not library.is_absolute():
            library = Path(path).parent / library
        result["library"] = file_state(library)
        if library.is_file():
            with library.open("rb") as handle:
                header = handle.read(20)
            result["library"]["elf_bits"] = {1: 32, 2: 64}.get(header[4]) if header[:4] == b"\x7fELF" else None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["parse_error"] = str(exc)
    return result


def backend_state(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("Backend URL must be a local HTTP origin")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url.rstrip("/") + "/v1/status", timeout=4) as response:
            state = json.loads(response.read(2_000_000))
        config = state.get("config", {})
        probe = config.get("fps_probe", {})
        game = config.get("game", {})
        # Never export the full status: weather configuration has coordinates.
        return {**{k: state.get(k) for k in ("busy", "running", "mode", "last_exit_code")},
                "display_backend": config.get("display_backend"), "trcc_bin": config.get("trcc_bin"),
                "fps_probe": {k: probe.get(k) for k in ("active", "age_ms", "source", "socket_path", "log_error", "log_dropped_samples")},
                "game": {k: game.get(k) for k in ("game_name", "game_launcher", "game_fps", "game_frametime_ms", "game_fps_source")}}
    except (OSError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


FPS_ENV = {"OPEN_TROFEO_FPS_LAYER", "OPEN_TROFEO_FPS_SOCKET", "OPEN_TROFEO_GAME_NAME",
           "OPEN_TROFEO_GAME_LAUNCHER", "DISABLE_OPEN_TROFEO_FPS_LAYER", "XDG_RUNTIME_DIR",
           "VK_LAYER_PATH", "VK_ADD_IMPLICIT_LAYER_PATH", "VK_IMPLICIT_LAYER_PATH",
           "VK_LOADER_LAYERS_ENABLE", "VK_LOADER_LAYERS_DISABLE", "FLATPAK_ID", "PROTON_ENABLE_WAYLAND",
           "STEAM_COMPAT_TOOL_PATHS", "SteamAppId"}


def game_processes(game, default_socket, proc_root=Path("/proc")):
    found = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            name = (entry / "comm").read_text().strip()
            if game.lower() not in name.lower():
                continue
            raw = (entry / "environ").read_bytes()[:2_000_000]
            env = dict(item.decode(errors="replace").split("=", 1) for item in raw.split(b"\0") if b"=" in item)
            item = {"pid": int(entry.name), "name": name, "env": {k: v[:500] for k, v in env.items() if k in FPS_ENV}}
            try:
                with (entry / "maps").open(errors="replace") as handle:
                    maps = handle.read(4_000_000).lower()
                item.update(probe_library_loaded="libopen_trofeo_fps_probe" in maps, mangohud_loaded="mangohud" in maps)
            except OSError as exc:
                item["maps_error"] = type(exc).__name__
            socket_path = env.get("OPEN_TROFEO_FPS_SOCKET") or str(Path(env.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "open-trofeo-lcd/fps.sock")
            item["socket_in_game_namespace"] = file_state(entry / "root" / socket_path.lstrip("/"))
            if socket_path != default_socket:
                item["backend_socket_in_game_namespace"] = file_state(entry / "root" / default_socket.lstrip("/"))
            found.append(item)
        except OSError:
            continue
        if len(found) >= 8:
            break
    return found


def log_excerpt(path, pattern=None):
    try:
        with Path(path).open("rb") as handle:
            handle.seek(max(0, Path(path).stat().st_size - 100_000))
            lines = handle.read(100_000).decode(errors="replace").splitlines()
        if pattern:
            lines = [line for line in lines if re.search(pattern, line, re.I)]
        return lines[-60:]
    except OSError as exc:
        return [type(exc).__name__]


def trcc_details(backend, home):
    launcher = backend.get("trcc_bin") or shutil.which("trcc")
    if launcher and not Path(launcher).is_file():
        launcher = shutil.which("trcc")
    result = {"launcher": launcher}
    interpreters = [sys.executable]
    if launcher:
        try:
            launcher = str(Path(launcher).resolve())
            result["launcher"] = launcher
            with Path(launcher).open() as handle:
                line = handle.readline(512).strip()
            if line.startswith("#!"):
                parts = shlex.split(line[2:])
                if parts and "python" in Path(parts[0]).name and Path(parts[0]).is_absolute():
                    interpreters.append(parts[0])
            adjacent = Path(launcher).parent / "python"
            if adjacent.is_file():
                interpreters.append(str(adjacent))
        except (OSError, UnicodeError, ValueError):
            pass
    result["versions"] = [{"python": interpreter, "trcc_linux": command([interpreter, "-c",
                           "import importlib.metadata as m; print(m.version('trcc-linux'))"])}
                          for interpreter in dict.fromkeys(interpreters)]
    result["saved_display_settings"] = {}
    for root in (home / ".trcc", Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "trcc"):
        for name in ("trcc.json", "trcc-next.json", "config.json"):
            path = root / name
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                devices = json.loads(path.read_text()).get("devices", {})
                selected = {key: {k: value.get(k) for k in ("orientation", "rotation", "brightness") if k in value}
                            for key, value in devices.items() if key.startswith("0416:5408") and isinstance(value, dict)}
                if selected:
                    result["saved_display_settings"][str(path)] = selected
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    return result


def redact(value, home, runtime):
    text = json.dumps(value, indent=2, ensure_ascii=False)
    text = text.replace(str(home), "$HOME").replace(runtime, "$RUNTIME")
    return re.sub(r'/run/user/\d+', '$RUNTIME', text)


def collect(url, game):
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    state = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local/state")))
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    flatpak = home / ".var/app/com.valvesoftware.Steam"
    backend = backend_state(url)
    socket_path = backend.get("fps_probe", {}).get("socket_path") or str(Path(runtime) / "open-trofeo-lcd/fps.sock")
    report = {"collected_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "package": command(["dpkg-query", "-W", "open-trofeo-lcd"]),
              "session": os.environ.get("XDG_SESSION_TYPE", "unknown"),
              "backend": backend, "fps_socket_on_host": file_state(socket_path),
              "manifests": [manifest_state(p) for p in (data / "vulkan/implicit_layer.d/VkLayer_OPEN_TROFEO_fps.json",
                            flatpak / ".local/share/vulkan/implicit_layer.d/VkLayer_OPEN_TROFEO_fps.json")],
              "game_processes": game_processes(game, socket_path),
              "trcc": trcc_details(backend, home)}
    if shutil.which("flatpak"):
        report["steam_flatpak_version"] = command(["flatpak", "info", "--show-version", "com.valvesoftware.Steam"])
        report["steam_flatpak_socket_overrides"] = {scope: [line for line in command(args).splitlines() if "xdg-run/open-trofeo-lcd" in line]
                for scope, args in (("user", ["flatpak", "override", "--user", "--show", "com.valvesoftware.Steam"]),
                                    ("system", ["flatpak", "override", "--show", "com.valvesoftware.Steam"]))}
    logs = [state / "open-trofeo-lcd/fps-probe.log", flatpak / ".local/state/open-trofeo-lcd/fps-probe.log"]
    report["fps_probe_logs"] = {str(p): log_excerpt(p, r"event=") for p in logs}
    worker = state / "open-trofeo-lcd/replay-worker.log"
    report["display_worker_log"] = log_excerpt(worker, r"TRCC display API|TRCC frame rotation|Error:|Animation loaded|readiness|slow send")
    return redact(report, home, runtime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18777")
    parser.add_argument("--game", default="Enshrouded")
    parser.add_argument("--output", default=str(Path.home() / "trofeo-support.txt"))
    parser.add_argument("--delay", type=int, default=0, help="Seconds to switch back into the game before collection (0-60)")
    args = parser.parse_args()
    if not args.game.strip():
        parser.error("--game must name the game to inspect")
    if not 0 <= args.delay <= 60:
        parser.error("--delay must be between 0 and 60 seconds")
    if args.delay:
        print(f"Collecting in {args.delay} seconds. Switch back into the unpaused game.", flush=True)
        time.sleep(args.delay)
    report = collect(args.url, args.game)
    if args.output == "-":
        print(report)
    else:
        output = Path(args.output).expanduser()
        output.write_text(report + "\n", encoding="utf-8")
        print(f"Saved {output}. Review this file before sharing it. No settings or USB state changed.")


if __name__ == "__main__":
    main()
