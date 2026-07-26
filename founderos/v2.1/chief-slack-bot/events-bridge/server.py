#!/usr/bin/env python3
"""Loopback-only Slack Events API receiver for the CHIEF relay."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROFILE_LIB = HERE.parent / "lib"
if str(PROFILE_LIB) not in sys.path:
    sys.path.insert(0, str(PROFILE_LIB))

from envfile import load_env_file  # noqa: E402

from bridge_core import (  # noqa: E402
    MAX_BODY_BYTES,
    AgentBusWriter,
    BridgeConfig,
    BridgeError,
    handle_request,
)


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, *args: Any, max_workers: int = 16, **kwargs: Any):
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        self.connection_timeout_seconds = 5.0
        self._worker_slots = threading.BoundedSemaphore(max_workers)
        super().__init__(*args, **kwargs)

    def process_request(self, request: Any, client_address: Any) -> None:
        self._worker_slots.acquire()
        try:
            super().process_request(request, client_address)
        except Exception:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "FounderOS-Chief-Slack-Relay/1.0"
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(  # type: ignore[attr-defined]
            self.server.connection_timeout_seconds  # type: ignore[attr-defined]
        )

    def log_message(self, format: str, *args: Any) -> None:
        print(
            json.dumps(
                {
                    "event": "http",
                    "client": self.client_address[0],
                    "message": format % args,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self._write_json(404, {"ok": False, "error": "not_found"})
            return
        self._write_json(
            200,
            {"ok": True, "mode": "relay_only", "llm_routing": False},
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/slack/events":
            self._write_json(404, {"ok": False, "error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                raise BridgeError(400, "invalid_content_length")
            if content_length > MAX_BODY_BYTES:
                raise BridgeError(413, "body_too_large")
            raw_body = self.rfile.read(content_length)
            if len(raw_body) != content_length:
                raise BridgeError(400, "incomplete_body")
            status, payload = handle_request(
                self.server.config,  # type: ignore[attr-defined]
                {key: value for key, value in self.headers.items()},
                raw_body,
                writer=self.server.writer,  # type: ignore[attr-defined]
            )
        except (socket.timeout, TimeoutError):
            self._write_json(408, {"ok": False, "error": "request_timeout"})
            return
        except (ValueError, BridgeError) as exc:
            status = exc.status if isinstance(exc, BridgeError) else 400
            code = exc.code if isinstance(exc, BridgeError) else "invalid_request"
            self._write_json(status, {"ok": False, "error": code})
            return
        except Exception:
            self._write_json(500, {"ok": False, "error": "internal_error"})
            return
        self._write_json(status, payload)


def main() -> int:
    env_path = Path(os.environ.get("HERMES_ROOT_ENV", "~/.hermes/.env")).expanduser()
    load_env_file(env_path)
    config = BridgeConfig.from_env()
    port = int(os.environ.get("CHIEF_SLACK_EVENTS_PORT", "18793"))
    if not 1024 <= port <= 65535:
        raise ValueError("CHIEF_SLACK_EVENTS_PORT must be between 1024 and 65535")
    server = BoundedThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.config = config  # type: ignore[attr-defined]
    server.writer = AgentBusWriter(config)  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "event": "started",
                "bind": "127.0.0.1",
                "port": port,
                "mode": "relay_only",
                "llm_routing": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
