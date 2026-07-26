from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / "events-bridge"))
sys.path.insert(0, str(PACK / "profile"))

from bridge_core import (  # noqa: E402
    AgentBusWriter,
    BridgeConfig,
    BridgeError,
    handle_request,
    slack_signature,
)
from server import BoundedThreadingHTTPServer, Handler  # noqa: E402


class BridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "_AgentBus"
        state = Path(self.temp.name) / "state" / "events.sqlite3"
        self.config = BridgeConfig(
            signing_secret="synthetic-signing-secret",
            bot_user_id="UCHIEF123",
            team_id="TTEAM123",
            api_app_id="AAPP123",
            allowed_channel_ids=frozenset({"CALLOWED123"}),
            allowed_user_ids=frozenset({"UDC123"}),
            agentbus_root=root,
            state_db=state,
        )
        self.writer = AgentBusWriter(self.config)
        self.now = 1_785_080_000

    def tearDown(self) -> None:
        self.temp.cleanup()

    def payload(self, **event_overrides: object) -> dict[str, object]:
        event: dict[str, object] = {
            "type": "app_mention",
            "user": "UDC123",
            "channel": "CALLOWED123",
            "text": "<@UCHIEF123> synthetic request",
            "ts": "1785080000.123456",
        }
        event.update(event_overrides)
        return {
            "type": "event_callback",
            "team_id": "TTEAM123",
            "api_app_id": "AAPP123",
            "event_id": "EvSynthetic001",
            "event": event,
        }

    def request(self, payload: dict[str, object], *, timestamp: int | None = None):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        stamp = str(self.now if timestamp is None else timestamp)
        headers = {
            "X-Slack-Request-Timestamp": stamp,
            "X-Slack-Signature": slack_signature(self.config.signing_secret, stamp, raw),
        }
        return handle_request(
            self.config,
            headers,
            raw,
            now=self.now,
            writer=self.writer,
        )

    def test_valid_mention_is_atomic_and_deduplicated(self) -> None:
        status, first = self.request(self.payload())
        self.assertEqual(status, 200)
        self.assertEqual(first["status"], "delivered")
        self.assertNotIn("target", first)
        self.assertEqual(len(first["message_id"]), 32)
        status, second = self.request(self.payload())
        self.assertEqual(status, 200)
        self.assertEqual(second["status"], "duplicate")
        inbox = list((self.config.agentbus_root / "chief").glob("*.json"))
        self.assertEqual(len(inbox), 1)
        self.assertFalse(self.config.agentbus_root.joinpath("_log.jsonl").exists())
        message = json.loads(inbox[0].read_text())
        self.assertFalse(message["read"])
        self.assertTrue(message["action_needed"])
        self.assertEqual(message["source"]["event_id"], "EvSynthetic001")

    def test_concurrent_retry_storm_produces_one_delivery(self) -> None:
        payload = self.payload()
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(lambda _index: self.request(payload), range(100)))
        statuses = [result[1]["status"] for result in results]
        self.assertEqual(statuses.count("delivered"), 1)
        self.assertEqual(statuses.count("duplicate"), 99)
        self.assertEqual(
            len(list((self.config.agentbus_root / "chief").glob("*.json"))),
            1,
        )
        self.assertFalse(self.config.agentbus_root.joinpath("_log.jsonl").exists())

    def test_missing_delivered_target_is_reconstructed(self) -> None:
        payload = self.payload()
        _status, first = self.request(payload)
        target = next((self.config.agentbus_root / "chief").glob("*.json"))
        target.unlink()
        _status, replay = self.request(payload)
        self.assertEqual(first["status"], "delivered")
        self.assertEqual(replay["status"], "repaired")
        self.assertTrue(target.is_file())
        restored = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(restored["source"]["event_id"], "EvSynthetic001")

    def test_same_event_id_with_changed_body_fails_closed(self) -> None:
        self.request(self.payload())
        changed = self.payload(text="<@UCHIEF123> altered body")
        with self.assertRaisesRegex(BridgeError, "deterministic_target_collision"):
            self.request(changed)

    def test_http_partial_body_and_slow_body_are_bounded(self) -> None:
        def receive_all(client: socket.socket) -> bytes:
            chunks: list[bytes] = []
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)

        server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler, max_workers=2)
        server.config = self.config
        server.writer = self.writer
        server.connection_timeout_seconds = 0.2
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            address = server.server_address
            with socket.create_connection(address, timeout=2) as client:
                client.sendall(
                    b"POST /slack/events HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Content-Length: 100\r\n"
                    b"Connection: close\r\n\r\n{}"
                )
                client.shutdown(socket.SHUT_WR)
                response = receive_all(client)
            self.assertIn(b"400", response.split(b"\r\n", 1)[0])
            self.assertIn(b"incomplete_body", response)

            with socket.create_connection(address, timeout=2) as client:
                client.sendall(
                    b"POST /slack/events HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Content-Length: 100\r\n"
                    b"Connection: close\r\n\r\n{"
                )
                response = receive_all(client)
            self.assertIn(b"408", response.split(b"\r\n", 1)[0])
            self.assertIn(b"request_timeout", response)
            self.assertEqual(server.request_queue_size, 32)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_rejects_invalid_signature_and_replay_window(self) -> None:
        payload = self.payload()
        raw = json.dumps(payload, separators=(",", ":")).encode()
        with self.assertRaisesRegex(BridgeError, "invalid_signature"):
            handle_request(
                self.config,
                {
                    "X-Slack-Request-Timestamp": str(self.now),
                    "X-Slack-Signature": "v0=bad",
                },
                raw,
                now=self.now,
            )
        with self.assertRaisesRegex(BridgeError, "stale_request"):
            self.request(payload, timestamp=self.now - 301)
        self.assertEqual(list((self.config.agentbus_root / "chief").glob("*.json")), [])

    def test_rejects_wrong_identity_scope(self) -> None:
        mutations = [
            {"team_id": "TWRONG"},
            {"api_app_id": "AWRONG"},
            {"event": {**self.payload()["event"], "channel": "CWRONG"}},
            {"event": {**self.payload()["event"], "user": "UWRONG"}},
        ]
        for mutation in mutations:
            payload = self.payload()
            payload.update(mutation)
            with self.subTest(mutation=mutation):
                with self.assertRaises(BridgeError):
                    self.request(payload)
        self.assertEqual(list((self.config.agentbus_root / "chief").glob("*.json")), [])

    def test_strict_mention_and_bot_loop_filters(self) -> None:
        cases = [
            {"text": "synthetic request without mention"},
            {"bot_id": "BOTHER"},
            {"subtype": "bot_message"},
            {"user": "UCHIEF123"},
            {"type": "message"},
        ]
        for event_changes in cases:
            payload = self.payload(**event_changes)
            with self.subTest(event_changes=event_changes):
                with self.assertRaises(BridgeError) as caught:
                    self.request(payload)
                self.assertIn(caught.exception.status, {202, 403})
        self.assertEqual(list((self.config.agentbus_root / "chief").glob("*.json")), [])

    def test_url_verification_is_signed_and_scoped(self) -> None:
        payload = {
            "type": "url_verification",
            "team_id": "TTEAM123",
            "api_app_id": "AAPP123",
            "challenge": "synthetic-challenge",
        }
        status, response = self.request(payload)
        self.assertEqual(status, 200)
        self.assertEqual(response, {"challenge": "synthetic-challenge"})
        self.assertEqual(list((self.config.agentbus_root / "chief").glob("*.json")), [])

    def test_root_must_be_exact_agentbus_directory(self) -> None:
        with self.assertRaisesRegex(ValueError, "named _AgentBus"):
            BridgeConfig.from_env(
                {
                    "CHIEF_SLACK_SIGNING_SECRET": "x",
                    "CHIEF_SLACK_BOT_USER_ID": "UCHIEF123",
                    "CHIEF_SLACK_TEAM_ID": "TTEAM123",
                    "CHIEF_SLACK_API_APP_ID": "AAPP123",
                    "CHIEF_SLACK_ALLOWED_CHANNEL_IDS": "CALLOWED123",
                    "CHIEF_SLACK_ALLOWED_USER_IDS": "UDC123",
                    "CHIEF_AGENTBUS_ROOT": str(Path(self.temp.name) / "wrong"),
                }
            )


if __name__ == "__main__":
    unittest.main()
