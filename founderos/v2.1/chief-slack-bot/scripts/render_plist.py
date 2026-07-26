#!/usr/bin/env python3
"""Render the LaunchAgent without putting secrets in arguments or the plist."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--profile-home", required=True)
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()

    replacements = {
        "__PYTHON3__": escape(str(Path(args.python).resolve())),
        "__PROFILE_HOME__": escape(str(Path(args.profile_home).expanduser().resolve())),
        "__HERMES_ENV_FILE__": escape(str(Path(args.env_file).expanduser().resolve())),
    }
    rendered = args.template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        rendered = rendered.replace(marker, value)
    if "__" in rendered:
        raise ValueError("unresolved plist marker")

    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    os.replace(temporary, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
