#!/usr/bin/env bash
# preflight.sh — verify it's safe to re-route Tailscale Funnel from 18789 to 3333
# Per shared-state.md (2026-04-24), Funnel is currently routed to 127.0.0.1:18789.
# `deploy/16-slack-socketmode-to-events.sh` will reset Funnel to 127.0.0.1:3333.
# Run THIS script first to confirm what's on 18789 before pulling that lever.
#
# Usage:
#   bash migration/preflight.sh
#
# Exit codes:
#   0 — safe to proceed with cutover
#   1 — port 18789 has a listener; review output before proceeding
#   2 — environment problem (tailscale not on PATH, etc.)

set -euo pipefail

bold() { printf "\n\033[1;36m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m!\033[0m %s\n" "$*"; }
err()  { printf "  \033[1;31m✗\033[0m %s\n" "$*"; }

bold "1. Tailscale state"
if ! command -v tailscale >/dev/null 2>&1; then
  err "tailscale CLI not on PATH"
  exit 2
fi
ok "tailscale: $(tailscale version | head -1)"

bold "2. Tailscale serve config (current routes)"
tailscale serve status 2>&1 || warn "no active serve config"

bold "3. Tailscale funnel config (public exposure)"
tailscale funnel status 2>&1 || warn "no active funnel config"

bold "4. Port 18789 listener"
LISTENER=$(lsof -nP -iTCP:18789 -sTCP:LISTEN 2>/dev/null || true)
if [ -z "$LISTENER" ]; then
  ok "Port 18789: nothing listening"
  PORT_FREE=1
else
  echo "$LISTENER"
  PROC=$(echo "$LISTENER" | awk 'NR==2 {print $1 " (pid " $2 ")"}')
  warn "Port 18789 in use: $PROC"
  PORT_FREE=0
fi

bold "5. Port 3333 listener (target for the Slack handler)"
EXISTING=$(lsof -nP -iTCP:3333 -sTCP:LISTEN 2>/dev/null || true)
if [ -z "$EXISTING" ]; then
  ok "Port 3333: free"
else
  echo "$EXISTING"
  warn "Port 3333 already in use — script will conflict. Investigate."
fi

bold "6. Required files on disk"
ECHO_ROOT="/Users/echo/Documents/Claude/Projects/ECHO"
for f in "$ECHO_ROOT/deploy/16-slack-socketmode-to-events.sh" \
         "$ECHO_ROOT/deploy/load-echo-config.sh" \
         "$ECHO_ROOT/ECHO-CONFIG.md"; do
  if [ -f "$f" ]; then
    ok "$f"
  else
    err "MISSING: $f"
  fi
done

bold "7. Slack credential format check (no values printed)"
if [ -f "$ECHO_ROOT/ECHO-CONFIG.md" ]; then
  for k in SLACK_BOT_TOKEN SLACK_SIGNING_SECRET; do
    if grep -qE "^${k}=" "$ECHO_ROOT/ECHO-CONFIG.md"; then
      ok "$k present"
    else
      err "$k MISSING from ECHO-CONFIG.md"
    fi
  done
fi

bold "8. OpenClaw version (must be >=2026.4.22 for native webhook support)"
if command -v openclaw >/dev/null 2>&1; then
  V=$(openclaw --version 2>/dev/null || echo "unknown")
  ok "openclaw: $V"
else
  warn "openclaw CLI not on PATH — version cannot be verified from this script"
fi

bold "9. Verdict"
if [ "$PORT_FREE" = "1" ]; then
  ok "Port 18789 is free — re-routing Funnel will not displace anything"
  echo ""
  echo "  Next step: bash deploy/16-slack-socketmode-to-events.sh"
  exit 0
else
  warn "Port 18789 has a listener (see section 4 above)"
  echo ""
  echo "  Decide before proceeding:"
  echo "  - If the listener is OpenClaw or another load-bearing service:"
  echo "      ABORT. Re-routing Funnel will cut it off the public internet."
  echo "  - If the listener is a stale dev server, or Funnel was pointing"
  echo "    at it for a non-critical reason:"
  echo "      Proceed with bash deploy/16-slack-socketmode-to-events.sh"
  echo "      (it will run \`tailscale funnel --bg off; tailscale serve reset\`"
  echo "      first — that disconnects the existing route)"
  exit 1
fi
