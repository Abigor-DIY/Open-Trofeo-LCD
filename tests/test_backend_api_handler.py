import io
import json
import unittest
from email.message import Message
from typing import Any

from trofeo_backend import ApiHandler


class _DummyController:
    def __init__(self) -> None:
        self.loaded_path = ""
        self.saved_theme: tuple[str, dict[str, Any]] | None = None
        self.preview_request: dict[str, Any] | None = None
        self.apply_request: dict[str, Any] | None = None
        self.saved_bundle_path = ""
        self.loaded_bundle: tuple[str, bool] | None = None

    def status(self) -> dict[str, Any]:
        return {"ok": True, "mode": "test"}

    def get_theme_schema(self) -> dict[str, Any]:
        return {"schema_version": 1, "stat_sources": []}

    def list_themes(self) -> dict[str, Any]:
        return {"count": 0, "items": []}

    def list_playlist(self) -> dict[str, Any]:
        return {"count": 0, "items": []}

    def build_bundle(self) -> dict[str, Any]:
        return {"themes": {}, "playlist": []}

    def load_theme_doc(self, path: str) -> dict[str, Any]:
        self.loaded_path = path
        if ".." in path:
            raise RuntimeError("path escapes workdir")
        return {"path": path, "document": {}, "theme_name": "Test"}

    def save_theme_doc(self, path: str, document: dict[str, Any]) -> dict[str, Any]:
        self.saved_theme = (path, document)
        if ".." in path:
            raise RuntimeError("path escapes workdir")
        return {"path": path, "document": document, "theme_name": "Saved"}

    def render_theme_preview(
        self,
        *,
        path: str | None,
        document: dict[str, Any] | None,
        include_image_base64: bool,
    ) -> dict[str, Any]:
        self.preview_request = {
            "path": path,
            "document": document,
            "include_image_base64": include_image_base64,
        }
        return {"image_path": "runtime/preview.png", "theme_name": "Preview"}

    def send_theme_doc(
        self,
        *,
        path: str | None,
        document: dict[str, Any] | None,
        timeout_s: float,
        resume_loop: bool,
    ) -> dict[str, Any]:
        self.apply_request = {
            "path": path,
            "document": document,
            "timeout_s": timeout_s,
            "resume_loop": resume_loop,
        }
        return {"applied": True}

    def save_bundle(self, path: str) -> dict[str, Any]:
        self.saved_bundle_path = path
        if ".." in path:
            raise RuntimeError("path escapes workdir")
        return {"path": path, "bytes": 42}

    def load_bundle(self, path: str, merge: bool = False) -> dict[str, Any]:
        self.loaded_bundle = (path, merge)
        if ".." in path:
            raise RuntimeError("path escapes workdir")
        return {"path": path, "merge": merge}


class _CapturingHandler(ApiHandler):
    def __init__(self, method_path: str, payload: dict[str, Any] | bytes | None = None) -> None:
        self.path = method_path
        self.rfile = io.BytesIO()
        self.wfile = io.BytesIO()
        self.headers = Message()
        self.response_code: int | None = None
        self.response_headers: dict[str, str] = {}
        if isinstance(payload, bytes):
            raw = payload
        elif payload is None:
            raw = b""
        else:
            raw = json.dumps(payload).encode("utf-8")
        self.rfile = io.BytesIO(raw)
        self.headers["Content-Length"] = str(len(raw))

    def send_response(self, code: int, message: str | None = None) -> None:  # type: ignore[override]
        self.response_code = code

    def send_header(self, keyword: str, value: str) -> None:  # type: ignore[override]
        self.response_headers[keyword] = value

    def end_headers(self) -> None:  # type: ignore[override]
        return

    def json_body(self) -> dict[str, Any]:
        raw = self.wfile.getvalue().decode("utf-8")
        return json.loads(raw)


class BackendApiHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = _DummyController()
        previous_controller = ApiHandler.controller
        previous_shutdown = ApiHandler.request_shutdown_cb
        self.addCleanup(setattr, ApiHandler, "controller", previous_controller)
        self.addCleanup(setattr, ApiHandler, "request_shutdown_cb", previous_shutdown)
        ApiHandler.controller = self.controller
        ApiHandler.request_shutdown_cb = None

    def test_health_endpoint_returns_ok(self) -> None:
        handler = _CapturingHandler("/health")

        handler.do_GET()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "trofeo-backend")

    def test_theme_doc_load_validates_required_path(self) -> None:
        handler = _CapturingHandler("/v1/theme-doc/load", {})

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "path is required")

    def test_runtime_errors_are_returned_as_http_400(self) -> None:
        handler = _CapturingHandler("/v1/theme-doc/load", {"path": "../escape.json"})

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "path escapes workdir")

    def test_invalid_json_returns_http_400(self) -> None:
        handler = _CapturingHandler("/v1/theme-doc/load", b"{bad json")

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 400)
        self.assertFalse(body["ok"])
        self.assertIn("invalid-json", body["error"])

    def test_theme_doc_save_requires_path_and_document(self) -> None:
        handler = _CapturingHandler("/v1/theme-doc/save", {"path": "themes/test.json", "document": "bad"})

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 400)
        self.assertEqual(body["error"], "path and document(object) are required")

    def test_theme_doc_save_passes_document_to_controller(self) -> None:
        document = {"meta": {"name": "Saved"}}
        handler = _CapturingHandler("/v1/theme-doc/save", {"path": "themes/test.json", "document": document})

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(self.controller.saved_theme, ("themes/test.json", document))
        self.assertEqual(body["result"]["theme_name"], "Saved")

    def test_theme_doc_preview_accepts_document_without_path(self) -> None:
        document = {"meta": {"name": "Preview"}}
        handler = _CapturingHandler(
            "/v1/theme-doc/preview",
            {"document": document, "include_image_base64": True},
        )

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(
            self.controller.preview_request,
            {"path": None, "document": document, "include_image_base64": True},
        )

    def test_theme_doc_apply_passes_timeout_and_resume_flags(self) -> None:
        handler = _CapturingHandler(
            "/v1/theme-doc/apply",
            {"path": "themes/test.json", "timeout_s": 12.5, "resume_loop": True},
        )

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(
            self.controller.apply_request,
            {"path": "themes/test.json", "document": None, "timeout_s": 12.5, "resume_loop": True},
        )

    def test_bundle_save_and_load_validate_path(self) -> None:
        save_handler = _CapturingHandler("/v1/bundle/save", {"path": "bundles/test.json"})
        load_handler = _CapturingHandler("/v1/bundle/load", {"path": "bundles/test.json", "merge": True})

        save_handler.do_POST()
        load_handler.do_POST()

        self.assertEqual(save_handler.response_code, 200)
        self.assertEqual(save_handler.json_body()["result"]["bytes"], 42)
        self.assertEqual(self.controller.saved_bundle_path, "bundles/test.json")
        self.assertEqual(load_handler.response_code, 200)
        self.assertEqual(self.controller.loaded_bundle, ("bundles/test.json", True))

    def test_bundle_path_runtime_error_is_http_400(self) -> None:
        handler = _CapturingHandler("/v1/bundle/save", {"path": "../escape.json"})

        handler.do_POST()

        body = handler.json_body()
        self.assertEqual(handler.response_code, 400)
        self.assertEqual(body["error"], "path escapes workdir")


if __name__ == "__main__":
    unittest.main()
