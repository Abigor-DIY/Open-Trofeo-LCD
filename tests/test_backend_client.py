import io
import socket
import unittest
import urllib.error
from unittest.mock import patch

from backend_client import BackendClient


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._body


class BackendClientTests(unittest.TestCase):
    def test_request_normalizes_url_and_decodes_json_response(self) -> None:
        client = BackendClient("http://127.0.0.1:18777/")

        with patch("backend_client.urllib.request.urlopen", return_value=_FakeResponse(b'{"ok": true}')) as urlopen:
            result = client.request("post", "v1/status", {"name": "Zażółć"}, timeout=3.0)

        request = urlopen.call_args.args[0]
        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.full_url, "http://127.0.0.1:18777/v1/status")
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("Zażółć".encode("utf-8"), request.data)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 3.0)

    def test_request_extracts_json_http_error_message(self) -> None:
        client = BackendClient("http://127.0.0.1:18777")
        error = urllib.error.HTTPError(
            "http://127.0.0.1:18777/v1/apply",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error": "bad payload"}'),
        )

        with patch("backend_client.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 400: bad payload"):
                client.request("POST", "/v1/apply", {})

    def test_request_turns_socket_timeout_into_runtime_error(self) -> None:
        client = BackendClient("http://127.0.0.1:18777")

        with patch("backend_client.urllib.request.urlopen", side_effect=socket.timeout):
            with self.assertRaisesRegex(RuntimeError, "Request timeout"):
                client.request("GET", "/v1/status")


if __name__ == "__main__":
    unittest.main()
