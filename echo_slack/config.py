"""Runtime config for the Slack Events server.

Secrets are read from ~/.openclaw/.env.slack, not from the repo. The path is
overridable with SLACK_ENV_FILE for testing.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(os.environ.get("SLACK_ENV_FILE", Path.home() / ".openclaw" / ".env.slack"))
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=False)


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"{name} is not set. Add it to {ENV_PATH} (chmod 600) and restart the service."
        )
    return val


def bot_token() -> str:
    return _require("SLACK_BOT_TOKEN")


def signing_secret() -> str:
    return _require("SLACK_SIGNING_SECRET")


def user_token() -> str | None:
    return os.environ.get("SLACK_USER_TOKEN") or None


PORT = int(os.environ.get("SLACK_SERVER_PORT", "8080"))
LOG_LEVEL = os.environ.get("SLACK_LOG_LEVEL", "INFO").upper()
