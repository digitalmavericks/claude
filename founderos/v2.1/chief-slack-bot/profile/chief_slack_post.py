#!/usr/bin/env python3
"""Post one stdin-supplied message as the dedicated CHIEF Slack bot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from envfile import load_env_file

SLACK_API = "https://slack.com/api"
MAX_MESSAGE_CHARS = 40_000


class SlackError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SlackError(f"missing required environment value: {name}")
    return value


def _csv_set(name: str, fallback: str = "") -> set[str]:
    raw = os.environ.get(name, fallback)
    return {item.strip() for item in raw.split(",") if item.strip()}


def _api_call(
    method: str,
    token: str,
    fields: dict[str, str],
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{SLACK_API}/{method}",
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "founderos-chief-slack-relay/1.0",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=20) as response:
            payload = response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise SlackError(f"Slack transport failed for {method}: {type(exc).__name__}") from exc
    try:
        result = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SlackError(f"Slack returned invalid JSON for {method}") from exc
    if not isinstance(result, dict) or not result.get("ok"):
        error = result.get("error", "unknown_error") if isinstance(result, dict) else "invalid_result"
        raise SlackError(f"Slack {method} failed: {error}")
    return result


def post_message(
    channel: str,
    text: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    if not text.strip():
        raise SlackError("message body is empty")
    if len(text) > MAX_MESSAGE_CHARS:
        raise SlackError(f"message exceeds {MAX_MESSAGE_CHARS} characters")
    if "\x00" in text:
        raise SlackError("message contains a NUL byte")

    token = _required("CHIEF_SLACK_BOT_TOKEN")
    expected_user = _required("CHIEF_SLACK_BOT_USER_ID")
    expected_team = _required("CHIEF_SLACK_TEAM_ID")
    allowed_channels = _csv_set(
        "CHIEF_SLACK_ALLOWED_CHANNEL_IDS",
        os.environ.get("CHIEF_SLACK_DEFAULT_CHANNEL_ID", ""),
    )
    if channel not in allowed_channels:
        raise SlackError("requested channel is not allowlisted")

    identity = _api_call("auth.test", token, {}, opener=opener)
    observed_user = str(identity.get("user_id", ""))
    observed_team = str(identity.get("team_id", ""))
    if observed_user != expected_user or observed_team != expected_team:
        raise SlackError("Slack token identity does not match the registered CHIEF user/team")

    result = _api_call(
        "chat.postMessage",
        token,
        {"channel": channel, "text": text, "unfurl_links": "false", "unfurl_media": "false"},
        opener=opener,
    )
    return {
        "ok": True,
        "channel": str(result.get("channel", channel)),
        "ts": str(result.get("ts", "")),
        "bot_user_id": observed_user,
        "team_id": observed_team,
        "message_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post stdin as the registered CHIEF Slack bot; token and body never enter argv."
    )
    parser.add_argument(
        "--channel",
        default="",
        help="Allowed channel ID; defaults to CHIEF_SLACK_DEFAULT_CHANNEL_ID.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(os.environ.get("HERMES_ROOT_ENV", "~/.hermes/.env")).expanduser(),
    )
    args = parser.parse_args()

    try:
        load_env_file(args.env_file)
        channel = args.channel.strip() or _required("CHIEF_SLACK_DEFAULT_CHANNEL_ID")
        text = sys.stdin.read()
        receipt = post_message(channel, text)
    except (OSError, ValueError, SlackError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
