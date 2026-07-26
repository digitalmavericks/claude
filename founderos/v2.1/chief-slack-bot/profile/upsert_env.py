#!/usr/bin/env python3
"""Atomically inspect or update one allowlisted key in a dotenv file."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows test fallback
    fcntl = None

KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_LOCAL_LOCK = threading.Lock()
ALLOWED_KEYS = {
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


def _line_key(line: str) -> str | None:
    candidate = line.strip()
    if candidate.startswith("export "):
        candidate = candidate[7:].lstrip()
    if "=" not in candidate:
        return None
    key = candidate.split("=", 1)[0].strip()
    return key if KEY_RE.fullmatch(key) else None


def has_key(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from envfile import read_env_file

    value = read_env_file(path).get(key)
    return value is not None and bool(value.strip())


@contextlib.contextmanager
def _exclusive_lock(path: Path):
    lock_path = path.with_name(f".{path.name}.chief-slack.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _LOCAL_LOCK:
        with lock_path.open("a+b") as handle:
            try:
                os.chmod(lock_path, 0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":  # Windows cannot open directories this way.
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_dir = path.parent / f"{path.name}.backups" / "chief-slack"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup = backup_dir / f"{stamp}-{os.getpid()}-{uuid.uuid4().hex[:8]}.env"
    data = path.read_bytes()
    with backup.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(backup, 0o600)
    _fsync_directory(backup_dir)
    return backup


def upsert(path: Path, key: str, value: str) -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"key is not allowlisted: {key}")
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("dotenv value contains a prohibited control character")

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _exclusive_lock(path):
        existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        replacement = f"{key}={json.dumps(value, ensure_ascii=False)}"
        output: list[str] = []
        replaced = False
        for line in existing:
            if _line_key(line) == key:
                if not replaced:
                    output.append(replacement)
                    replaced = True
                continue
            output.append(line)
        if not replaced:
            output.append(replacement)

        rendered = "\n".join(output).rstrip() + "\n"
        if path.exists() and path.read_text(encoding="utf-8") == rendered:
            os.chmod(path, 0o600)
            return

        _backup_existing(path)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, prefix=".env.", suffix=".tmp"
        ) as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_directory(path.parent)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("get", "has", "set"))
    parser.add_argument("path", type=Path)
    parser.add_argument("key", choices=sorted(ALLOWED_KEYS))
    args = parser.parse_args()

    if args.operation == "has":
        return 0 if has_key(args.path, args.key) else 1
    if args.operation == "get":
        if not args.path.exists():
            return 1
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from envfile import read_env_file

        value = read_env_file(args.path).get(args.key)
        if value is None:
            return 1
        sys.stdout.write(value)
        return 0

    value = sys.stdin.read()
    upsert(args.path, args.key, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
