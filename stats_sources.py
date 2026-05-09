#!/usr/bin/env python3
"""
System statistics sources for Open Trofeo LCD themes.
"""

from __future__ import annotations

import os
import subprocess
import time
import re
import shutil
import threading
import hashlib
import json
import mimetypes
from urllib.parse import unquote, urlparse, urlencode
from urllib.request import Request, urlopen
from dataclasses import dataclass


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.0f}%"


def _parse_proc_stat():
    total = None
    cores = []

    with open("/proc/stat", "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("cpu"):
                break
            parts = line.split()
            if len(parts) < 5:
                continue
            label = parts[0]
            values = [int(x) for x in parts[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            busy = sum(values) - idle
            pair = (busy, idle)
            if label == "cpu":
                total = pair
            elif label.startswith("cpu") and label[3:].isdigit():
                cores.append(pair)

    return total, cores


@dataclass
class StatsSnapshot:
    values: dict[str, str]


class StatsProvider:
    def __init__(self) -> None:
        self._cpu_snapshot = None
        self._cpu_core_snapshot = None
        self._net_io_snapshot = (time.time(), 0, 0)
        self._gpu_type = self._detect_gpu_type()
        self._last_media_snapshot = self._default_media_snapshot()
        self._last_media_at = 0.0
        self._ffmpeg_bin = shutil.which("ffmpeg")
        self._media_cover_cache: dict[str, str] = {}
        self._media_cover_failures: dict[str, float] = {}
        self._public_api_lock = threading.Lock()
        self._musicbrainz_last_request_at = 0.0
        self._media_frame_cache: dict[str, str] = {}
        self._media_frame_jobs: set[str] = set()
        self._media_frame_failures: dict[str, float] = {}
        self._media_frame_lock = threading.Lock()
        self._media_frame_runtime_dir = os.path.join(
            os.path.expanduser("~/.local/state/open-trofeo-lcd/runtime"),
            "media-video-frames",
        )
        self._media_cover_runtime_dir = os.path.join(
            os.path.expanduser("~/.local/state/open-trofeo-lcd/runtime"),
            "media-covers",
        )

    @staticmethod
    def _default_media_snapshot() -> dict[str, str]:
        return {
            "media_title": "N/A",
            "media_artist": "N/A",
            "media_album": "N/A",
            "media_app": "N/A",
            "media_state": "stopped",
            "media_cover_path": "",
            "media_video_frame_path": "",
            "media_source_url": "",
        }

    @staticmethod
    def _media_priority(player_name: str, state: str, title: str) -> tuple[int, int, int]:
        p = player_name.lower()
        state_score = 3 if state == "playing" else (2 if state == "paused" else 1)
        source_score = 1
        if "spotify" in p:
            source_score = 5
        elif any(x in p for x in ("chrom", "brave", "edge", "firefox", "opera", "vivaldi")):
            source_score = 4
        elif "youtube" in p or "ytmusic" in p:
            source_score = 4
        title_score = 1 if title else 0
        return state_score, source_score, title_score

    @staticmethod
    def _cleanup_media_artist(value: str) -> str:
        text = value.strip()
        if not text:
            return ""
        if text.startswith("[") and text.endswith("]"):
            text = text.strip("[]")
            text = re.sub(r"[\"']", "", text)
        text = re.sub(r"\s*,\s*", ", ", text)
        return text.strip()

    @staticmethod
    def _is_browser_player(player_name: str) -> bool:
        player = player_name.strip().lower()
        return any(token in player for token in ("chrom", "brave", "edge", "firefox", "opera", "vivaldi"))

    def is_browser_media_player(self, player_name: str) -> bool:
        return self._is_browser_player(player_name)

    @staticmethod
    def _normalize_media_cover_path(raw_path: str) -> str:
        art_url = str(raw_path).strip()
        if not art_url:
            return ""
        parsed = urlparse(art_url)
        if parsed.scheme == "file":
            cover_path = unquote(parsed.path)
            if cover_path and os.path.exists(cover_path):
                return cover_path
            return ""
        if os.path.exists(art_url):
            return art_url
        return ""

    def _copy_media_cover_to_runtime(self, cover_path: str, stable_key: str = "") -> str:
        os.makedirs(self._media_cover_runtime_dir, exist_ok=True)
        stat = os.stat(cover_path)
        source_key = hashlib.sha1(
            f"{os.path.abspath(cover_path)}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
        ).hexdigest()
        runtime_key = stable_key.strip() or source_key
        suffix = os.path.splitext(cover_path)[1].lower() or ".img"
        out_path = os.path.join(self._media_cover_runtime_dir, f"{runtime_key}{suffix}")
        cached = self._media_cover_cache.get(runtime_key, "") or self._media_cover_cache.get(source_key, "")
        if cached and os.path.exists(cached):
            return cached
        if not os.path.exists(out_path):
            shutil.copyfile(cover_path, out_path)
        self._media_cover_cache[runtime_key] = out_path
        self._media_cover_cache[source_key] = out_path
        return out_path

    def _cached_cover_for_key(self, cache_key: str) -> str:
        cached = self._media_cover_cache.get(cache_key, "")
        if cached and os.path.exists(cached):
            return cached
        try:
            if not os.path.isdir(self._media_cover_runtime_dir):
                return ""
            prefix = f"{cache_key}."
            for name in os.listdir(self._media_cover_runtime_dir):
                if not name.startswith(prefix):
                    continue
                candidate = os.path.join(self._media_cover_runtime_dir, name)
                if os.path.isfile(candidate):
                    self._media_cover_cache[cache_key] = candidate
                    return candidate
        except Exception:
            return ""
        return ""

    @staticmethod
    def _cover_lookup_key(player_name: str, title: str, artist: str, album: str) -> str:
        raw = "\n".join(part.strip().lower() for part in (player_name, title, artist, album))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _cover_lookup_score(result: dict[str, object], title: str, artist: str, album: str) -> int:
        def _norm(value: object) -> str:
            return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

        title_q = _norm(title)
        artist_q = _norm(artist)
        album_q = _norm(album)
        title_r = _norm(result.get("trackName", ""))
        artist_r = _norm(result.get("artistName", ""))
        album_r = _norm(result.get("collectionName", ""))

        score = 0
        if title_q:
            if title_q == title_r:
                score += 8
            elif title_q in title_r or title_r in title_q:
                score += 5
        if artist_q:
            if artist_q == artist_r:
                score += 6
            elif artist_q in artist_r or artist_r in artist_q:
                score += 4
        if album_q:
            if album_q == album_r:
                score += 3
            elif album_q in album_r or album_r in album_q:
                score += 2
        return score

    def _download_cover_bytes(self, image_url: str, cache_key: str) -> str:
        req = Request(image_url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
        with urlopen(req, timeout=2.5) as response:
            payload = response.read()
            content_type = response.headers.get_content_type()
        if not payload:
            raise RuntimeError("empty-cover-payload")
        os.makedirs(self._media_cover_runtime_dir, exist_ok=True)
        suffix = mimetypes.guess_extension(content_type or "") or os.path.splitext(urlparse(image_url).path)[1].lower() or ".img"
        if suffix == ".jpe":
            suffix = ".jpg"
        out_path = os.path.join(self._media_cover_runtime_dir, f"{cache_key}{suffix}")
        tmp_path = f"{out_path}.tmp"
        with open(tmp_path, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, out_path)
        self._media_cover_cache[cache_key] = out_path
        self._media_cover_failures.pop(cache_key, None)
        return out_path

    def _rate_limit_musicbrainz(self) -> None:
        with self._public_api_lock:
            now = time.time()
            wait_s = 1.05 - (now - self._musicbrainz_last_request_at)
            if wait_s > 0:
                time.sleep(wait_s)
            self._musicbrainz_last_request_at = time.time()

    def _resolve_musicbrainz_cover_path(self, cache_key: str, title: str, artist: str, album: str) -> str:
        query_parts = [part.strip() for part in (artist, album or title) if part and part.strip() and part.strip() != "N/A"]
        if len(query_parts) < 2:
            return ""

        mb_query = []
        if artist and artist != "N/A":
            mb_query.append(f'artist:"{artist}"')
        if album and album != "N/A":
            mb_query.append(f'release:"{album}"')
        elif title and title != "N/A":
            mb_query.append(f'release:"{title}"')
        if not mb_query:
            return ""

        search_url = "https://musicbrainz.org/ws/2/release/?" + urlencode(
            {
                "query": " AND ".join(mb_query),
                "fmt": "json",
                "limit": "5",
            }
        )

        try:
            self._rate_limit_musicbrainz()
            req = Request(search_url, headers={"User-Agent": "OpenTrofeoLCD/1.0 (media-cover-fallback)"})
            with urlopen(req, timeout=2.5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            return ""

        releases = payload.get("releases", [])
        if not isinstance(releases, list):
            return ""

        best_id = ""
        best_score = -1
        for release in releases:
            if not isinstance(release, dict):
                continue
            artist_credit = release.get("artist-credit", [])
            if isinstance(artist_credit, list):
                artist_name = " ".join(
                    str(item.get("name", ""))
                    for item in artist_credit
                    if isinstance(item, dict)
                ).strip()
            else:
                artist_name = ""
            candidate = {
                "trackName": title,
                "artistName": artist_name,
                "collectionName": release.get("title", ""),
            }
            score = self._cover_lookup_score(candidate, title or album, artist, album or title)
            release_id = str(release.get("id", "")).strip()
            if release_id and score > best_score:
                best_score = score
                best_id = release_id

        if not best_id or best_score <= 0:
            return ""

        image_url = f"https://coverartarchive.org/release/{best_id}/front-500"
        try:
            self._rate_limit_musicbrainz()
            return self._download_cover_bytes(image_url, cache_key)
        except Exception:
            return ""

    def _resolve_deezer_cover_path(self, cache_key: str, title: str, artist: str, album: str) -> str:
        queries = []
        artist_clean = artist.strip()
        title_clean = title.strip()
        album_clean = album.strip()
        if artist_clean and title_clean and artist_clean != "N/A" and title_clean != "N/A":
            queries.append(f'artist:"{artist_clean}" track:"{title_clean}"')
        plain_parts = [part for part in (artist_clean, title_clean, album_clean) if part and part != "N/A"]
        if plain_parts:
            queries.append(" ".join(plain_parts))

        for query in queries:
            search_url = "https://api.deezer.com/search/track?" + urlencode({"q": query})
            try:
                req = Request(search_url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
                with urlopen(req, timeout=2.5) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except Exception:
                continue

            results = payload.get("data", [])
            if not isinstance(results, list):
                continue

            best_url = ""
            best_score = -1
            for result in results:
                if not isinstance(result, dict):
                    continue
                artist_obj = result.get("artist", {})
                album_obj = result.get("album", {})
                candidate = {
                    "trackName": result.get("title", ""),
                    "artistName": artist_obj.get("name", "") if isinstance(artist_obj, dict) else "",
                    "collectionName": album_obj.get("title", "") if isinstance(album_obj, dict) else "",
                }
                score = self._cover_lookup_score(candidate, title, artist, album)
                if score <= 0 or not isinstance(album_obj, dict):
                    continue
                image_url = str(
                    album_obj.get("cover_xl")
                    or album_obj.get("cover_big")
                    or album_obj.get("cover_medium")
                    or album_obj.get("cover")
                    or ""
                ).strip()
                if image_url and score > best_score:
                    best_score = score
                    best_url = image_url

            if best_url:
                try:
                    return self._download_cover_bytes(best_url, cache_key)
                except Exception:
                    continue
        return ""

    def _resolve_browser_cover_path(self, player_name: str, title: str, artist: str, album: str) -> str:
        if not self._is_browser_player(player_name):
            return ""

        query_parts = [part.strip() for part in (artist, title, album) if part and part.strip() and part.strip() != "N/A"]
        if not query_parts:
            return ""

        cache_key = self._cover_lookup_key(player_name, title, artist, album)
        cached = self._cached_cover_for_key(cache_key)
        if cached:
            return cached

        last_failure = float(self._media_cover_failures.get(cache_key, 0.0))
        if last_failure and (time.time() - last_failure) < 1800.0:
            return ""

        itunes_search_url = "https://itunes.apple.com/search?" + urlencode(
            {
                "term": " ".join(query_parts),
                "media": "music",
                "entity": "song",
                "limit": "5",
            }
        )
        try:
            req = Request(itunes_search_url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
            with urlopen(req, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            payload = {}

        results = payload.get("results", [])
        if isinstance(results, list):
            best_url = ""
            best_score = -1
            for result in results:
                if not isinstance(result, dict):
                    continue
                art_url = str(result.get("artworkUrl100") or result.get("artworkUrl60") or "").strip()
                if not art_url:
                    continue
                score = self._cover_lookup_score(result, title, artist, album)
                if score > best_score:
                    best_score = score
                    best_url = art_url

            if best_url and best_score > 0:
                best_url = re.sub(r"/\d+x\d+bb\.", "/600x600bb.", best_url)
                try:
                    return self._download_cover_bytes(best_url, cache_key)
                except Exception:
                    pass

        musicbrainz_cover = self._resolve_musicbrainz_cover_path(cache_key, title, artist, album)
        if musicbrainz_cover:
            return musicbrainz_cover

        deezer_cover = self._resolve_deezer_cover_path(cache_key, title, artist, album)
        if deezer_cover:
            return deezer_cover

        self._media_cover_failures[cache_key] = time.time()
        return ""

    def resolve_media_cover_path(
        self,
        raw_path: str,
        *,
        player_name: str = "",
        title: str = "",
        artist: str = "",
        album: str = "",
    ) -> str:
        cover_path = self._normalize_media_cover_path(raw_path)
        if cover_path:
            try:
                stable_key = ""
                if any(part and part != "N/A" for part in (title, artist, album)):
                    stable_key = self._cover_lookup_key(player_name, title, artist, album)
                return self._copy_media_cover_to_runtime(cover_path, stable_key=stable_key)
            except Exception:
                return cover_path
        return self._resolve_browser_cover_path(player_name, title, artist, album)

    @staticmethod
    def _normalize_media_source_path(raw_url: str) -> str:
        media_url = str(raw_url).strip()
        if not media_url:
            return ""
        parsed = urlparse(media_url)
        if parsed.scheme == "file":
            media_path = unquote(parsed.path)
            if media_path and os.path.exists(media_path):
                return media_path
            return ""
        if parsed.scheme:
            return ""
        if os.path.exists(media_url):
            return media_url
        return ""

    @staticmethod
    def _is_local_video_path(path: str) -> bool:
        if not path:
            return False
        ext = os.path.splitext(path)[1].lower()
        return ext in {
            ".mp4",
            ".m4v",
            ".mkv",
            ".webm",
            ".avi",
            ".mov",
            ".mpg",
            ".mpeg",
            ".wmv",
            ".flv",
            ".ts",
            ".m2ts",
        }

    def _media_frame_cache_key(self, media_path: str) -> str:
        try:
            stat = os.stat(media_path)
            raw = f"{os.path.abspath(media_path)}:{stat.st_mtime_ns}:{stat.st_size}"
        except Exception:
            raw = os.path.abspath(media_path)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _extract_media_video_frame(self, media_path: str, cache_key: str) -> None:
        try:
            os.makedirs(self._media_frame_runtime_dir, exist_ok=True)
            out_path = os.path.join(self._media_frame_runtime_dir, f"{cache_key}.jpg")
            tmp_path = os.path.join(self._media_frame_runtime_dir, f"{cache_key}.tmp.jpg")
            cmd = [
                str(self._ffmpeg_bin),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                "00:00:01",
                "-i",
                media_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=960:-2:force_original_aspect_ratio=decrease",
                tmp_path,
            ]
            proc = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3.0,
                check=False,
            )
            if proc.returncode == 0 and os.path.exists(tmp_path):
                os.replace(tmp_path, out_path)
                with self._media_frame_lock:
                    self._media_frame_cache[cache_key] = out_path
                    self._media_frame_failures.pop(cache_key, None)
            elif os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        finally:
            with self._media_frame_lock:
                if cache_key not in self._media_frame_cache:
                    self._media_frame_failures[cache_key] = time.time()
                self._media_frame_jobs.discard(cache_key)

    def resolve_media_video_frame_path(self, raw_url: str, fallback_cover_path: str = "") -> str:
        fallback = str(fallback_cover_path).strip()
        media_path = self._normalize_media_source_path(raw_url)
        if not media_path or not self._is_local_video_path(media_path) or not self._ffmpeg_bin:
            return fallback
        cache_key = self._media_frame_cache_key(media_path)
        with self._media_frame_lock:
            cached = self._media_frame_cache.get(cache_key, "")
            if cached and os.path.exists(cached):
                return cached
            last_failure = float(self._media_frame_failures.get(cache_key, 0.0))
            if last_failure and (time.time() - last_failure) < 30.0:
                return fallback
            if cache_key not in self._media_frame_jobs:
                self._media_frame_jobs.add(cache_key)
                threading.Thread(
                    target=self._extract_media_video_frame,
                    args=(media_path, cache_key),
                    daemon=True,
                ).start()
        return fallback

    def should_disable_browser_video_frame(self, player_name: str, raw_url: str) -> bool:
        if not self._is_browser_player(player_name):
            return False
        media_path = self._normalize_media_source_path(raw_url)
        return not media_path or not self._is_local_video_path(media_path)

    def _detect_gpu_type(self) -> str | None:
        if os.path.exists("/usr/bin/nvidia-smi"):
            return "nvidia"
        for i in range(4):
            if os.path.exists(f"/sys/class/drm/card{i}/device/hwmon"):
                return f"amd{i}"
        return None

    def read_local_ip(self) -> str:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def read_disk_usage(self) -> tuple[int, int, int] | None:
        try:
            st = os.statvfs("/")
            total = (st.f_blocks * st.f_frsize) // (1024 * 1024 * 1024)
            free = (st.f_bfree * st.f_frsize) // (1024 * 1024 * 1024)
            used = total - free
            percent = int((used * 100) // total) if total > 0 else 0
            return used, total, percent
        except Exception:
            return None

    def read_net_speeds(self) -> tuple[float, float]:
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()
            total_recv = 0
            total_sent = 0
            for line in lines[2:]:
                parts = line.split()
                if len(parts) > 9:
                    total_recv += int(parts[1])
                    total_sent += int(parts[9])
            now = time.time()
            prev_time, prev_recv, prev_sent = self._net_io_snapshot
            self._net_io_snapshot = (now, total_recv, total_sent)
            dt = now - prev_time
            if dt <= 0: return 0.0, 0.0
            return (total_recv - prev_recv) / 1024.0 / dt, (total_sent - prev_sent) / 1024.0 / dt
        except Exception:
            return 0.0, 0.0

    def read_gpu_stats(self) -> dict[str, str]:
        stats = {
            "gpu_name": "N/A", "gpu_temp": "N/A", "gpu_load": "N/A",
            "vram_used_mb": "N/A", "vram_total_mb": "N/A", "vram_percent": "N/A"
        }
        if self._gpu_type == "nvidia":
            try:
                cmd = ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]
                out = subprocess.check_output(cmd, encoding="utf-8").strip().split(", ")
                if len(out) >= 5:
                    stats.update({
                        "gpu_name": out[0], "gpu_temp": f"{out[1]}°C", "gpu_load": f"{out[2]}%",
                        "vram_used_mb": out[3], "vram_total_mb": out[4],
                        "vram_percent": f"{int(float(out[3])*100/float(out[4]))}%"
                    })
            except Exception: pass
        return stats

    def read_cpu_usage_percent(self) -> str:
        current_total, _ = _parse_proc_stat()
        if current_total is None:
            return "N/A"

        prev = self._cpu_snapshot
        self._cpu_snapshot = current_total
        if prev is None:
            return "N/A"

        busy_delta = current_total[0] - prev[0]
        idle_delta = current_total[1] - prev[1]
        total_delta = busy_delta + idle_delta
        if total_delta <= 0:
            return "N/A"
        return f"{(busy_delta * 100.0 / total_delta):.0f}%"

    def read_cpu_core_summary(self) -> tuple[float, float, int] | None:
        _, current_cores = _parse_proc_stat()
        if not current_cores:
            return None

        prev = self._cpu_core_snapshot
        self._cpu_core_snapshot = current_cores
        if prev is None or len(prev) != len(current_cores):
            return None

        usages = []
        for old_pair, new_pair in zip(prev, current_cores):
            busy_delta = new_pair[0] - old_pair[0]
            idle_delta = new_pair[1] - old_pair[1]
            total_delta = busy_delta + idle_delta
            if total_delta > 0:
                usages.append(busy_delta * 100.0 / total_delta)

        if not usages:
            return None

        return sum(usages) / len(usages), max(usages), len(usages)

    def read_load_average(self) -> str:
        try:
            with open("/proc/loadavg", "r", encoding="utf-8") as handle:
                parts = handle.read().split()
            if len(parts) >= 3:
                return f"{parts[0]}/{parts[1]}/{parts[2]}"
        except Exception:
            pass
        return "N/A"

    def read_cpu_freq_ghz(self) -> str:
        try:
            freqs = []
            with open("/proc/cpuinfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith("cpu mhz"):
                        value = float(line.split(":", 1)[1].strip())
                        freqs.append(value)
            if freqs:
                avg_mhz = sum(freqs) / len(freqs)
                return f"{avg_mhz / 1000.0:.2f} GHz"
        except Exception:
            pass
        return "N/A"

    def read_cpu_temperature(self) -> str:
        candidates = []

        try:
            for zone in os.listdir("/sys/class/thermal"):
                if not zone.startswith("thermal_zone"):
                    continue
                base = f"/sys/class/thermal/{zone}"
                temp_path = f"{base}/temp"
                type_path = f"{base}/type"
                if not os.path.exists(temp_path):
                    continue
                try:
                    with open(temp_path, "r", encoding="utf-8") as handle:
                        raw = int(handle.read().strip())
                    celsius = raw / 1000.0 if raw > 1000 else float(raw)
                    if not (10.0 <= celsius <= 120.0):
                        continue
                    label = ""
                    if os.path.exists(type_path):
                        with open(type_path, "r", encoding="utf-8") as handle:
                            label = handle.read().strip().lower()
                    score = 0
                    if any(x in label for x in ("cpu", "x86_pkg_temp", "package", "tctl", "tdie")):
                        score = 2
                    elif label:
                        score = 1
                    candidates.append((score, celsius))
                except Exception:
                    continue
        except Exception:
            pass

        try:
            for hw in os.listdir("/sys/class/hwmon"):
                base = f"/sys/class/hwmon/{hw}"
                for entry in os.listdir(base):
                    if not entry.startswith("temp") or not entry.endswith("_input"):
                        continue
                    temp_path = f"{base}/{entry}"
                    label_path = f"{base}/{entry[:-6]}_label"
                    try:
                        with open(temp_path, "r", encoding="utf-8") as handle:
                            raw = int(handle.read().strip())
                        celsius = raw / 1000.0 if raw > 1000 else float(raw)
                        if not (10.0 <= celsius <= 120.0):
                            continue
                        label = ""
                        if os.path.exists(label_path):
                            with open(label_path, "r", encoding="utf-8") as handle:
                                label = handle.read().strip().lower()
                        score = 0
                        if any(x in label for x in ("cpu", "package", "tctl", "tdie")):
                            score = 3
                        elif label:
                            score = 1
                        candidates.append((score, celsius))
                    except Exception:
                        continue
        except Exception:
            pass

        if not candidates:
            return "N/A"

        best = sorted(candidates, key=lambda x: (x[0], x[1]), reverse=True)[0][1]
        return f"{best:.0f}°C"

    def _read_meminfo(self) -> tuple[int, int, int] | None:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                lines = handle.readlines()
            total_mb = int(lines[0].split()[1]) // 1024
            avail_mb = int(lines[2].split()[1]) // 1024
            used_mb = total_mb - avail_mb
            return used_mb, total_mb, int((used_mb * 100) // total_mb) if total_mb > 0 else 0
        except Exception:
            return None

    def _read_uptime(self) -> tuple[int, int] | None:
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as handle:
                uptime_sec = float(handle.read().split()[0])
            hours = int(uptime_sec // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            return hours, minutes
        except Exception:
            return None

    def _read_media_now_playing(self) -> dict[str, str]:
        out = self._default_media_snapshot()
        if not os.path.exists("/usr/bin/playerctl"):
            return out

        try:
            payload = subprocess.check_output(
                [
                    "playerctl",
                    "-a",
                    "metadata",
                    "--format",
                    "{{playerName}}\t{{status}}\t{{xesam:title}}\t{{xesam:artist}}\t{{mpris:artUrl}}\t{{xesam:url}}\t{{xesam:album}}",
                ],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
                timeout=0.6,
            ).strip()
            if payload:
                best = None
                for line in payload.splitlines():
                    parts = line.split("\t")
                    player = parts[0].strip() if len(parts) > 0 else ""
                    state = parts[1].strip().lower() if len(parts) > 1 else "stopped"
                    title = parts[2].strip() if len(parts) > 2 else ""
                    artist = self._cleanup_media_artist(parts[3] if len(parts) > 3 else "")
                    art_url = parts[4].strip() if len(parts) > 4 else ""
                    media_url = parts[5].strip() if len(parts) > 5 else ""
                    album = parts[6].strip() if len(parts) > 6 else ""
                    score = self._media_priority(player, state, title)
                    row = (score, player, state, title, artist, art_url, media_url, album)
                    if best is None or row[0] > best[0]:
                        best = row
                if best is not None:
                    _score, player, state, title, artist, art_url, media_url, album = best
                    out["media_state"] = state or "stopped"
                    if player:
                        out["media_app"] = player
                    if title:
                        out["media_title"] = title
                    if artist:
                        out["media_artist"] = artist
                    if album:
                        out["media_album"] = album
                    if media_url:
                        out["media_source_url"] = media_url
                    out["media_cover_path"] = self.resolve_media_cover_path(
                        art_url,
                        player_name=player,
                        title=title,
                        artist=artist,
                        album=album,
                    )
                    out["media_video_frame_path"] = self.resolve_media_video_frame_path(
                        out.get("media_source_url", ""),
                        out["media_cover_path"],
                    )
                    if title or artist:
                        self._last_media_snapshot = dict(out)
                        self._last_media_at = time.time()
                    return out
        except Exception:
            pass
        try:
            payload = subprocess.check_output(
                ["playerctl", "-a", "status", "--format", "{{playerName}}\t{{status}}"],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
                timeout=0.35,
            )
            best = None
            for line in payload.strip().splitlines():
                parts = line.split("\t")
                player = parts[0].strip() if len(parts) > 0 else ""
                state = parts[1].strip().lower() if len(parts) > 1 else "stopped"
                score = self._media_priority(player, state, "")
                row = (score, player, state)
                if best is None or row[0] > best[0]:
                    best = row
            if best is not None:
                _score, player, state = best
                out["media_state"] = state or "stopped"
                if player:
                    out["media_app"] = player
        except Exception:
            pass
        if out["media_state"] in {"playing", "paused"} and (time.time() - self._last_media_at) <= 600.0:
            fallback = dict(self._last_media_snapshot)
            if fallback.get("media_title") and fallback["media_title"] != "N/A":
                out["media_title"] = fallback["media_title"]
            if fallback.get("media_artist"):
                out["media_artist"] = fallback["media_artist"]
            if fallback.get("media_cover_path"):
                out["media_cover_path"] = fallback["media_cover_path"]
            if fallback.get("media_video_frame_path"):
                out["media_video_frame_path"] = fallback["media_video_frame_path"]
            if fallback.get("media_source_url"):
                out["media_source_url"] = fallback["media_source_url"]
            if out["media_app"] == "N/A" and fallback.get("media_app"):
                out["media_app"] = fallback["media_app"]
        return out

    def snapshot(self) -> StatsSnapshot:
        now = time.localtime()
        core_summary = self.read_cpu_core_summary()
        mem = self._read_meminfo()
        uptime = self._read_uptime()
        disk = self.read_disk_usage()
        dl_speed, ul_speed = self.read_net_speeds()
        gpu = self.read_gpu_stats()
        media = self._read_media_now_playing()

        values = {
            "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
            "ip_local": self.read_local_ip(),
            "time_hms": time.strftime("%H:%M:%S", now),
            "date_ymd": time.strftime("%Y-%m-%d", now),
            "cpu_usage_percent": self.read_cpu_usage_percent(),
            "cpu_core_avg_percent": _format_percent(None if core_summary is None else core_summary[0]),
            "cpu_core_max_percent": _format_percent(None if core_summary is None else core_summary[1]),
            "cpu_core_count": "N/A" if core_summary is None else str(core_summary[2]),
            "cpu_freq_ghz": self.read_cpu_freq_ghz(),
            "cpu_temp_c": self.read_cpu_temperature(),
            "load_average": self.read_load_average(),
            "mem_used_mb": "N/A" if mem is None else str(mem[0]),
            "mem_total_mb": "N/A" if mem is None else str(mem[1]),
            "mem_percent": "N/A" if mem is None else f"{mem[2]}%",
            "disk_used_gb": "N/A" if disk is None else str(disk[0]),
            "disk_total_gb": "N/A" if disk is None else str(disk[1]),
            "disk_percent": "N/A" if disk is None else f"{disk[2]}%",
            "net_dl_kbps": f"{dl_speed:.1f} KB/s",
            "net_ul_kbps": f"{ul_speed:.1f} KB/s",
            "uptime_human": "N/A" if uptime is None else f"{uptime[0]}h {uptime[1]}m",
            **gpu,
            **media,
        }
        return StatsSnapshot(values=values)
