from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / "profile"))

from chief_slack_post import SlackError, post_message  # noqa: E402
from envfile import load_env_file, read_env_file  # noqa: E402
from upsert_env import has_key, upsert  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self.payload


class SenderAndEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = {
            "CHIEF_SLACK_BOT_TOKEN": "synthetic-token",
            "CHIEF_SLACK_BOT_USER_ID": "UCHIEF123",
            "CHIEF_SLACK_TEAM_ID": "TTEAM123",
            "CHIEF_SLACK_DEFAULT_CHANNEL_ID": "CALLOWED123",
            "CHIEF_SLACK_ALLOWED_CHANNEL_IDS": "CALLOWED123",
        }

    def opener(self, request, timeout=0):
        method = request.full_url.rsplit("/", 1)[-1]
        if method == "auth.test":
            return FakeResponse({"ok": True, "user_id": "UCHIEF123", "team_id": "TTEAM123"})
        return FakeResponse({"ok": True, "channel": "CALLOWED123", "ts": "1785080000.1"})

    def test_sender_attests_identity_and_redacts_body(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            receipt = post_message("CALLOWED123", "synthetic body", opener=self.opener)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["bot_user_id"], "UCHIEF123")
        self.assertNotIn("synthetic body", json.dumps(receipt))
        self.assertNotIn("xoxb-", json.dumps(receipt))

    def test_sender_fails_closed_on_channel_and_identity(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            with self.assertRaisesRegex(SlackError, "not allowlisted"):
                post_message("CWRONG", "synthetic", opener=self.opener)

            def wrong_identity(request, timeout=0):
                return FakeResponse({"ok": True, "user_id": "UECHO", "team_id": "TTEAM123"})

            with self.assertRaisesRegex(SlackError, "does not match"):
                post_message("CALLOWED123", "synthetic", opener=wrong_identity)

    def test_env_upsert_is_atomic_and_non_executing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            value = 'literal $(touch /tmp/never) "quotes"'
            upsert(env_path, "CHIEF_SLACK_BOT_TOKEN", value)
            self.assertEqual(read_env_file(env_path)["CHIEF_SLACK_BOT_TOKEN"], value)
            if os.name != "nt":
                self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_env_loader_imports_only_chief_relay_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                'CHIEF_SLACK_TEAM_ID="TTEAM123"\n'
                'OPENAI_API_KEY="must-not-load"\n'
                'ECHO_PRIVATE_SENTINEL="must-not-load"\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                load_env_file(env_path)
                self.assertEqual(os.environ["CHIEF_SLACK_TEAM_ID"], "TTEAM123")
                self.assertNotIn("OPENAI_API_KEY", os.environ)
                self.assertNotIn("ECHO_PRIVATE_SENTINEL", os.environ)

    def test_concurrent_upserts_preserve_both_values_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            upsert(env_path, "CHIEF_SLACK_TEAM_ID", "TOLD")
            barrier = threading.Barrier(2)

            def write(key: str, value: str) -> None:
                barrier.wait()
                upsert(env_path, key, value)

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(write, "CHIEF_SLACK_TEAM_ID", "TTEAM123"),
                    executor.submit(write, "CHIEF_SLACK_BOT_USER_ID", "UCHIEF123"),
                ]
                for future in futures:
                    future.result()
            values = read_env_file(env_path)
            self.assertEqual(values["CHIEF_SLACK_TEAM_ID"], "TTEAM123")
            self.assertEqual(values["CHIEF_SLACK_BOT_USER_ID"], "UCHIEF123")
            backups = list(
                env_path.parent.joinpath(".env.backups", "chief-slack").glob("*.env")
            )
            self.assertGreaterEqual(len(backups), 2)
            self.assertTrue(
                any(read_env_file(path).get("CHIEF_SLACK_TEAM_ID") == "TOLD" for path in backups)
            )

    def test_empty_env_value_is_not_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text('CHIEF_SLACK_TEAM_ID=""\n', encoding="utf-8")
            self.assertFalse(has_key(env_path, "CHIEF_SLACK_TEAM_ID"))


if __name__ == "__main__":
    unittest.main()
