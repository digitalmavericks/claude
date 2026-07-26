"""Strict Slack Events API validation and atomic AgentBus delivery."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_CLOCK_SKEW_SECONDS = 300
MAX_BODY_BYTES = 256 * 1024
MAX_MESSAGE_CHARS = 32_000
ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,80}$")


class BridgeError(RuntimeError):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def _required(env: dict[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"missing required environment value: {name}")
    return value


def _csv(env: dict[str, str], name: str) -> frozenset[str]:
    values = frozenset(item.strip() for item in _required(env, name).split(",") if item.strip())
    if not values:
        raise ValueError(f"empty allowlist: {name}")
    for value in values:
        if not ID_RE.fullmatch(value):
            raise ValueError(f"invalid Slack ID in {name}")
    return values


@dataclass(frozen=True)
class BridgeConfig:
    signing_secret: str
    bot_user_id: str
    team_id: str
    api_app_id: str
    allowed_channel_ids: frozenset[str]
    allowed_user_ids: frozenset[str]
    agentbus_root: Path
    state_db: Path

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "BridgeConfig":
        source = dict(os.environ if env is None else env)
        root = Path(_required(source, "CHIEF_AGENTBUS_ROOT")).expanduser().resolve()
        if root.name != "_AgentBus":
            raise ValueError("CHIEF_AGENTBUS_ROOT must resolve to a directory named _AgentBus")
        profile_home = Path(
            source.get("CHIEF_PROFILE_HOME", "~/.hermes/profiles/chief")
        ).expanduser()
        return cls(
            signing_secret=_required(source, "CHIEF_SLACK_SIGNING_SECRET"),
            bot_user_id=_required(source, "CHIEF_SLACK_BOT_USER_ID"),
            team_id=_required(source, "CHIEF_SLACK_TEAM_ID"),
            api_app_id=_required(source, "CHIEF_SLACK_API_APP_ID"),
            allowed_channel_ids=_csv(source, "CHIEF_SLACK_ALLOWED_CHANNEL_IDS"),
            allowed_user_ids=_csv(source, "CHIEF_SLACK_ALLOWED_USER_IDS"),
            agentbus_root=root,
            state_db=Path(
                source.get(
                    "CHIEF_SLACK_EVENT_DB",
                    str(profile_home / "state" / "slack-events.sqlite3"),
                )
            ).expanduser(),
        )


def slack_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    base = b"v0:" + timestamp.encode("ascii") + b":" + raw_body
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def verify_slack_request(
    config: BridgeConfig,
    headers: dict[str, str],
    raw_body: bytes,
    *,
    now: int | None = None,
) -> None:
    if len(raw_body) > MAX_BODY_BYTES:
        raise BridgeError(413, "body_too_large")
    normalized = {key.lower(): value for key, value in headers.items()}
    timestamp = normalized.get("x-slack-request-timestamp", "")
    signature = normalized.get("x-slack-signature", "")
    try:
        request_time = int(timestamp)
    except ValueError as exc:
        raise BridgeError(401, "invalid_timestamp") from exc
    current = int(time.time() if now is None else now)
    if abs(current - request_time) > MAX_CLOCK_SKEW_SECONDS:
        raise BridgeError(401, "stale_request")
    expected = slack_signature(config.signing_secret, timestamp, raw_body)
    if not hmac.compare_digest(signature, expected):
        raise BridgeError(401, "invalid_signature")


class AgentBusWriter:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self._delivery_lock = threading.Lock()
        self.inbox = config.agentbus_root / "chief"
        self.inbox.mkdir(parents=True, exist_ok=True, mode=0o700)
        config.state_db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with contextlib.closing(self._connect()) as database:
            database.execute("PRAGMA journal_mode=WAL")
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS slack_events (
                    event_id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    delivered_at REAL
                )
                """
            )
            database.commit()
        if config.state_db.exists():
            os.chmod(config.state_db, 0o600)

    def _connect(self) -> sqlite3.Connection:
        database = sqlite3.connect(self.config.state_db, timeout=30)
        database.execute("PRAGMA busy_timeout=30000")
        database.execute("PRAGMA synchronous=FULL")
        return database

    @staticmethod
    def _message_id(team_id: str, event_id: str) -> str:
        return hashlib.sha256(f"{team_id}:{event_id}".encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        if os.name == "nt":  # Windows cannot open directories this way.
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _write_or_validate_target(
        self,
        target: Path,
        message: dict[str, Any],
    ) -> bool:
        """Return True when a missing target had to be reconstructed."""
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise BridgeError(500, "invalid_existing_target") from exc
            if existing != message:
                raise BridgeError(500, "deterministic_target_collision")
            return False

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.inbox,
            delete=False,
            prefix=f".{target.name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(message, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        self._fsync_directory(self.inbox)
        return True

    def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._delivery_lock:
            return self._enqueue_locked(payload)

    def _enqueue_locked(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = payload["event"]
        event_id = payload["event_id"]
        message_id = self._message_id(payload["team_id"], event_id)
        event_ts = float(event["ts"])
        target = self.inbox / f"{event_ts:.6f}__slack__{message_id}.json"

        thread_seed = str(event.get("thread_ts") or event["ts"])
        thread = re.sub(r"[^a-zA-Z0-9_-]+", "-", f"slack-{event['channel']}-{thread_seed}")
        message = {
            "id": message_id,
            "ts": event_ts,
            "iso": datetime.fromtimestamp(event_ts, tz=timezone.utc).isoformat(),
            "from": "slack",
            "to": "chief",
            "thread": thread,
            "body": str(event["text"]),
            "read": False,
            "read_ts": None,
            "action_needed": True,
            "handoff": "",
            "source": {
                "type": "slack_app_mention",
                "event_id": event_id,
                "team_id": payload["team_id"],
                "api_app_id": payload["api_app_id"],
                "channel_id": event["channel"],
                "user_id": event["user"],
                "event_ts": str(event["ts"]),
            },
        }

        with contextlib.closing(self._connect()) as database:
            database.execute("BEGIN IMMEDIATE")
            try:
                row = database.execute(
                    "SELECT message_id, target_path, delivered_at FROM slack_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if row and row[2] is not None:
                    if row[0] != message_id or row[1] != str(target):
                        raise BridgeError(500, "event_identity_collision")
                    repaired = self._write_or_validate_target(target, message)
                    if repaired:
                        database.execute(
                            "UPDATE slack_events SET delivered_at = ? WHERE event_id = ?",
                            (time.time(), event_id),
                        )
                    database.commit()
                    return {
                        "status": "repaired" if repaired else "duplicate",
                        "event_id": event_id,
                        "message_id": row[0],
                        "target": row[1],
                    }
                if row is None:
                    database.execute(
                        "INSERT INTO slack_events(event_id, message_id, target_path, delivered_at) VALUES(?, ?, ?, NULL)",
                        (event_id, message_id, str(target)),
                    )
                elif row[0] != message_id or row[1] != str(target):
                    raise BridgeError(500, "event_identity_collision")

                self._write_or_validate_target(target, message)

                database.execute(
                    "UPDATE slack_events SET delivered_at = ? WHERE event_id = ?",
                    (time.time(), event_id),
                )
                database.commit()
            except Exception:
                database.rollback()
                raise
        return {
            "status": "delivered",
            "event_id": event_id,
            "message_id": message_id,
            "target": str(target),
        }


def validate_event_payload(config: BridgeConfig, payload: dict[str, Any]) -> None:
    if payload.get("type") not in {"url_verification", "event_callback"}:
        raise BridgeError(400, "unsupported_payload_type")
    if payload.get("team_id") != config.team_id:
        raise BridgeError(403, "wrong_team")
    if payload.get("api_app_id") != config.api_app_id:
        raise BridgeError(403, "wrong_app")
    if payload["type"] == "url_verification":
        if not isinstance(payload.get("challenge"), str) or not payload["challenge"]:
            raise BridgeError(400, "missing_challenge")
        return

    event_id = payload.get("event_id")
    event = payload.get("event")
    if not isinstance(event_id, str) or not event_id:
        raise BridgeError(400, "missing_event_id")
    if not isinstance(event, dict):
        raise BridgeError(400, "missing_event")
    if event.get("type") != "app_mention":
        raise BridgeError(202, "ignored_event_type")
    if event.get("subtype") or event.get("bot_id"):
        raise BridgeError(202, "ignored_bot_event")
    user_id = str(event.get("user", ""))
    channel_id = str(event.get("channel", ""))
    text = str(event.get("text", ""))
    if user_id == config.bot_user_id:
        raise BridgeError(202, "ignored_self_event")
    if user_id not in config.allowed_user_ids:
        raise BridgeError(403, "user_not_allowed")
    if channel_id not in config.allowed_channel_ids:
        raise BridgeError(403, "channel_not_allowed")
    if f"<@{config.bot_user_id}>" not in text:
        raise BridgeError(202, "strict_mention_required")
    if len(text) > MAX_MESSAGE_CHARS or "\x00" in text:
        raise BridgeError(400, "invalid_message_body")
    try:
        float(event["ts"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BridgeError(400, "invalid_event_timestamp") from exc


def handle_request(
    config: BridgeConfig,
    headers: dict[str, str],
    raw_body: bytes,
    *,
    now: int | None = None,
    writer: AgentBusWriter | None = None,
) -> tuple[int, dict[str, Any]]:
    verify_slack_request(config, headers, raw_body, now=now)
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise BridgeError(400, "invalid_json") from exc
    if not isinstance(payload, dict):
        raise BridgeError(400, "invalid_payload")
    validate_event_payload(config, payload)
    if payload["type"] == "url_verification":
        return 200, {"challenge": payload["challenge"]}
    if writer is None:
        raise BridgeError(500, "writer_not_configured")
    result = writer.enqueue(payload)
    return 200, {
        "ok": True,
        "status": result["status"],
        "event_id": result["event_id"],
        "message_id": result["message_id"],
    }
