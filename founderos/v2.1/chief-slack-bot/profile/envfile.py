"""Minimal non-executing dotenv reader for the CHIEF relay."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
CHIEF_RELAY_KEYS = frozenset(
    {
        "CHIEF_AGENTBUS_ROOT",
        "CHIEF_PROFILE_HOME",
        "CHIEF_SLACK_ALLOWED_CHANNEL_IDS",
        "CHIEF_SLACK_ALLOWED_USER_IDS",
        "CHIEF_SLACK_API_APP_ID",
        "CHIEF_SLACK_BOT_TOKEN",
        "CHIEF_SLACK_BOT_USER_ID",
        "CHIEF_SLACK_DEFAULT_CHANNEL_ID",
        "CHIEF_SLACK_EVENT_DB",
        "CHIEF_SLACK_EVENTS_PORT",
        "CHIEF_SLACK_SIGNING_SECRET",
        "CHIEF_SLACK_TEAM_ID",
    }
)


def _decode_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON-quoted dotenv value") from exc
        if not isinstance(decoded, str):
            raise ValueError("dotenv value must decode to a string")
        return decoded
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1]
    return value


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"invalid dotenv line {line_number}")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not KEY_RE.fullmatch(key):
            raise ValueError(f"invalid dotenv key on line {line_number}")
        values[key] = _decode_value(raw_value)
    return values


def load_env_file(
    path: Path,
    *,
    allowed_keys: frozenset[str] = CHIEF_RELAY_KEYS,
    override: bool = False,
) -> None:
    for key, value in read_env_file(path).items():
        if key not in allowed_keys:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
