#!/usr/bin/env bash
# Deploy Echo Slack Events API server on the Mac mini behind Tailscale Funnel.
#
# Prereqs (one-time, on the Mac):
#   - This repo cloned at $OPENCLAW_HOME (default ~/.openclaw)
#   - Tailscale signed in with Funnel enabled in admin console
#   - ~/.openclaw/.env.slack populated with SLACK_BOT_TOKEN + SLACK_SIGNING_SECRET (chmod 600)
#
# Usage:
#   bash scripts/deploy_slack.sh

set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
VENV="${OPENCLAW_HOME}/venv-slack"
ENV_FILE="${OPENCLAW_HOME}/.env.slack"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_LABEL="ai.openclaw.slack"
PORT="${SLACK_SERVER_PORT:-8080}"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "${OPENCLAW_HOME}/logs" "$LAUNCH_AGENT_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: ${ENV_FILE} not found." >&2
  echo "Create it with SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET, then re-run." >&2
  echo "Template: ${REPO_DIR}/config/.env.slack.example" >&2
  exit 1
fi
chmod 600 "$ENV_FILE"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "ERROR: tailscale CLI not on PATH. Install Tailscale.app from tailscale.com first." >&2
  exit 1
fi

echo "[1/5] Creating venv at ${VENV}"
if [ ! -d "$VENV" ]; then
  /usr/bin/python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --upgrade pip --quiet
"$VENV/bin/pip" install -r "$REPO_DIR/requirements.txt" --quiet

echo "[2/5] Linking source into ${OPENCLAW_HOME}"
if [ "$REPO_DIR" != "$OPENCLAW_HOME" ]; then
  ln -snf "$REPO_DIR/echo_slack" "$OPENCLAW_HOME/echo_slack"
fi

echo "[3/5] Installing LaunchAgent ${PLIST_LABEL}"
PLIST_DST="$LAUNCH_AGENT_DIR/${PLIST_LABEL}.plist"
sed "s|__OPENCLAW_HOME__|${OPENCLAW_HOME}|g" \
  "$REPO_DIR/config/ai.openclaw.slack.plist" > "$PLIST_DST"

launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/${PLIST_LABEL}"
launchctl kickstart -k "gui/$(id -u)/${PLIST_LABEL}"

echo "[4/5] Health check on http://127.0.0.1:${PORT}/healthz"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    echo "  server up"
    break
  fi
  if [ "$i" = "10" ]; then
    echo "ERROR: server didn't come up. Tail: ${OPENCLAW_HOME}/logs/slack_error.log" >&2
    exit 1
  fi
  sleep 1
done

echo "[5/5] Configuring Tailscale Funnel on port ${PORT}"
tailscale funnel --bg "${PORT}" >/dev/null

DNS_NAME="$(tailscale status --json | python3 -c 'import sys, json; d=json.load(sys.stdin); print(d["Self"]["DNSName"].rstrip("."))')"
URL="https://${DNS_NAME}/slack/events"

cat <<EOF

==========================================================================
Echo Slack server is live.

Next steps in the Slack app dashboard (https://api.slack.com/apps):
  1. Event Subscriptions -> Enable Events
  2. Request URL: ${URL}
     (Slack will send a url_verification challenge; this server replies.)
  3. Subscribe to bot events: app_mention, message.im (and message.channels if needed)
  4. OAuth & Permissions -> Reinstall to Workspace
  5. Settings -> Socket Mode -> DISABLE (you no longer need it)

Tail logs:
  tail -f ${OPENCLAW_HOME}/logs/slack.log ${OPENCLAW_HOME}/logs/slack_error.log

Restart server:
  launchctl kickstart -k gui/\$(id -u)/${PLIST_LABEL}
==========================================================================
EOF
