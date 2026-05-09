#!/usr/bin/env python3
"""
Open Trofeo LCD Backend (Etap 2.2)

Local HTTP/JSON control plane for the LCD runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
import shutil
import queue
from copy import deepcopy
from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image
from replay_from_pcap import parse_usbpcap_bulk_payloads, extract_init_and_frames
from stats_sources import StatsProvider
from theme_renderer import render_theme_document
from theme_schema import (
    KNOWN_STAT_SOURCES,
    THEME_SCHEMA_VERSION,
    ThemeDocument,
    load_theme_document,
    normalize_theme_document,
    save_theme_document,
)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def to_abs(base: Path, raw_path: str) -> Path:
    p = Path(raw_path).expanduser()
    return p if p.is_absolute() else (base / p)


@dataclass
class BackendConfig:
    workdir: Path
    pcap_path: Path
    frame_index: int
    host: str
    port: int
    ack_timeout_ms: int
    inter_packet_delay: float
    frame_delay: float
    connect_retries: int
    connect_retry_delay: float
    python_bin: str
    replay_script: Path
    trofeo_script: Path
    trcc_static_script: Path
    trcc_static_overlay_script: Path
    trcc_animation_script: Path
    child_log_file: Path
    themes_file: Path
    playlist_file: Path
    display_backend: str
    trcc_bin: str

    def as_json(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "workdir",
            "pcap_path",
            "replay_script",
            "trofeo_script",
            "trcc_static_script",
            "trcc_static_overlay_script",
            "trcc_animation_script",
            "child_log_file",
            "themes_file",
            "playlist_file",
        ):
            data[key] = str(data[key])
        return data


class ReplayController:
    def __init__(self, cfg: BackendConfig):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.runtime_dir = Path.home() / ".local/state/open-trofeo-lcd" / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.proc: subprocess.Popen | None = None
        self.proc_started_at: float | None = None
        self.mode = "idle"
        self.last_error: str | None = None
        self.last_exit_code: int | None = None
        self.init_present = False
        self.frame_count = 0
        self.last_capture_scan_at: str | None = None
        self.themes: dict[str, dict[str, Any]] = {}
        self.themes_file_mtime_ns: int | None = None
        self.playlist: list[dict[str, Any]] = []
        self.playlist_thread: threading.Thread | None = None
        self.playlist_stop = threading.Event()
        self.playlist_started_at: float | None = None
        self.playlist_index = 0
        self.live_theme_thread: threading.Thread | None = None
        self.live_theme_stop = threading.Event()
        self.live_theme_started_at: float | None = None
        self.stats_provider = StatsProvider()
        self._load_themes()
        self._load_playlist()

    def _refresh_mode_locked(self) -> None:
        playlist_running = self.playlist_thread is not None and self.playlist_thread.is_alive()
        live_theme_running = self.live_theme_thread is not None and self.live_theme_thread.is_alive()
        proc_running = self.proc is not None and self.proc.poll() is None
        if playlist_running:
            self.mode = "playlist"
        elif live_theme_running:
            self.mode = "theme-live"
        elif not proc_running:
            self.mode = "idle"

    def _log(self, msg: str) -> None:
        print(f"[{now_iso()}] {msg}", flush=True)

    def _runtime_temp_dir(self, prefix: str) -> Path:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=prefix, dir=str(self.runtime_dir)))

    def _runtime_temp_file(self, prefix: str, suffix: str) -> Path:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=str(self.runtime_dir))
        os.close(fd)
        return Path(tmp_name)

    def _kill_orphan_display_helpers(self) -> list[int]:
        patterns = [
            str(self.cfg.workdir / "scripts/trcc_static_image.py"),
            str(self.cfg.workdir / "scripts/trcc_static_overlay_image.py"),
            str(self.cfg.workdir / "scripts/trcc_animated_image.py"),
            str(self.cfg.workdir / "replay_from_pcap.py"),
            str(self.cfg.workdir / "trofeo_lcd.py"),
        ]
        protected = {os.getpid()}
        if self.proc is not None:
            protected.add(self.proc.pid)
        killed: list[int] = []
        for pattern in patterns:
            try:
                payload = subprocess.check_output(
                    ["pgrep", "-f", pattern],
                    encoding="utf-8",
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                continue
            pids = [
                int(line.strip())
                for line in payload.splitlines()
                if line.strip().isdigit() and int(line.strip()) not in protected
            ]
            if not pids:
                continue
            self._log(f"kill orphan display helpers for pattern={pattern}: {' '.join(str(pid) for pid in pids)}")
            pending = list(dict.fromkeys(pids))
            for sig in (signal.SIGTERM, signal.SIGKILL):
                for pid in list(pending):
                    try:
                        os.kill(pid, sig)
                    except ProcessLookupError:
                        pending.remove(pid)
                    except Exception:
                        pass
                deadline = time.time() + (0.8 if sig == signal.SIGTERM else 0.5)
                while pending and time.time() < deadline:
                    still_running: list[int] = []
                    for pid in pending:
                        try:
                            os.kill(pid, 0)
                            still_running.append(pid)
                        except ProcessLookupError:
                            killed.append(pid)
                        except Exception:
                            still_running.append(pid)
                    pending = still_running
                    if pending:
                        time.sleep(0.08)
                if not pending:
                    break
            killed.extend(pid for pid in pids if pid not in killed)
        return sorted(set(killed))

    def _preflight_trcc_display_start(self) -> None:
        self._stop_display_worker()
        killed = self._kill_orphan_display_helpers()
        time.sleep(1.0 if killed else 0.35)

    def _load_themes(self) -> None:
        with self.lock:
            self.themes = {}
            try:
                if not self.cfg.themes_file.exists():
                    self.themes_file_mtime_ns = None
                    return
                raw = json.loads(self.cfg.themes_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for name, item in raw.items():
                        if not isinstance(name, str) or not isinstance(item, dict):
                            continue
                        path = str(item.get("path", "")).strip()
                        if not path:
                            continue
                        self.themes[name] = {
                            "path": path,
                            "raw_jpeg_passthrough": bool(item.get("raw_jpeg_passthrough", False)),
                        }
                try:
                    self.themes_file_mtime_ns = self.cfg.themes_file.stat().st_mtime_ns
                except Exception:
                    self.themes_file_mtime_ns = None
            except Exception as exc:
                self.last_error = f"themes load failed: {exc}"

    def _save_themes(self) -> None:
        with self.lock:
            ensure_parent(self.cfg.themes_file)
            payload = json.dumps(self.themes, ensure_ascii=False, indent=2)
            self.cfg.themes_file.write_text(payload + "\n", encoding="utf-8")
            try:
                self.themes_file_mtime_ns = self.cfg.themes_file.stat().st_mtime_ns
            except Exception:
                self.themes_file_mtime_ns = None

    def _reload_themes_if_changed(self) -> None:
        with self.lock:
            current_mtime_ns: int | None = None
            try:
                if self.cfg.themes_file.exists():
                    current_mtime_ns = self.cfg.themes_file.stat().st_mtime_ns
            except Exception:
                current_mtime_ns = None
            if current_mtime_ns != self.themes_file_mtime_ns:
                self._load_themes()

    def list_themes(self) -> dict[str, Any]:
        self._reload_themes_if_changed()
        with self.lock:
            items = []
            for name in sorted(self.themes.keys()):
                item = self.themes[name]
                resolved = to_abs(self.cfg.workdir, item["path"])
                theme_type = "image"
                if resolved.suffix.lower() == ".json":
                    theme_type = "theme-doc"
                items.append(
                    {
                        "name": name,
                        "path": item["path"],
                        "raw_jpeg_passthrough": bool(item.get("raw_jpeg_passthrough", False)),
                        "type": theme_type,
                        "exists": resolved.exists(),
                        "resolved_path": str(resolved),
                    }
                )
            return {"count": len(items), "items": items}

    def add_theme(self, name: str, path: str, raw_jpeg_passthrough: bool = False) -> dict[str, Any]:
        self._reload_themes_if_changed()
        with self.lock:
            name = str(name).strip()
            path = str(path).strip()
            if not name:
                raise RuntimeError("theme name is required")
            if not path:
                raise RuntimeError("theme path is required")
            self.themes[name] = {
                "path": path,
                "raw_jpeg_passthrough": bool(raw_jpeg_passthrough),
            }
            self._save_themes()
            return {"name": name, "theme": self.themes[name]}

    def remove_theme(self, name: str) -> dict[str, Any]:
        self._reload_themes_if_changed()
        with self.lock:
            name = str(name).strip()
            if name not in self.themes:
                raise RuntimeError(f"theme not found: {name}")
            removed = self.themes.pop(name)
            self._save_themes()
            return {"name": name, "removed": removed}

    def apply_theme(self, name: str, resume_loop: bool = False, timeout_s: float = 30.0) -> dict[str, Any]:
        self._reload_themes_if_changed()
        with self.lock:
            name = str(name).strip()
            theme = self.themes.get(name)
            if theme is None:
                raise RuntimeError(f"theme not found: {name}")
            resolved = to_abs(self.cfg.workdir, str(theme["path"]))
            if resolved.suffix.lower() == ".json":
                return self.send_theme_doc(
                    path=str(theme["path"]),
                    resume_loop=resume_loop,
                    timeout_s=timeout_s,
                )
            return self.send_image(
                image_path=str(theme["path"]),
                raw_jpeg_passthrough=bool(theme.get("raw_jpeg_passthrough", False)),
                timeout_s=timeout_s,
                resume_loop=resume_loop,
            )

    def get_theme_schema(self) -> dict[str, Any]:
        return {
            "schema_version": THEME_SCHEMA_VERSION,
            "stat_sources": sorted(KNOWN_STAT_SOURCES),
        }

    def load_theme_doc(self, path: str) -> dict[str, Any]:
        target = to_abs(self.cfg.workdir, path)
        if not target.exists():
            raise RuntimeError(f"theme file not found: {target}")
        doc = load_theme_document(target)
        return {
            "path": str(path),
            "resolved_path": str(target),
            "document": doc.data,
            "theme_name": doc.name,
        }

    def save_theme_doc(self, path: str, document: dict[str, Any]) -> dict[str, Any]:
        target = to_abs(self.cfg.workdir, path)
        saved = save_theme_document(target, document)
        doc = load_theme_document(saved)
        return {
            "path": str(path),
            "resolved_path": str(saved),
            "document": doc.data,
            "theme_name": doc.name,
            "bytes": saved.stat().st_size,
        }

    def _render_theme_doc_to_file(
        self,
        path: str | None = None,
        document: dict[str, Any] | None = None,
        out_path: str | None = None,
        stats_override: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if document is not None:
            theme = ThemeDocument(normalize_theme_document(document))
            base_dir = self.cfg.workdir if path is None else to_abs(self.cfg.workdir, path).parent
        else:
            if not path:
                raise RuntimeError("theme path is required")
            source = to_abs(self.cfg.workdir, path)
            if not source.exists():
                raise RuntimeError(f"theme file not found: {source}")
            theme = load_theme_document(source)
            base_dir = source.parent

        image = render_theme_document(
            theme,
            base_dir=base_dir,
            stats_provider=self.stats_provider,
            stats_override=stats_override,
        )
        if out_path:
            target = Path(out_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f"{target.stem}-", suffix=target.suffix or ".png", dir=str(target.parent))
            os.close(fd)
            tmp_target = Path(tmp_name)
            image.save(tmp_target)
            os.replace(tmp_target, target)
            out_file = target
        else:
            fd, tmp_name = tempfile.mkstemp(prefix="trofeo-theme-", suffix=".png")
            os.close(fd)
            out_file = Path(tmp_name)
            image.save(out_file)
        return {
            "image_path": str(out_file),
            "theme_name": theme.name,
            "width": image.width,
            "height": image.height,
        }

    def _merge_live_stats(self, media_override: dict[str, str] | None = None) -> dict[str, str]:
        values = dict(self.stats_provider.snapshot().values)
        if isinstance(media_override, dict):
            for key, value in media_override.items():
                values[str(key)] = str(value)
        return values

    def render_theme_preview(self, path: str | None = None, document: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._render_theme_doc_to_file(path=path, document=document)

    def _theme_animation_spec(
        self,
        path: str | None = None,
        document: dict[str, Any] | None = None,
        max_frames: int | None = None,
    ) -> dict[str, Any] | None:
        if document is not None:
            theme = ThemeDocument(normalize_theme_document(document))
            base_dir = self.cfg.workdir if path is None else to_abs(self.cfg.workdir, path).parent
        else:
            if not path:
                return None
            source = to_abs(self.cfg.workdir, path)
            if not source.exists():
                return None
            theme = load_theme_document(source)
            base_dir = source.parent

        animation = theme.data.get("effects", {}).get("animation", {})
        if not isinstance(animation, dict):
            return None
        if not bool(animation.get("enabled", False)):
            return None
        if not bool(animation.get("use_as_background", True)):
            return None
        frame_paths = animation.get("frame_paths", [])
        if not isinstance(frame_paths, list) or len(frame_paths) <= 1:
            return None
        frame_durations = animation.get("frame_durations_ms", [])
        if not isinstance(frame_durations, list):
            frame_durations = []
        default_duration = max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
        rendered_dir = self._runtime_temp_dir("trofeo-theme-anim-")
        rendered_frames: list[str] = []
        durations_ms: list[int] = []
        selected_indices = list(range(len(frame_paths)))
        if isinstance(max_frames, int) and max_frames > 0 and len(frame_paths) > max_frames:
            stride = max(1, (len(frame_paths) + max_frames - 1) // max_frames)
            selected_indices = list(range(0, len(frame_paths), stride))
            if selected_indices[-1] != len(frame_paths) - 1:
                selected_indices.append(len(frame_paths) - 1)

        for idx in selected_indices:
            theme_frame = json.loads(json.dumps(theme.data))
            theme_frame.setdefault("effects", {}).setdefault("animation", {})
            theme_frame["effects"]["animation"]["current_frame"] = idx
            image = render_theme_document(ThemeDocument(normalize_theme_document(theme_frame)), base_dir=base_dir, stats_provider=self.stats_provider)
            out_path = rendered_dir / f"frame_{idx:04d}.png"
            image.save(out_path)
            rendered_frames.append(str(out_path))
            duration_ms = default_duration
            if idx < len(frame_durations):
                try:
                    duration_ms = max(1, int(frame_durations[idx]))
                except Exception:
                    duration_ms = default_duration
            if len(selected_indices) != len(frame_paths):
                duration_ms = int(round(duration_ms * (len(frame_paths) / max(1, len(selected_indices)))))
                duration_ms = max(1, duration_ms)
            durations_ms.append(duration_ms)
        return {
            "frame_paths": rendered_frames,
            "frame_durations_ms": durations_ms,
            "loop": bool(animation.get("loop", True)),
            "fps": float(animation.get("fps", 12.0)),
            "frame_count": len(rendered_frames),
        }

    def _split_media_overlay_document(self, document: dict[str, Any] | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if not isinstance(document, dict):
            return None, None
        base_doc = deepcopy(document)
        overlay_doc = deepcopy(document)
        media_stats: list[dict[str, Any]] = []
        base_stats: list[dict[str, Any]] = []
        media_item_ids: set[str] = set()
        media_images: list[dict[str, Any]] = []
        base_images: list[dict[str, Any]] = []

        for item in document.get("stats", []):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            item_copy = deepcopy(item)
            if source.startswith("media_"):
                if source == "media_title":
                    item_copy["marquee"] = False
                media_stats.append(item_copy)
                item_id = str(item.get("id", "")).strip()
                if item_id:
                    media_item_ids.add(item_id)
            else:
                base_stats.append(item_copy)

        for item in document.get("images", []):
            if not isinstance(item, dict):
                continue
            item_copy = deepcopy(item)
            source = str(item.get("source", "")).strip()
            if source in {"media_cover", "media_video_frame"}:
                media_images.append(item_copy)
                item_id = str(item.get("id", "")).strip()
                if item_id:
                    media_item_ids.add(item_id)
            else:
                base_images.append(item_copy)

        if not media_stats and not media_images:
            return base_doc, None

        base_doc["stats"] = base_stats
        base_doc["images"] = base_images
        overlay_doc["stats"] = media_stats
        overlay_doc["images"] = media_images
        overlay_doc["texts"] = []
        overlay_doc["background"] = {
            "kind": "color",
            "base_color": [0, 0, 0, 0],
            "accent_color": [0, 0, 0, 0],
            "texture_alpha": 0.0,
            "panels": [],
        }

        effects = overlay_doc.get("effects", {})
        if not isinstance(effects, dict):
            effects = {}
            overlay_doc["effects"] = effects
        effects["show_grid"] = False
        effects["show_safe_area"] = False
        animation = effects.get("animation", {})
        if not isinstance(animation, dict):
            animation = {}
            effects["animation"] = animation
        animation["enabled"] = False
        animation["frame_paths"] = []
        animation["frame_durations_ms"] = []
        animation["current_frame"] = 0
        motion_tracks = effects.get("motion_tracks", [])
        if isinstance(motion_tracks, list):
            effects["motion_tracks"] = [
                deepcopy(track)
                for track in motion_tracks
                if isinstance(track, dict) and str(track.get("item_id", "")).strip() in media_item_ids
            ]
        else:
            effects["motion_tracks"] = []
        return base_doc, overlay_doc

    def _render_theme_overlay_to_file(
        self,
        document: dict[str, Any],
        *,
        path: str | None = None,
        out_path: str | None = None,
        stats_override: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        theme = ThemeDocument(normalize_theme_document(document))
        base_dir = self.cfg.workdir if path is None else to_abs(self.cfg.workdir, path).parent
        image = render_theme_document(
            theme,
            base_dir=base_dir,
            stats_provider=self.stats_provider,
            stats_override=stats_override,
            transparent_background=True,
            include_images=True,
            include_effects=False,
            output_mode="RGBA",
        )
        if out_path:
            target = Path(out_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f"{target.stem}-", suffix=target.suffix or ".png", dir=str(target.parent))
            os.close(fd)
            tmp_target = Path(tmp_name)
            image.save(tmp_target)
            os.replace(tmp_target, target)
        else:
            fd, tmp_name = tempfile.mkstemp(prefix="trofeo-theme-overlay-", suffix=".png")
            os.close(fd)
            target = Path(tmp_name)
            image.save(target)
        return {
            "image_path": str(target),
            "width": image.width,
            "height": image.height,
        }

    def _compose_overlay_frame(self, base_path: str, overlay_path: str, out_path: str) -> dict[str, Any]:
        base = Image.open(base_path).convert("RGBA")
        overlay = Image.open(overlay_path).convert("RGBA")
        composed = Image.alpha_composite(base, overlay)
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f"{target.stem}-", suffix=target.suffix or ".png", dir=str(target.parent))
        os.close(fd)
        tmp_target = Path(tmp_name)
        composed.save(tmp_target)
        os.replace(tmp_target, target)
        return {
            "image_path": str(target),
            "width": composed.width,
            "height": composed.height,
        }

    def send_theme_doc(
        self,
        path: str | None = None,
        document: dict[str, Any] | None = None,
        timeout_s: float = 30.0,
        resume_loop: bool = False,
        live_refresh: bool = True,
        keep_live_refresh_running: bool = False,
    ) -> dict[str, Any]:
        send_result: dict[str, Any]
        live_refresh_overlay_doc: dict[str, Any] | None = None
        live_refresh_overlay_path: str | None = None
        live_refresh_render_path: str | None = None
        live_refresh_base_path: str | None = None
        theme_input = document
        if theme_input is None and path:
            try:
                loaded = self.load_theme_doc(path)
                raw_document = loaded.get("document")
                if isinstance(raw_document, dict):
                    theme_input = raw_document
            except Exception:
                theme_input = None
        # Stop the previous live-refresh worker before switching the base theme.
        # Otherwise the old worker can still repaint the LCD with the previous
        # theme while the new TRCC worker is starting, which makes "Apply"
        # appear to do nothing even though the API reports success.
        if not keep_live_refresh_running:
            self._stop_live_theme_refresh()
        if self.cfg.display_backend == "trcc":
            overlay_doc = None
            theme_for_animation = theme_input
            if self._theme_has_media_sources(theme_input):
                theme_for_animation, overlay_doc = self._split_media_overlay_document(theme_input)
            animation_spec = self._theme_animation_spec(path=path, document=theme_for_animation, max_frames=None)
            if animation_spec is not None:
                if overlay_doc is not None:
                    overlay_render = self._render_theme_overlay_to_file(
                        overlay_doc,
                        path=path,
                        stats_override=self._merge_live_stats(self.stats_provider._read_media_now_playing()),
                    )
                    animation_spec["overlay_path"] = overlay_render["image_path"]
                    live_refresh_overlay_doc = overlay_doc
                    live_refresh_overlay_path = str(overlay_render["image_path"])
                send_result = self._start_trcc_animation_worker(animation_spec)
                send_result["rendered_animation"] = animation_spec
                if overlay_doc is not None:
                    send_result["overlay_render"] = overlay_render
            else:
                render_out_path = None
                if overlay_doc is not None:
                    runtime_dir = self._runtime_temp_dir("trofeo-theme-live-")
                    live_refresh_base_path = str(runtime_dir / "base.png")
                    live_refresh_overlay_path = str(runtime_dir / "overlay.png")
                    render_out_path = str(runtime_dir / "current.png")
                    live_refresh_render_path = render_out_path
                    self._render_theme_doc_to_file(
                        path=path,
                        document=theme_for_animation,
                        out_path=live_refresh_base_path,
                    )
                    self._render_theme_overlay_to_file(
                        overlay_doc,
                        path=path,
                        out_path=live_refresh_overlay_path,
                        stats_override=self._merge_live_stats(self.stats_provider._read_media_now_playing()),
                    )
                    rendered = self._compose_overlay_frame(
                        live_refresh_base_path,
                        live_refresh_overlay_path,
                        render_out_path,
                    )
                else:
                    rendered = self._render_theme_doc_to_file(path=path, document=document, out_path=render_out_path)
                send_result = self.send_image(
                    image_path=rendered["image_path"],
                    raw_jpeg_passthrough=False,
                    timeout_s=timeout_s,
                    resume_loop=resume_loop,
                    stop_live_refresh=not keep_live_refresh_running,
                )
                send_result["rendered_theme"] = rendered
        else:
            rendered = self._render_theme_doc_to_file(path=path, document=document)
            send_result = self.send_image(
                image_path=rendered["image_path"],
                raw_jpeg_passthrough=False,
                timeout_s=timeout_s,
                resume_loop=resume_loop,
                stop_live_refresh=not keep_live_refresh_running,
            )
            send_result["rendered_theme"] = rendered
        if live_refresh:
            theme_for_scan = theme_input
            if self._theme_has_media_sources(theme_for_scan):
                self._start_live_theme_refresh(
                    path=path,
                    document=theme_for_scan,
                    interval_s=1.0,
                    overlay_document=live_refresh_overlay_doc,
                    overlay_path=live_refresh_overlay_path,
                    refresh_target_path=live_refresh_render_path,
                    base_render_path=live_refresh_base_path,
                )
            else:
                self._stop_live_theme_refresh()
        return send_result

    def _stop_display_worker(self, timeout: float = 5.0) -> dict[str, Any]:
        with self.lock:
            self._cleanup_proc_locked()
            if self.proc is None:
                return {"running": False, "already_stopped": True}

            proc = self.proc
            pid = proc.pid
            self._log(f"stop display worker pid={pid}")
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._log(f"kill display worker pid={pid}")
                proc.kill()
                proc.wait(timeout=2)

            self.last_exit_code = proc.returncode
            self.proc = None
            self.proc_started_at = None
            self._refresh_mode_locked()
            return {"running": False, "pid": pid, "exit_code": self.last_exit_code}

    def _theme_has_media_sources(self, document: dict[str, Any] | None) -> bool:
        if not isinstance(document, dict):
            return False
        for entry in document.get("stats", []):
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source", "")).strip()
            if source.startswith("media_"):
                return True
        for entry in document.get("images", []):
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source", "")).strip()
            if source in {"media_cover", "media_video_frame"}:
                return True
        return False

    def _theme_has_background_animation(self, document: dict[str, Any] | None) -> bool:
        if not isinstance(document, dict):
            return False
        effects = document.get("effects", {})
        if not isinstance(effects, dict):
            return False
        animation = effects.get("animation", {})
        if not isinstance(animation, dict):
            return False
        if not bool(animation.get("enabled", False)):
            return False
        if not bool(animation.get("use_as_background", True)):
            return False
        frames = animation.get("frame_paths", [])
        return isinstance(frames, list) and len(frames) > 1

    def _live_theme_worker(
        self,
        path: str | None,
        document: dict[str, Any],
        interval_s: float,
        overlay_document: dict[str, Any] | None = None,
        overlay_path: str | None = None,
        refresh_target_path: str | None = None,
        base_render_path: str | None = None,
    ) -> None:
        self._log("live theme refresh worker start")
        follow_meta: subprocess.Popen | None = None
        follow_status: subprocess.Popen | None = None
        follow_queue: queue.SimpleQueue[tuple[str, str | None, float]] = queue.SimpleQueue()
        last_refresh = 0.0
        last_fallback = 0.0
        last_event_at = 0.0
        animated_theme = self._theme_has_background_animation(document)
        cheap_overlay_mode = isinstance(overlay_document, dict) and bool(overlay_path)
        fast_file_refresh_mode = bool(refresh_target_path) and not cheap_overlay_mode
        overlay_sources: set[str] = set()
        if isinstance(overlay_document, dict):
            for item in overlay_document.get("stats", []):
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source", "")).strip()
                if source:
                    overlay_sources.add(source)
            for item in overlay_document.get("images", []):
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source", "")).strip()
                if source:
                    overlay_sources.add(source)
        fallback_interval_s = 300.0 if cheap_overlay_mode else (3600.0 if animated_theme else (120.0 if fast_file_refresh_mode else max(10.0, interval_s)))
        last_media_sig: tuple[str, str, str, str, str] | None = None
        last_probe = 0.0
        probe_interval_s = 0.45 if cheap_overlay_mode else (0.25 if fast_file_refresh_mode else max(0.7, min(2.0, interval_s)))
        min_refresh_gap_s = 0.18 if cheap_overlay_mode else (12.0 if animated_theme else (0.12 if fast_file_refresh_mode else 0.25))

        media_players: dict[str, dict[str, str]] = {}

        def _default_media() -> dict[str, str]:
            return self.stats_provider._default_media_snapshot()

        def _media_priority(player_name: str, state: str, title: str) -> tuple[int, int, int]:
            return self.stats_provider._media_priority(player_name, state, title)

        def _normalize_media(raw: dict[str, Any] | None) -> dict[str, str]:
            out = _default_media()
            if not isinstance(raw, dict):
                return out
            for key in ("media_title", "media_artist", "media_album", "media_app", "media_state", "media_source_url"):
                value = str(raw.get(key, "")).strip()
                if value:
                    out[key] = value.lower() if key == "media_state" else value
            cover_raw = str(raw.get("media_cover_path", "") or raw.get("art_url", "")).strip()
            out["media_cover_path"] = self.stats_provider.resolve_media_cover_path(
                cover_raw,
                player_name=str(out.get("media_app", "")),
                title=str(out.get("media_title", "")),
                artist=str(out.get("media_artist", "")),
                album=str(out.get("media_album", "")),
            )
            video_raw = str(raw.get("media_video_frame_path", "")).strip()
            if video_raw:
                out["media_video_frame_path"] = video_raw
            else:
                out["media_video_frame_path"] = self.stats_provider.resolve_media_video_frame_path(
                    out.get("media_source_url", ""),
                    out.get("media_cover_path", ""),
                )
            return out

        def _media_sig(media: dict[str, str]) -> tuple[str, str, str, str, str, str]:
            return (
                str(media.get("media_app", "")),
                str(media.get("media_state", "")),
                str(media.get("media_title", "")),
                str(media.get("media_artist", "")),
                str(media.get("media_cover_path", "")),
                str(media.get("media_video_frame_path", "")),
            )

        def _select_best_player(players: dict[str, dict[str, str]]) -> dict[str, str]:
            best_score = None
            best_media = _default_media()
            for player_name, media in players.items():
                score = _media_priority(player_name, str(media.get("media_state", "")), str(media.get("media_title", "")))
                if best_score is None or score > best_score:
                    best_score = score
                    best_media = dict(media)
            return best_media

        def _merge_follow_metadata(line: str, current: dict[str, str]) -> tuple[str, dict[str, str]]:
            parts = line.rstrip("\n").split("\t")
            player = parts[0].strip() if len(parts) > 0 else ""
            state = parts[1].strip().lower() if len(parts) > 1 else ""
            title = parts[2].strip() if len(parts) > 2 else ""
            artist = parts[3].strip() if len(parts) > 3 else ""
            art_url = parts[4].strip() if len(parts) > 4 else ""
            media_url = parts[5].strip() if len(parts) > 5 else ""
            album = parts[6].strip() if len(parts) > 6 else ""
            candidate = dict(current)
            if player:
                candidate["media_app"] = player
            if state:
                candidate["media_state"] = state
            if title:
                candidate["media_title"] = title
            elif state == "stopped":
                candidate["media_title"] = "N/A"
            if artist:
                candidate["media_artist"] = artist
            elif state == "stopped":
                candidate["media_artist"] = "N/A"
            if album:
                candidate["media_album"] = album
            elif state == "stopped":
                candidate["media_album"] = "N/A"
            if media_url:
                candidate["media_source_url"] = media_url
            cover_path = self.stats_provider.resolve_media_cover_path(
                art_url,
                player_name=player or str(candidate.get("media_app", "")),
                title=str(candidate.get("media_title", "")),
                artist=str(candidate.get("media_artist", "")),
                album=str(candidate.get("media_album", "")),
            )
            if cover_path:
                candidate["media_cover_path"] = cover_path
            elif state == "stopped":
                candidate["media_cover_path"] = ""
            if state == "stopped":
                candidate["media_video_frame_path"] = ""
            else:
                candidate["media_video_frame_path"] = self.stats_provider.resolve_media_video_frame_path(
                    candidate.get("media_source_url", ""),
                    candidate.get("media_cover_path", ""),
                )
            return player or candidate.get("media_app", ""), candidate

        media_cache = _normalize_media(self.stats_provider._read_media_now_playing())
        last_media_sig = _media_sig(media_cache)
        if media_cache.get("media_app") and media_cache["media_app"] != "N/A":
            media_players[media_cache["media_app"]] = dict(media_cache)

        def _start_followers() -> tuple[subprocess.Popen | None, subprocess.Popen | None]:
            meta = None
            status = None
            cmd_prefix: list[str] = []
            stdbuf_bin = shutil.which("stdbuf")
            if stdbuf_bin:
                cmd_prefix = [stdbuf_bin, "-oL"]

            def _spawn_reader(proc: subprocess.Popen | None, kind: str) -> None:
                if proc is None or proc.stdout is None:
                    return

                def _reader() -> None:
                    try:
                        for raw_line in proc.stdout:
                            follow_queue.put((kind, raw_line, time.time()))
                    except Exception:
                        pass
                    finally:
                        follow_queue.put((kind, None, time.time()))

                threading.Thread(target=_reader, daemon=True).start()

            try:
                meta = subprocess.Popen(
                    cmd_prefix + [
                        "playerctl",
                        "-a",
                        "metadata",
                        "--follow",
                        "--format",
                        "{{playerName}}\t{{status}}\t{{xesam:title}}\t{{xesam:artist}}\t{{mpris:artUrl}}\t{{xesam:url}}\t{{xesam:album}}",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                _spawn_reader(meta, "meta")
            except Exception:
                meta = None
            try:
                status = subprocess.Popen(
                    cmd_prefix + ["playerctl", "-a", "status", "--format", "{{playerName}}\t{{status}}", "--follow"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                _spawn_reader(status, "status")
            except Exception:
                status = None
            return meta, status

        def _close_proc(proc: subprocess.Popen | None) -> None:
            if proc is None:
                return
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=0.5)
            except Exception:
                pass

        follow_meta, follow_status = _start_followers()
        while not self.live_theme_stop.is_set():
            now = time.time()
            event = False

            for proc in (follow_meta, follow_status):
                if proc is not None and proc.poll() is not None:
                    event = True
            if (follow_meta is None or follow_meta.poll() is not None) and (follow_status is None or follow_status.poll() is not None):
                follow_meta, follow_status = _start_followers()

            had_follow_data = False
            deadline = time.time() + (0.10 if cheap_overlay_mode else (0.12 if fast_file_refresh_mode else 0.35))
            while True:
                timeout = max(0.0, deadline - time.time())
                if timeout <= 0:
                    break
                try:
                    kind, line, event_ts = follow_queue.get(timeout=timeout)
                except queue.Empty:
                    break
                had_follow_data = True
                if line is None:
                    continue
                changed = False
                if cheap_overlay_mode or fast_file_refresh_mode:
                    previous = dict(media_cache)
                    if kind == "meta":
                        parts = line.rstrip("\n").split("\t")
                        hinted_player = parts[0].strip() if len(parts) > 0 else ""
                        player_name, merged = _merge_follow_metadata(
                            line,
                            media_players.get(hinted_player, media_cache),
                        )
                        if player_name:
                            current_player = media_players.get(player_name, _default_media())
                            current_player.update(merged)
                            media_players[player_name] = current_player
                    else:
                        parts = line.rstrip("\n").split("\t")
                        player_name = parts[0].strip() if len(parts) > 0 else ""
                        state = parts[1].strip().lower() if len(parts) > 1 else ""
                        if player_name and state:
                            current_player = dict(media_players.get(player_name, _default_media()))
                            current_player["media_app"] = player_name
                            current_player["media_state"] = state
                            if state == "stopped":
                                current_player["media_title"] = current_player.get("media_title") or "N/A"
                                current_player["media_artist"] = current_player.get("media_artist", "")
                            media_players[player_name] = current_player
                    media_cache = _select_best_player(media_players) if media_players else media_cache
                    changed = _media_sig(media_cache) != _media_sig(previous)
                    if changed:
                        last_media_sig = _media_sig(media_cache)
                if changed or (not cheap_overlay_mode and not fast_file_refresh_mode):
                    event = True
                    last_event_at = event_ts
            if not had_follow_data:
                self.live_theme_stop.wait(0.05 if cheap_overlay_mode else (0.08 if fast_file_refresh_mode else 0.2))

            if now - last_probe >= probe_interval_s:
                last_probe = now
                try:
                    media = _normalize_media(self.stats_provider._read_media_now_playing())
                    sig = _media_sig(media)
                    if last_media_sig is None:
                        last_media_sig = sig
                        media_cache = media
                        if media.get("media_app") and media["media_app"] != "N/A":
                            media_players[media["media_app"]] = dict(media)
                        if media.get("media_state") in {"playing", "paused"} or media.get("media_title") not in {"", "N/A"}:
                            event = True
                            last_event_at = time.time()
                    elif sig != last_media_sig:
                        prev = last_media_sig
                        last_media_sig = sig
                        media_cache = media
                        if media.get("media_app") and media["media_app"] != "N/A":
                            media_players[media["media_app"]] = dict(media)
                        # For animated themes refresh only on meaningful metadata changes
                        # to reduce visible stutter and expensive worker restarts.
                        if cheap_overlay_mode:
                            changed_track = (sig[2], sig[3], sig[4]) != (prev[2], prev[3], prev[4])
                            changed_state = sig[1] != prev[1]
                            changed_app = sig[0] != prev[0]
                            changed_cover = sig[4] != prev[4]
                            changed_video = sig[5] != prev[5]
                            if changed_track or changed_app:
                                event = True
                            elif changed_cover and "media_cover" in overlay_sources:
                                event = True
                            elif changed_video and "media_video_frame" in overlay_sources:
                                event = True
                            elif changed_state and "media_state" in overlay_sources:
                                event = True
                            if event:
                                last_event_at = time.time()
                        elif animated_theme:
                            changed_track = (sig[2], sig[3]) != (prev[2], prev[3])
                            if changed_track:
                                event = True
                        else:
                            event = True
                except Exception:
                    pass

            if now - last_fallback >= fallback_interval_s:
                event = True
                last_fallback = now

            if event and now - last_refresh >= min_refresh_gap_s:
                try:
                    merged_stats = self._merge_live_stats(media_cache)
                    if overlay_document is not None and overlay_path and refresh_target_path and base_render_path:
                        self._render_theme_overlay_to_file(
                            deepcopy(overlay_document),
                            path=path,
                            out_path=overlay_path,
                            stats_override=merged_stats,
                        )
                        self._compose_overlay_frame(
                            base_render_path,
                            overlay_path,
                            refresh_target_path,
                        )
                    elif overlay_document is not None and overlay_path:
                        self._render_theme_overlay_to_file(
                            deepcopy(overlay_document),
                            path=path,
                            out_path=overlay_path,
                            stats_override=merged_stats,
                        )
                    elif refresh_target_path:
                        self._render_theme_doc_to_file(
                            path=path,
                            document=deepcopy(document),
                            out_path=refresh_target_path,
                            stats_override=merged_stats,
                        )
                    else:
                        self.send_theme_doc(
                            path=path,
                            document=deepcopy(document),
                            timeout_s=max(6.0, interval_s + 5.0),
                            resume_loop=False,
                            live_refresh=False,
                            keep_live_refresh_running=True,
                        )
                    last_refresh = time.time()
                    if cheap_overlay_mode or fast_file_refresh_mode:
                        self._log(
                            "media overlay refreshed"
                            + (
                                f" delay_ms={int(max(0.0, last_refresh - last_event_at) * 1000)}"
                                if last_event_at > 0
                                else ""
                            )
                            + f" state={media_cache.get('media_state', '')}"
                            + f" title={media_cache.get('media_title', '')[:64]}"
                            + f" cover={'yes' if media_cache.get('media_cover_path') else 'no'}"
                            + f" video={'yes' if media_cache.get('media_video_frame_path') else 'no'}"
                        )
                except Exception as exc:
                    with self.lock:
                        self.last_error = f"live-theme refresh failed: {exc}"

        _close_proc(follow_meta)
        _close_proc(follow_status)
        with self.lock:
            self.live_theme_thread = None
            self.live_theme_started_at = None
        self._log("live theme refresh worker stop")

    def _start_live_theme_refresh(
        self,
        path: str | None,
        document: dict[str, Any] | None,
        interval_s: float = 1.0,
        overlay_document: dict[str, Any] | None = None,
        overlay_path: str | None = None,
        refresh_target_path: str | None = None,
        base_render_path: str | None = None,
    ) -> None:
        if not isinstance(document, dict):
            return
        self._stop_live_theme_refresh()
        with self.lock:
            self.live_theme_stop.clear()
            frozen_doc = deepcopy(document)
            frozen_overlay_doc = deepcopy(overlay_document) if isinstance(overlay_document, dict) else None
            self.live_theme_thread = threading.Thread(
                target=self._live_theme_worker,
                args=(
                    path,
                    frozen_doc,
                    max(0.3, float(interval_s)),
                    frozen_overlay_doc,
                    overlay_path,
                    refresh_target_path,
                    base_render_path,
                ),
                daemon=True,
            )
            self.live_theme_started_at = time.time()
            self.live_theme_thread.start()
            self.mode = "theme-live"

    def _stop_live_theme_refresh(self, timeout: float = 3.0) -> None:
        with self.lock:
            th = self.live_theme_thread
            if th is None or not th.is_alive():
                self.live_theme_thread = None
                self.live_theme_started_at = None
                return
            self.live_theme_stop.set()
        if th is threading.current_thread():
            return
        th.join(timeout=max(0.1, timeout))
        with self.lock:
            if self.live_theme_thread is not None and not self.live_theme_thread.is_alive():
                self.live_theme_thread = None
                self.live_theme_started_at = None

    def _normalize_playlist_item(self, item: dict[str, Any]) -> dict[str, Any]:
        name = str(item.get("name", "")).strip()
        if not name:
            raise RuntimeError("playlist item: missing theme name")
        if name not in self.themes:
            raise RuntimeError(f"playlist item: unknown theme '{name}'")
        duration_s = float(item.get("duration_s", 5.0))
        duration_s = max(0.2, duration_s)
        return {"name": name, "duration_s": duration_s}

    def _load_playlist(self) -> None:
        with self.lock:
            self.playlist = []
            try:
                if not self.cfg.playlist_file.exists():
                    return
                raw = json.loads(self.cfg.playlist_file.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    for item in raw:
                        if not isinstance(item, dict):
                            continue
                        try:
                            self.playlist.append(self._normalize_playlist_item(item))
                        except Exception:
                            continue
            except Exception as exc:
                self.last_error = f"playlist load failed: {exc}"

    def _save_playlist(self) -> None:
        with self.lock:
            ensure_parent(self.cfg.playlist_file)
            payload = json.dumps(self.playlist, ensure_ascii=False, indent=2)
            self.cfg.playlist_file.write_text(payload + "\n", encoding="utf-8")

    def _normalize_themes_payload(self, raw_themes: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(raw_themes, dict):
            raise RuntimeError("bundle.themes must be an object")

        out: dict[str, dict[str, Any]] = {}
        for name, item in raw_themes.items():
            if not isinstance(name, str):
                continue
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            if not path:
                continue
            out[name] = {
                "path": path,
                "raw_jpeg_passthrough": bool(item.get("raw_jpeg_passthrough", False)),
            }
        return out

    def build_bundle(self) -> dict[str, Any]:
        with self.lock:
            return {
                "version": 1,
                "exported_at": now_iso(),
                "themes": self.themes,
                "playlist": self.playlist,
            }

    def apply_bundle(self, bundle: dict[str, Any], merge: bool = False) -> dict[str, Any]:
        with self.lock:
            if not isinstance(bundle, dict):
                raise RuntimeError("bundle must be an object")

            themes_in = self._normalize_themes_payload(bundle.get("themes", {}))
            playlist_raw = bundle.get("playlist", [])
            if playlist_raw is None:
                playlist_raw = []
            if not isinstance(playlist_raw, list):
                raise RuntimeError("bundle.playlist must be a list")

            if merge:
                self.themes.update(themes_in)
            else:
                self.themes = dict(themes_in)

            normalized_playlist = []
            for item in playlist_raw:
                if not isinstance(item, dict):
                    continue
                normalized_playlist.append(self._normalize_playlist_item(item))

            if merge:
                self.playlist.extend(normalized_playlist)
            else:
                self.playlist = normalized_playlist

            if self.playlist:
                self.playlist_index %= len(self.playlist)
            else:
                self.playlist_index = 0

            self._save_themes()
            self._save_playlist()
            return {
                "theme_count": len(self.themes),
                "playlist_count": len(self.playlist),
                "merge": bool(merge),
            }

    def save_bundle(self, path: str) -> dict[str, Any]:
        target = to_abs(self.cfg.workdir, path)
        bundle = self.build_bundle()
        ensure_parent(target)
        target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"path": str(target), "bytes": target.stat().st_size}

    def load_bundle(self, path: str, merge: bool = False) -> dict[str, Any]:
        source = to_abs(self.cfg.workdir, path)
        if not source.exists():
            raise RuntimeError(f"bundle file not found: {source}")
        raw = json.loads(source.read_text(encoding="utf-8"))
        result = self.apply_bundle(raw, merge=merge)
        result["path"] = str(source)
        return result

    def list_playlist(self) -> dict[str, Any]:
        with self.lock:
            items = []
            for idx, item in enumerate(self.playlist):
                name = item["name"]
                duration_s = float(item["duration_s"])
                theme = self.themes.get(name)
                theme_path = None if theme is None else str(theme.get("path"))
                items.append(
                    {
                        "index": idx,
                        "name": name,
                        "duration_s": duration_s,
                        "theme_exists": theme is not None,
                        "theme_path": theme_path,
                    }
                )
            return {
                "count": len(items),
                "running": self.playlist_thread is not None and self.playlist_thread.is_alive(),
                "position": self.playlist_index,
                "items": items,
            }

    def set_playlist(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        with self.lock:
            normalized = [self._normalize_playlist_item(item) for item in items]
            self.playlist = normalized
            self.playlist_index = 0
            self._save_playlist()
            return self.list_playlist()

    def add_playlist_item(self, name: str, duration_s: float = 5.0) -> dict[str, Any]:
        with self.lock:
            self.playlist.append(self._normalize_playlist_item({"name": name, "duration_s": duration_s}))
            self._save_playlist()
            return self.list_playlist()

    def remove_playlist_item(self, index: int) -> dict[str, Any]:
        with self.lock:
            idx = int(index)
            if idx < 0 or idx >= len(self.playlist):
                raise RuntimeError(f"playlist index out of range: {idx}")
            self.playlist.pop(idx)
            if self.playlist:
                self.playlist_index %= len(self.playlist)
            else:
                self.playlist_index = 0
            self._save_playlist()
            return self.list_playlist()

    def _playlist_worker(self) -> None:
        self._log("playlist worker start")
        while not self.playlist_stop.is_set():
            with self.lock:
                if not self.playlist:
                    self.last_error = "playlist is empty"
                    break
                idx = self.playlist_index % len(self.playlist)
                item = dict(self.playlist[idx])
                self.playlist_index = (idx + 1) % len(self.playlist)
                self.mode = "playlist"

            name = item["name"]
            duration_s = float(item["duration_s"])
            try:
                self.apply_theme(name, resume_loop=False, timeout_s=max(10.0, duration_s + 10.0))
            except Exception as exc:
                self.last_error = f"playlist apply failed ({name}): {exc}"
                self._log(self.last_error)
                if self.playlist_stop.wait(1.0):
                    break
                continue

            if self.playlist_stop.wait(duration_s):
                break

        with self.lock:
            self.playlist_thread = None
            self.playlist_started_at = None
            self._refresh_mode_locked()
        self._log("playlist worker stop")

    def start_playlist(self) -> dict[str, Any]:
        with self.lock:
            if not self.playlist:
                raise RuntimeError("playlist is empty")
            if self.playlist_thread is not None and self.playlist_thread.is_alive():
                return {"running": True, "already_running": True, "position": self.playlist_index}

            self.stop_loop()
            self._stop_live_theme_refresh()
            self.playlist_stop.clear()
            self.playlist_started_at = time.time()
            self.playlist_thread = threading.Thread(target=self._playlist_worker, daemon=True)
            self.playlist_thread.start()
            self.mode = "playlist"
            return {"running": True, "position": self.playlist_index}

    def stop_playlist(self, timeout: float = 5.0) -> dict[str, Any]:
        with self.lock:
            th = self.playlist_thread
            if th is None or not th.is_alive():
                self.playlist_thread = None
                self._refresh_mode_locked()
                return {"running": False, "already_stopped": True}
            self.playlist_stop.set()

        th.join(timeout=max(0.1, timeout))
        alive = th.is_alive()
        with self.lock:
            if not alive:
                self.playlist_thread = None
                self.playlist_started_at = None
                self._refresh_mode_locked()
        return {"running": alive is True, "stopped": alive is False}

    def scan_capture(self) -> dict[str, Any]:
        with self.lock:
            sig = parse_usbpcap_bulk_payloads(self.cfg.pcap_path)
            init_out, frames = extract_init_and_frames(sig)
            self.init_present = init_out is not None
            self.frame_count = len(frames)
            self.last_capture_scan_at = now_iso()
            if self.frame_count <= 0:
                raise RuntimeError("Capture nie zawiera ramek cmd=0x01")
            if self.cfg.frame_index < 0 or self.cfg.frame_index >= self.frame_count:
                raise RuntimeError(
                    f"frame_index={self.cfg.frame_index} poza zakresem 0..{self.frame_count - 1}"
                )
            return {
                "init_present": self.init_present,
                "frame_count": self.frame_count,
                "frame_index": self.cfg.frame_index,
                "pcap_path": str(self.cfg.pcap_path),
            }

    def _build_replay_cmd(self) -> list[str]:
        return [
            self.cfg.python_bin,
            str(self.cfg.replay_script),
            "--pcap",
            str(self.cfg.pcap_path),
            "--frame",
            str(self.cfg.frame_index),
            "--send-init",
            "--recover-before-send",
            "--drain-in-before-send",
            "--ack-every-packet",
            "--ack-on-seq0-only",
            "--ack-timeout-ms",
            str(self.cfg.ack_timeout_ms),
            "--inter-packet-delay",
            str(self.cfg.inter_packet_delay),
            "--loop",
            "--frame-delay",
            str(self.cfg.frame_delay),
            "--connect-retries",
            str(self.cfg.connect_retries),
            "--connect-retry-delay",
            str(self.cfg.connect_retry_delay),
        ]

    def _cleanup_proc_locked(self) -> None:
        if self.proc is None:
            return
        code = self.proc.poll()
        if code is not None:
            self.last_exit_code = code
            self.proc = None
            self.proc_started_at = None
            self._refresh_mode_locked()
            self._log(f"worker zakończony kodem={code}")

    def start_loop(self) -> dict[str, Any]:
        with self.lock:
            if self.playlist_thread is not None and self.playlist_thread.is_alive():
                raise RuntimeError("playlist is running; stop playlist first")
            self._cleanup_proc_locked()
            self.scan_capture()
            if self.proc is not None and self.proc.poll() is None:
                return {"running": True, "pid": self.proc.pid, "already_running": True}

            ensure_parent(self.cfg.child_log_file)
            child_log = open(self.cfg.child_log_file, "a", encoding="utf-8")
            child_log.write(
                f"\n[{now_iso()}] start loop frame={self.cfg.frame_index} pcap={self.cfg.pcap_path}\n"
            )
            child_log.flush()

            cmd = self._build_replay_cmd()
            self._log("start worker: " + " ".join(cmd))
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=self.cfg.workdir,
                    stdout=child_log,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self.proc_started_at = time.time()
                self.mode = "loop"
                self.last_error = None
                child_log.close()
            except Exception as exc:
                child_log.close()
                self.last_error = str(exc)
                raise

            return {"running": True, "pid": self.proc.pid}

    def _start_trcc_static_worker(self, image_path: Path) -> dict[str, Any]:
        self._preflight_trcc_display_start()
        trcc_bin = Path(self.cfg.trcc_bin).expanduser()
        if not trcc_bin.is_absolute():
            trcc_bin = (self.cfg.workdir / trcc_bin).resolve()
        if not trcc_bin.exists():
            raise RuntimeError(f"Brak binarki trcc: {trcc_bin}")

        trcc_python = trcc_bin.parent / "python"
        if not trcc_python.exists():
            raise RuntimeError(f"Brak interpretera venv trcc: {trcc_python}")
        if not self.cfg.trcc_static_script.exists():
            raise RuntimeError(f"Brak skryptu TRCC static worker: {self.cfg.trcc_static_script}")

        ensure_parent(self.cfg.child_log_file)
        child_log = open(self.cfg.child_log_file, "a", encoding="utf-8")
        child_log.write(f"\n[{now_iso()}] start static image {image_path}\n")
        child_log.flush()

        cmd = [
            str(trcc_python),
            str(self.cfg.trcc_static_script),
            str(image_path),
            "--interval",
            "0.5",
        ]
        self._log("start static worker: " + " ".join(cmd))
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=self.cfg.workdir,
                stdout=child_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.proc_started_at = time.time()
            self.mode = "static-image"
            self.last_error = None
            child_log.close()
        except Exception:
            child_log.close()
            raise

        time.sleep(1.2)
        self._cleanup_proc_locked()
        if self.proc is None or self.proc.poll() is not None:
            tail = ""
            try:
                tail = self.cfg.child_log_file.read_text(encoding="utf-8", errors="replace")[-1200:]
            except Exception:
                pass
            raise RuntimeError(f"static worker failed to start: {tail.strip() or 'unknown error'}")

        return {"running": True, "pid": self.proc.pid, "mode": self.mode}

    def _start_native_static_worker(
        self,
        image_path: Path,
        raw_jpeg_passthrough: bool = False,
        stop_live_refresh: bool = True,
    ) -> dict[str, Any]:
        if stop_live_refresh:
            self._stop_live_theme_refresh()
        self._stop_display_worker(timeout=2.0)
        killed = self._kill_orphan_display_helpers()
        time.sleep(1.0 if killed else 0.35)

        ensure_parent(self.cfg.child_log_file)
        child_log = open(self.cfg.child_log_file, "a", encoding="utf-8")
        child_log.write(f"\n[{now_iso()}] start native static image {image_path}\n")
        child_log.flush()

        cmd = [
            self.cfg.python_bin,
            str(self.cfg.trofeo_script),
            "--trcc-compatible",
            "--recover-before-send",
            "--drain-in-before-send",
            "--ack-every-packet",
            "--ack-on-seq0-only",
            "--ack-timeout-ms",
            "500",
            "--inter-packet-delay",
            "0.01",
            "--loop",
            "--interval",
            "0.05",
        ]
        if raw_jpeg_passthrough:
            cmd.append("--raw-jpeg-passthrough")
        cmd.append(str(image_path))

        self._log("start native static worker: " + " ".join(cmd))
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=self.cfg.workdir,
                stdout=child_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.proc_started_at = time.time()
            self.mode = "static-image"
            self.last_error = None
            child_log.close()
        except Exception:
            child_log.close()
            raise

        time.sleep(1.2)
        self._cleanup_proc_locked()
        if self.proc is None or self.proc.poll() is not None:
            tail = ""
            try:
                tail = self.cfg.child_log_file.read_text(encoding="utf-8", errors="replace")[-1200:]
            except Exception:
                pass
            raise RuntimeError(f"native static worker failed to start: {tail.strip() or 'unknown error'}")

        return {"running": True, "pid": self.proc.pid, "mode": self.mode}

    def _start_trcc_static_overlay_worker(self, image_path: Path, overlay_path: Path) -> dict[str, Any]:
        self._preflight_trcc_display_start()
        trcc_bin = Path(self.cfg.trcc_bin).expanduser()
        if not trcc_bin.is_absolute():
            trcc_bin = (self.cfg.workdir / trcc_bin).resolve()
        if not trcc_bin.exists():
            raise RuntimeError(f"Brak binarki trcc: {trcc_bin}")

        trcc_python = trcc_bin.parent / "python"
        if not trcc_python.exists():
            raise RuntimeError(f"Brak interpretera venv trcc: {trcc_python}")
        if not self.cfg.trcc_static_overlay_script.exists():
            raise RuntimeError(f"Brak skryptu TRCC static overlay worker: {self.cfg.trcc_static_overlay_script}")

        ensure_parent(self.cfg.child_log_file)
        child_log = open(self.cfg.child_log_file, "a", encoding="utf-8")
        child_log.write(f"\n[{now_iso()}] start static overlay base={image_path} overlay={overlay_path}\n")
        child_log.flush()

        cmd = [
            str(trcc_python),
            str(self.cfg.trcc_static_overlay_script),
            str(image_path),
            "--overlay",
            str(overlay_path),
            "--interval",
            "0.5",
        ]
        self._log("start static overlay worker: " + " ".join(cmd))
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=self.cfg.workdir,
                stdout=child_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.proc_started_at = time.time()
            self.mode = "static-image"
            self.last_error = None
            child_log.close()
        except Exception:
            child_log.close()
            raise

        time.sleep(1.2)
        self._cleanup_proc_locked()
        if self.proc is None or self.proc.poll() is not None:
            tail = ""
            try:
                tail = self.cfg.child_log_file.read_text(encoding="utf-8", errors="replace")[-1200:]
            except Exception:
                pass
            raise RuntimeError(f"static overlay worker failed to start: {tail.strip() or 'unknown error'}")

        return {"running": True, "pid": self.proc.pid, "mode": self.mode}

    def _start_trcc_animation_worker(self, animation_spec: dict[str, Any]) -> dict[str, Any]:
        self._preflight_trcc_display_start()
        trcc_bin = Path(self.cfg.trcc_bin).expanduser()
        if not trcc_bin.is_absolute():
            trcc_bin = (self.cfg.workdir / trcc_bin).resolve()
        if not trcc_bin.exists():
            raise RuntimeError(f"Brak binarki trcc: {trcc_bin}")

        trcc_python = trcc_bin.parent / "python"
        if not trcc_python.exists():
            raise RuntimeError(f"Brak interpretera venv trcc: {trcc_python}")
        if not self.cfg.trcc_animation_script.exists():
            raise RuntimeError(f"Brak skryptu TRCC animation worker: {self.cfg.trcc_animation_script}")
        frame_paths = animation_spec.get("frame_paths", [])
        if not isinstance(frame_paths, list) or not frame_paths:
            raise RuntimeError("animation worker failed to start: manifest has no frames")
        missing_frames = [str(raw) for raw in frame_paths if not Path(str(raw)).expanduser().exists()]
        if missing_frames:
            raise RuntimeError(
                "animation worker failed to start: missing rendered frames: "
                + ", ".join(missing_frames[:3])
                + (" ..." if len(missing_frames) > 3 else "")
            )

        manifest_path = self._runtime_temp_file("trofeo-theme-anim-", ".json")
        manifest_path.write_text(json.dumps(animation_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        def _read_start_tail() -> str:
            try:
                return self.cfg.child_log_file.read_text(encoding="utf-8", errors="replace")[-1600:]
            except Exception:
                return ""

        startup_tail = ""
        for attempt in range(2):
            ensure_parent(self.cfg.child_log_file)
            child_log = open(self.cfg.child_log_file, "a", encoding="utf-8")
            child_log.write(f"\n[{now_iso()}] start animation manifest {manifest_path} attempt={attempt + 1}\n")
            child_log.flush()

            cmd = [
                str(trcc_python),
                str(self.cfg.trcc_animation_script),
                str(manifest_path),
            ]
            self._log("start animation worker: " + " ".join(cmd))
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=self.cfg.workdir,
                    stdout=child_log,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self.proc_started_at = time.time()
                self.mode = "animation"
                self.last_error = None
                child_log.close()
            except Exception:
                child_log.close()
                raise

            time.sleep(1.2)
            self._cleanup_proc_locked()
            if self.proc is not None and self.proc.poll() is None:
                return {
                    "running": True,
                    "pid": self.proc.pid,
                    "mode": self.mode,
                    "frame_count": int(animation_spec.get("frame_count", 0)),
                    "manifest_path": str(manifest_path),
                }

            startup_tail = _read_start_tail().strip()
            if attempt == 0 and (
                "in use by another process" in startup_tail.lower()
                or "operation timed out" in startup_tail.lower()
            ):
                self._log("animation worker retry after device busy/timeout")
                self._stop_display_worker(timeout=2.0)
                time.sleep(1.0)
                continue
            break

        raise RuntimeError(f"animation worker failed to start: {startup_tail or 'unknown error'}")

    def stop_loop(self, timeout: float = 5.0) -> dict[str, Any]:
        with self.lock:
            self._stop_live_theme_refresh()
            self._cleanup_proc_locked()
            if self.proc is None:
                return {"running": False, "already_stopped": True}

            proc = self.proc
            pid = proc.pid
            self._log(f"stop worker pid={pid}")
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._log(f"kill worker pid={pid}")
                proc.kill()
                proc.wait(timeout=2)

            self.last_exit_code = proc.returncode
            self.proc = None
            self.proc_started_at = None
            if self.playlist_thread is None or not self.playlist_thread.is_alive():
                self.mode = "idle"
            return {"running": False, "pid": pid, "exit_code": self.last_exit_code}

    def restart_loop(self) -> dict[str, Any]:
        with self.lock:
            self.stop_loop()
            return self.start_loop()

    def set_frame(self, frame_index: int) -> dict[str, Any]:
        with self.lock:
            self.cfg.frame_index = int(frame_index)
            self.scan_capture()
            if self.proc is not None and self.proc.poll() is None:
                self._log(f"frame_index -> {self.cfg.frame_index}; restart worker")
                return self.restart_loop()
            return {"running": False, "frame_index": self.cfg.frame_index}

    def set_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            restart_required = False

            if "pcap_path" in payload:
                self.cfg.pcap_path = to_abs(self.cfg.workdir, str(payload["pcap_path"]))
                restart_required = True
            if "frame_index" in payload:
                self.cfg.frame_index = int(payload["frame_index"])
                restart_required = True
            if "ack_timeout_ms" in payload:
                self.cfg.ack_timeout_ms = max(1, int(payload["ack_timeout_ms"]))
                restart_required = True
            if "inter_packet_delay" in payload:
                self.cfg.inter_packet_delay = max(0.0, float(payload["inter_packet_delay"]))
                restart_required = True
            if "frame_delay" in payload:
                self.cfg.frame_delay = max(0.0, float(payload["frame_delay"]))
                restart_required = True
            if "connect_retries" in payload:
                self.cfg.connect_retries = max(1, int(payload["connect_retries"]))
                restart_required = True
            if "connect_retry_delay" in payload:
                self.cfg.connect_retry_delay = max(0.0, float(payload["connect_retry_delay"]))
                restart_required = True

            self.scan_capture()
            if restart_required and self.proc is not None and self.proc.poll() is None:
                return self.restart_loop()
            return {"running": self.is_running(), "config": self.cfg.as_json()}

    def send_image(
        self,
        image_path: str,
        raw_jpeg_passthrough: bool = False,
        timeout_s: float = 30.0,
        resume_loop: bool = False,
        stop_live_refresh: bool = True,
    ) -> dict[str, Any]:
        with self.lock:
            if stop_live_refresh:
                self._stop_live_theme_refresh()
            resolved = to_abs(self.cfg.workdir, image_path)
            if not resolved.exists():
                raise RuntimeError(f"Brak pliku obrazu: {resolved}")

        with self.lock:
            result = self._start_native_static_worker(
                resolved,
                raw_jpeg_passthrough=raw_jpeg_passthrough,
                stop_live_refresh=stop_live_refresh,
            )
            result["image_path"] = str(resolved)
            return result

    def is_running(self) -> bool:
        with self.lock:
            self._cleanup_proc_locked()
            return self.proc is not None and self.proc.poll() is None

    def status(self) -> dict[str, Any]:
        with self.lock:
            self._cleanup_proc_locked()
            playlist_running = self.playlist_thread is not None and self.playlist_thread.is_alive()
            live_theme_running = self.live_theme_thread is not None and self.live_theme_thread.is_alive()
            return {
                "ok": True,
                "mode": self.mode,
                "running": self.proc is not None and self.proc.poll() is None,
                "live_theme_running": live_theme_running,
                "live_theme_uptime_s": None
                if self.live_theme_started_at is None
                else round(time.time() - self.live_theme_started_at, 3),
                "pid": None if self.proc is None else self.proc.pid,
                "uptime_s": None if self.proc_started_at is None else round(time.time() - self.proc_started_at, 3),
                "playlist_running": playlist_running,
                "playlist_uptime_s": None
                if self.playlist_started_at is None
                else round(time.time() - self.playlist_started_at, 3),
                "playlist_index": self.playlist_index,
                "playlist_count": len(self.playlist),
                "last_error": self.last_error,
                "last_exit_code": self.last_exit_code,
                "init_present": self.init_present,
                "frame_count": self.frame_count,
                "last_capture_scan_at": self.last_capture_scan_at,
                "theme_count": len(self.themes),
                "config": self.cfg.as_json(),
            }


class ApiHandler(BaseHTTPRequestHandler):
    controller: ReplayController | None = None
    request_shutdown_cb: Any = None

    def _write_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _controller(self) -> ReplayController:
        if self.controller is None:
            raise RuntimeError("Controller is not initialized")
        return self.controller

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        ctl = self._controller()
        if path in ("/health", "/v1/health"):
            self._write_json(200, {"ok": True, "service": "trofeo-backend", "time": now_iso()})
            return
        if path == "/v1/status":
            self._write_json(200, ctl.status())
            return
        if path == "/v1/themes":
            self._write_json(200, {"ok": True, "result": ctl.list_themes(), "status": ctl.status()})
            return
        if path == "/v1/theme-schema":
            self._write_json(200, {"ok": True, "result": ctl.get_theme_schema(), "status": ctl.status()})
            return
        if path == "/v1/playlist":
            self._write_json(200, {"ok": True, "result": ctl.list_playlist(), "status": ctl.status()})
            return
        if path == "/v1/bundle/export":
            self._write_json(200, {"ok": True, "result": ctl.build_bundle(), "status": ctl.status()})
            return
        self._write_json(404, {"ok": False, "error": "not-found", "path": path})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        ctl = self._controller()
        try:
            body = self._read_json_body()
        except json.JSONDecodeError as exc:
            self._write_json(400, {"ok": False, "error": f"invalid-json: {exc}"})
            return

        try:
            if path == "/v1/start":
                if "frame_index" in body:
                    ctl.set_frame(int(body["frame_index"]))
                result = ctl.start_loop()
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/stop":
                result = ctl.stop_loop()
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/shutdown":
                result = ctl.stop_loop()
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                callback = getattr(self, "request_shutdown_cb", None)
                if callable(callback):
                    callback("api shutdown")
                return
            if path == "/v1/restart":
                result = ctl.restart_loop()
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/set-frame":
                if "frame_index" not in body:
                    self._write_json(400, {"ok": False, "error": "frame_index is required"})
                    return
                result = ctl.set_frame(int(body["frame_index"]))
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/config":
                result = ctl.set_config(body)
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/scan":
                result = ctl.scan_capture()
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/send-image":
                image_path = body.get("path")
                if not image_path:
                    self._write_json(400, {"ok": False, "error": "path is required"})
                    return
                raw_passthrough = bool(body.get("raw_jpeg_passthrough", False))
                timeout_s = float(body.get("timeout_s", 30.0))
                resume_loop = bool(body.get("resume_loop", False))
                result = ctl.send_image(
                    image_path=str(image_path),
                    raw_jpeg_passthrough=raw_passthrough,
                    timeout_s=timeout_s,
                    resume_loop=resume_loop,
                )
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/themes/add":
                name = body.get("name")
                theme_path = body.get("path")
                if not name or not theme_path:
                    self._write_json(400, {"ok": False, "error": "name and path are required"})
                    return
                raw_passthrough = bool(body.get("raw_jpeg_passthrough", False))
                result = ctl.add_theme(str(name), str(theme_path), raw_passthrough)
                self._write_json(200, {"ok": True, "result": result, "themes": ctl.list_themes(), "status": ctl.status()})
                return
            if path == "/v1/themes/remove":
                name = body.get("name")
                if not name:
                    self._write_json(400, {"ok": False, "error": "name is required"})
                    return
                result = ctl.remove_theme(str(name))
                self._write_json(200, {"ok": True, "result": result, "themes": ctl.list_themes(), "status": ctl.status()})
                return
            if path == "/v1/themes/apply":
                name = body.get("name")
                if not name:
                    self._write_json(400, {"ok": False, "error": "name is required"})
                    return
                timeout_s = float(body.get("timeout_s", 30.0))
                resume_loop = bool(body.get("resume_loop", False))
                result = ctl.apply_theme(str(name), resume_loop=resume_loop, timeout_s=timeout_s)
                if isinstance(result, dict) and "rendered_animation" in result:
                    compact = dict(result)
                    try:
                        ra = compact.get("rendered_animation")
                        if isinstance(ra, dict):
                            compact["rendered_animation"] = {
                                "frame_count": int(ra.get("frame_count", 0)),
                                "fps": float(ra.get("fps", 0.0)),
                                "loop": bool(ra.get("loop", True)),
                            }
                    except Exception:
                        pass
                    result = compact
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/theme-doc/load":
                theme_path = body.get("path")
                if not theme_path:
                    self._write_json(400, {"ok": False, "error": "path is required"})
                    return
                result = ctl.load_theme_doc(str(theme_path))
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/theme-doc/save":
                theme_path = body.get("path")
                document = body.get("document")
                if not theme_path or not isinstance(document, dict):
                    self._write_json(400, {"ok": False, "error": "path and document(object) are required"})
                    return
                result = ctl.save_theme_doc(str(theme_path), document)
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/theme-doc/preview":
                theme_path = body.get("path")
                document = body.get("document")
                if not theme_path and not isinstance(document, dict):
                    self._write_json(400, {"ok": False, "error": "path or document(object) is required"})
                    return
                result = ctl.render_theme_preview(
                    path=None if not theme_path else str(theme_path),
                    document=document if isinstance(document, dict) else None,
                )
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/theme-doc/apply":
                theme_path = body.get("path")
                document = body.get("document")
                if not theme_path and not isinstance(document, dict):
                    self._write_json(400, {"ok": False, "error": "path or document(object) is required"})
                    return
                timeout_s = float(body.get("timeout_s", 30.0))
                resume_loop = bool(body.get("resume_loop", False))
                result = ctl.send_theme_doc(
                    path=None if not theme_path else str(theme_path),
                    document=document if isinstance(document, dict) else None,
                    timeout_s=timeout_s,
                    resume_loop=resume_loop,
                )
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/playlist/set":
                items = body.get("items")
                if not isinstance(items, list):
                    self._write_json(400, {"ok": False, "error": "items(list) is required"})
                    return
                result = ctl.set_playlist(items)
                self._write_json(200, {"ok": True, "result": result, "playlist": result, "status": ctl.status()})
                return
            if path == "/v1/playlist/add":
                name = body.get("name")
                if not name:
                    self._write_json(400, {"ok": False, "error": "name is required"})
                    return
                duration_s = float(body.get("duration_s", 5.0))
                result = ctl.add_playlist_item(str(name), duration_s)
                self._write_json(200, {"ok": True, "result": result, "playlist": result, "status": ctl.status()})
                return
            if path == "/v1/playlist/remove":
                if "index" not in body:
                    self._write_json(400, {"ok": False, "error": "index is required"})
                    return
                result = ctl.remove_playlist_item(int(body["index"]))
                self._write_json(200, {"ok": True, "result": result, "playlist": result, "status": ctl.status()})
                return
            if path == "/v1/playlist/start":
                result = ctl.start_playlist()
                self._write_json(200, {"ok": True, "result": result, "playlist": ctl.list_playlist(), "status": ctl.status()})
                return
            if path == "/v1/playlist/stop":
                result = ctl.stop_playlist()
                self._write_json(200, {"ok": True, "result": result, "playlist": ctl.list_playlist(), "status": ctl.status()})
                return
            if path == "/v1/bundle/import":
                bundle = body.get("bundle")
                if not isinstance(bundle, dict):
                    self._write_json(400, {"ok": False, "error": "bundle(object) is required"})
                    return
                merge = bool(body.get("merge", False))
                result = ctl.apply_bundle(bundle, merge=merge)
                self._write_json(
                    200,
                    {
                        "ok": True,
                        "result": result,
                        "themes": ctl.list_themes(),
                        "playlist": ctl.list_playlist(),
                        "status": ctl.status(),
                    },
                )
                return
            if path == "/v1/bundle/save":
                out_path = body.get("path")
                if not out_path:
                    self._write_json(400, {"ok": False, "error": "path is required"})
                    return
                result = ctl.save_bundle(str(out_path))
                self._write_json(200, {"ok": True, "result": result, "status": ctl.status()})
                return
            if path == "/v1/bundle/load":
                in_path = body.get("path")
                if not in_path:
                    self._write_json(400, {"ok": False, "error": "path is required"})
                    return
                merge = bool(body.get("merge", False))
                result = ctl.load_bundle(str(in_path), merge=merge)
                self._write_json(
                    200,
                    {
                        "ok": True,
                        "result": result,
                        "themes": ctl.list_themes(),
                        "playlist": ctl.list_playlist(),
                        "status": ctl.status(),
                    },
                )
                return

            self._write_json(404, {"ok": False, "error": "not-found", "path": path})
        except RuntimeError as exc:
            self._write_json(400, {"ok": False, "error": str(exc), "status": ctl.status()})
        except Exception as exc:
            self._write_json(500, {"ok": False, "error": str(exc), "status": ctl.status()})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{now_iso()}] http {self.address_string()} {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trofeo local backend API")
    parser.add_argument("--workdir", default=str(Path.cwd()))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18777)
    parser.add_argument("--pcap", default="dzis.pcapng")
    parser.add_argument("--frame-index", type=int, default=0)
    parser.add_argument("--ack-timeout-ms", type=int, default=500)
    parser.add_argument("--inter-packet-delay", type=float, default=0.01)
    parser.add_argument("--frame-delay", type=float, default=0.02)
    parser.add_argument("--connect-retries", type=int, default=20)
    parser.add_argument("--connect-retry-delay", type=float, default=0.5)
    parser.add_argument("--child-log-file", default=str(Path.home() / ".local/state/open-trofeo-lcd/replay-worker.log"))
    parser.add_argument("--themes-file", default=str(Path(".trofeo-themes.json")))
    parser.add_argument("--playlist-file", default=str(Path(".trofeo-playlist.json")))
    parser.add_argument("--display-backend", choices=("native", "trcc"), default=None)
    parser.add_argument("--trcc-bin", default=str(Path(".venv-trcc/bin/trcc")))
    parser.add_argument("--autostart", action="store_true")
    args = parser.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    trcc_bin = Path(args.trcc_bin).expanduser()
    if not trcc_bin.is_absolute():
        trcc_bin = (workdir / trcc_bin).resolve()
    display_backend = args.display_backend or ("trcc" if trcc_bin.exists() else "native")
    cfg = BackendConfig(
        workdir=workdir,
        pcap_path=to_abs(workdir, args.pcap).resolve(),
        frame_index=max(0, int(args.frame_index)),
        host=args.host,
        port=int(args.port),
        ack_timeout_ms=max(1, int(args.ack_timeout_ms)),
        inter_packet_delay=max(0.0, float(args.inter_packet_delay)),
        frame_delay=max(0.0, float(args.frame_delay)),
        connect_retries=max(1, int(args.connect_retries)),
        connect_retry_delay=max(0.0, float(args.connect_retry_delay)),
        python_bin=os.environ.get("PYTHON_BIN", "/usr/bin/python3"),
        replay_script=(workdir / "replay_from_pcap.py"),
        trofeo_script=(workdir / "trofeo_lcd.py"),
        trcc_static_script=(workdir / "scripts" / "trcc_static_image.py"),
        trcc_static_overlay_script=(workdir / "scripts" / "trcc_static_overlay_image.py"),
        trcc_animation_script=(workdir / "scripts" / "trcc_animated_image.py"),
        child_log_file=Path(args.child_log_file).expanduser(),
        themes_file=to_abs(workdir, str(args.themes_file)).resolve(),
        playlist_file=to_abs(workdir, str(args.playlist_file)).resolve(),
        display_backend=display_backend,
        trcc_bin=str(trcc_bin),
    )

    if not cfg.replay_script.exists():
        raise RuntimeError(f"Brak skryptu replay: {cfg.replay_script}")
    if not cfg.trofeo_script.exists():
        raise RuntimeError(f"Brak skryptu drivera: {cfg.trofeo_script}")
    if not cfg.trcc_static_script.exists():
        raise RuntimeError(f"Brak skryptu static worker: {cfg.trcc_static_script}")
    if not cfg.trcc_static_overlay_script.exists():
        raise RuntimeError(f"Brak skryptu static overlay worker: {cfg.trcc_static_overlay_script}")
    if not cfg.trcc_animation_script.exists():
        raise RuntimeError(f"Brak skryptu animation worker: {cfg.trcc_animation_script}")
    if not cfg.pcap_path.exists():
        raise RuntimeError(f"Brak pliku pcap: {cfg.pcap_path}")

    controller = ReplayController(cfg)
    controller.scan_capture()

    ApiHandler.controller = controller
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), ApiHandler)
    httpd.daemon_threads = True

    shutdown_once = threading.Event()

    def request_shutdown(reason: str) -> None:
        if shutdown_once.is_set():
            return
        shutdown_once.set()
        print(f"[{now_iso()}] {reason}, zamykam backend", flush=True)

        def _shutdown() -> None:
            try:
                controller.stop_playlist()
            except Exception:
                pass
            try:
                controller.stop_loop()
            finally:
                httpd.shutdown()

        threading.Thread(target=_shutdown, daemon=True).start()

    def shutdown_handler(_signum, _frame):
        request_shutdown("sygnał stop")

    ApiHandler.request_shutdown_cb = request_shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(
        f"[{now_iso()}] backend start http://{cfg.host}:{cfg.port} "
        f"pcap={cfg.pcap_path} frame={cfg.frame_index} frames={controller.frame_count}",
        flush=True,
    )

    if args.autostart:
        try:
            controller.start_loop()
        except Exception as exc:
            controller.last_error = f"autostart failed: {exc}"
            print(f"[{now_iso()}] autostart failed: {exc}", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        request_shutdown("keyboard interrupt")
    finally:
        controller.stop_playlist()
        controller.stop_loop()
        httpd.server_close()
        print(f"[{now_iso()}] backend stopped", flush=True)


if __name__ == "__main__":
    main()
