"""Small HTTP client used by the Qt frontend to talk to the local backend."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any


class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        data = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(self._url(path), data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            err_text = body
            try:
                decoded = json.loads(body) if body else {}
                if isinstance(decoded, dict) and "error" in decoded:
                    err_text = str(decoded["error"])
            except Exception:
                pass
            raise RuntimeError(f"HTTP {exc.code}: {err_text}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Połączenie nieudane: {exc}") from exc
        except socket.timeout as exc:
            raise RuntimeError("Request timeout") from exc
