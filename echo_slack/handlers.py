"""Slack event handlers.

Wire your real Echo logic into these functions. The server already verifies
signatures, dedupes retries, and dispatches in the background — handlers just
need to do the work.
"""

import logging
from typing import Any

from . import client

log = logging.getLogger("echo_slack.handlers")


def handle_app_mention(event: dict[str, Any]) -> None:
    user = event.get("user")
    channel = event.get("channel")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")
    log.info("app_mention from %s in %s: %s", user, channel, text[:200])
    client.post_message(
        channel=channel,
        text=f"<@{user}> Echo here. (Events API + Tailscale Funnel — no socket.)",
        thread_ts=thread_ts,
    )


def handle_message_im(event: dict[str, Any]) -> None:
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return
    user = event.get("user")
    channel = event.get("channel")
    text = event.get("text", "")
    log.info("DM from %s: %s", user, text[:200])
    client.post_message(channel=channel, text=f"Got it: {text}")


def handle_message_channels(event: dict[str, Any]) -> None:
    if event.get("bot_id") or event.get("subtype"):
        return
    log.debug("channel message in %s", event.get("channel"))


EVENT_ROUTES = {
    "app_mention": handle_app_mention,
    "message": lambda e: (
        handle_message_im(e) if e.get("channel_type") == "im" else handle_message_channels(e)
    ),
}


def dispatch(event: dict[str, Any]) -> None:
    handler = EVENT_ROUTES.get(event.get("type"))
    if handler is None:
        log.debug("no handler for event type %s", event.get("type"))
        return
    try:
        handler(event)
    except Exception:
        log.exception("handler failed for event type %s", event.get("type"))
