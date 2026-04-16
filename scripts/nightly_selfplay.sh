#!/usr/bin/env bash
# Nightly self-play runner
# Install: crontab -e → add: 0 2 * * * /home/user/claude/scripts/nightly_selfplay.sh
# On macOS: cp config/ai.openclaw.selfplay.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/ai.openclaw.selfplay.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_DIR}/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"

echo "[${TIMESTAMP}] Starting nightly self-play" >> "${LOG_DIR}/selfplay.log"

python3 scripts/cli.py nightly \
    --skills video-script,ad-copy \
    --rounds 5 \
    >> "${LOG_DIR}/selfplay.log" 2>&1

echo "[$(date +%Y%m%d_%H%M%S)] Nightly self-play complete" >> "${LOG_DIR}/selfplay.log"
