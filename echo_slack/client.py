"""Outbound Slack Web API wrapper. Stateless HTTPS, no WebSocket."""

from functools import lru_cache
from slack_sdk import WebClient

from . import config


@lru_cache(maxsize=1)
def bot_client() -> WebClient:
    return WebClient(token=config.bot_token())


@lru_cache(maxsize=1)
def user_client() -> WebClient | None:
    token = config.user_token()
    return WebClient(token=token) if token else None


def post_message(channel: str, text: str, thread_ts: str | None = None, as_user: bool = False):
    client = user_client() if as_user else bot_client()
    if client is None:
        raise RuntimeError("user_client requested but SLACK_USER_TOKEN not set")
    return client.chat_postMessage(channel=channel, text=text, thread_ts=thread_ts)
