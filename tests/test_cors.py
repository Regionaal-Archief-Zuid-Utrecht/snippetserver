import asyncio
import os
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS": "https://ontwikkel.viewer.razu.nl"}):
    from main import app


async def preflight(origin):
    messages = []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "OPTIONS",
        "scheme": "http",
        "path": "/snippet",
        "raw_path": b"/snippet",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"origin", origin.encode()),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"Content-Type"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    headers = {
        key.decode().lower(): value.decode()
        for key, value in start["headers"]
    }
    return start["status"], headers


class CorsPreflightTests(unittest.TestCase):
    def test_allowed_origin_preflight(self):
        origin = "https://ontwikkel.viewer.razu.nl"

        status, headers = asyncio.run(preflight(origin))

        self.assertEqual(status, 200)
        self.assertEqual(headers["access-control-allow-origin"], origin)
        self.assertIn("POST", headers["access-control-allow-methods"])
        self.assertIn("Content-Type", headers["access-control-allow-headers"])

    def test_disallowed_origin_preflight(self):
        status, headers = asyncio.run(preflight("https://example.com"))

        self.assertEqual(status, 400)
        self.assertNotIn("access-control-allow-origin", headers)


if __name__ == "__main__":
    unittest.main()
