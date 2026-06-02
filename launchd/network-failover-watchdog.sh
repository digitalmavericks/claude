#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# ECHO Mac mini — Network Failover Watchdog (LaunchDaemon)
# ════════════════════════════════════════════════════════════════════════════
# THE PROBLEM THIS SOLVES
#   The Mac mini's primary uplink is the wired LAN (FrontierDC). When that
#   connection dropped while DC was out of town, the Mac had NO fallback — so
#   Tailscale and the remote-control Funnel (→ 127.0.0.1:18789) went dark and
#   there was no way back in. It stayed offline for ~7 days, unnoticed.
#
# WHAT THIS DOES (every 2 min via launchd, and once at boot)
#   1. Tests REAL internet reachability against several targets.
#   2. If UP  → makes sure Tailscale is up and the Funnel is re-armed, then
#               exits quietly. (No Wi-Fi changes when the wired link is fine.)
#   3. If DOWN → powers on Wi-Fi and joins the BACKUP network "Frenchie Fam",
#               which is a DIFFERENT ISP. It will NEVER join "FrontierDC" —
#               that Wi-Fi rides the same dead uplink as the wired LAN, so it
#               would be just as offline. Then it re-checks, re-arms Tailscale,
#               and posts a Slack alert (which now delivers, because the backup
#               link is live).
#
# WHY A LAUNCHDAEMON (not a LaunchAgent)
#   It must run as root, at boot, with NO user logged in — which is exactly the
#   state the Mac is in after an uplink drop / power blip. `networksetup` and
#   `tailscale` both need that privilege/availability.
#
# SECRETS
#   The Wi-Fi password is NOT stored in this repo. It is read (in order) from:
#     1. env var  FRENCHIE_FAM_PSK
#     2. ECHO-CONFIG.md line  FRENCHIE_FAM_PSK=...
#     3. the macOS System keychain (if "Frenchie Fam" is already a known
#        network — then no password is needed at all).
# ════════════════════════════════════════════════════════════════════════════
set -uo pipefail

# ──── Config ────────────────────────────────────────────────────────────────
BACKUP_SSID="Frenchie Fam"          # backup ISP — different uplink than the LAN
FORBIDDEN_SSID="FrontierDC"         # same physical uplink as the wired LAN — NEVER join
FUNNEL_PORT="18789"                 # OpenClaw gateway behind the Tailscale Funnel
PING_TARGETS=(1.1.1.1 8.8.8.8 9.9.9.9)
CURL_PROBE="https://captive.apple.com/hotspot-detect.html"
ECHO_ROOT="/Users/echo/Documents/Claude/Projects/ECHO"
CONFIG_FILE="$ECHO_ROOT/ECHO-CONFIG.md"
REALERT_SECONDS=$(( 6 * 3600 ))     # while still fully down, re-alert at most every 6h

# ──── Logging / state ───────────────────────────────────────────────────────
LOG_DIR="/Users/echo/Library/Logs/digitalmavericks"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/network-failover.log"
STATE_FILE="$LOG_DIR/network-failover.state"
exec >> "$LOG_FILE" 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*"; }
log "──── network-failover watchdog run ────"

# ──── Helpers ───────────────────────────────────────────────────────────────
load_config_value() {  # $1 = KEY → prints value (env first, then ECHO-CONFIG.md)
  local key="$1" val=""
  val="$(printenv "$key" 2>/dev/null || true)"
  if [ -z "$val" ] && [ -f "$CONFIG_FILE" ]; then
    # Trim only the leading/trailing whitespace + surrounding quotes — NOT
    # internal spaces (Wi-Fi passwords are allowed to contain them).
    val="$(grep -E "^${key}[[:space:]]*=" "$CONFIG_FILE" | head -1 \
            | sed -E 's/^[^=]*=[[:space:]]*//; s/[[:space:]]*$//')"
    val="${val%\"}"; val="${val#\"}"
  fi
  printf '%s' "$val"
}

find_wifi_device() {   # prints e.g. "en0"
  networksetup -listallhardwareports 2>/dev/null \
    | awk '/Wi-Fi|AirPort/{getline; if ($1=="Device:") {print $2; exit}}'
}

current_ssid() {       # $1 = wifi device → prints joined SSID (or empty)
  networksetup -getairportnetwork "$1" 2>/dev/null | sed 's/^Current Wi-Fi Network: //'
}

internet_up() {
  local t
  for t in "${PING_TARGETS[@]}"; do
    ping -c1 -t3 "$t" >/dev/null 2>&1 && return 0
  done
  # Final fallback for ICMP-blocked networks: a plain HTTP probe.
  curl -fsS --max-time 5 "$CURL_PROBE" >/dev/null 2>&1
}

resolve_tailscale() {
  command -v tailscale 2>/dev/null && return
  local p
  for p in /usr/local/bin/tailscale /opt/homebrew/bin/tailscale \
           "/Applications/Tailscale.app/Contents/MacOS/Tailscale"; do
    [ -x "$p" ] && { echo "$p"; return; }
  done
  echo ""
}

rearm_tailscale() {
  local ts; ts="$(resolve_tailscale)"
  if [ -z "$ts" ]; then
    log "WARN: tailscale CLI not found — skipping Funnel re-arm (may be managed at OS level)"
    return
  fi
  "$ts" up >/dev/null 2>&1 && log "tailscale up: ok" || log "WARN: 'tailscale up' returned non-zero"
  if "$ts" funnel --bg "$FUNNEL_PORT" >/dev/null 2>&1; then
    log "Funnel re-armed → 127.0.0.1:$FUNNEL_PORT"
  else
    log "WARN: 'tailscale funnel --bg $FUNNEL_PORT' failed (Funnel may be externally managed)"
  fi
}

slack_alert() {        # $1 = title, $2 = mrkdwn body
  local hook; hook="$(load_config_value SLACK_OPS_WEBHOOK)"
  if [ -z "$hook" ]; then
    log "WARN: no SLACK_OPS_WEBHOOK configured — alert NOT sent: $1"
    return
  fi
  local payload
  payload=$(cat <<JSON
{ "text": "$1",
  "blocks": [
    {"type":"header","text":{"type":"plain_text","text":"$1"}},
    {"type":"section","text":{"type":"mrkdwn","text":"$2"}},
    {"type":"context","elements":[{"type":"mrkdwn","text":"Mac: $(hostname) · $(date '+%Y-%m-%d %H:%M %Z')"}]}
  ] }
JSON
)
  curl -s -X POST -H 'Content-Type: application/json' -d "$payload" "$hook" >/dev/null 2>&1 \
    && log "Slack alert sent: $1" || log "WARN: Slack POST failed"
}

prev_status() { [ -f "$STATE_FILE" ] && awk '{print $1}' "$STATE_FILE" || echo "UNKNOWN"; }
prev_ts()     { [ -f "$STATE_FILE" ] && awk '{print $2}' "$STATE_FILE" || echo "0"; }
write_state() { echo "$1 $(date +%s)" > "$STATE_FILE"; }

# ──── Main ──────────────────────────────────────────────────────────────────
PREV="$(prev_status)"
PREV_TS="$(prev_ts)"
NOW="$(date +%s)"

# 1) Happy path — wired/primary link is fine.
if internet_up; then
  log "Internet: UP"
  rearm_tailscale
  if [ "$PREV" = "DOWN" ] || [ "$PREV" = "FAILOVER" ]; then
    WIFI_DEV="$(find_wifi_device)"
    slack_alert "✅ ECHO Mac back online" \
      "Internet recovered. Current Wi-Fi: *$(current_ssid "${WIFI_DEV:-en0}")*. Tailscale Funnel re-armed on port $FUNNEL_PORT. If it came back on the primary wired link, you can ignore this."
  fi
  write_state "UP"
  exit 0
fi

# 2) Internet is DOWN → fail over to the backup ISP's Wi-Fi.
log "Internet: DOWN — initiating Wi-Fi failover to '$BACKUP_SSID'"
WIFI_DEV="$(find_wifi_device)"
if [ -z "$WIFI_DEV" ]; then
  log "ERROR: no Wi-Fi device found — cannot fail over"
  if [ "$PREV" != "DOWN" ] || [ $(( NOW - PREV_TS )) -ge "$REALERT_SECONDS" ]; then
    slack_alert "🚨 ECHO Mac OFFLINE — no Wi-Fi device" \
      "Wired uplink is DOWN and no Wi-Fi interface was found to fail over to. Physical check needed."
  fi
  write_state "DOWN"
  exit 1
fi

networksetup -setairportpower "$WIFI_DEV" on >/dev/null 2>&1
sleep 3

# Explicitly join the BACKUP SSID. We never issue a join for "$FORBIDDEN_SSID".
PSK="$(load_config_value FRENCHIE_FAM_PSK)"
if [ -n "$PSK" ]; then
  networksetup -setairportnetwork "$WIFI_DEV" "$BACKUP_SSID" "$PSK" >/dev/null 2>&1 \
    && log "Issued join for '$BACKUP_SSID' (config/keychain password)" \
    || log "WARN: join for '$BACKUP_SSID' with provided password failed"
else
  # No PSK on hand → rely on the System keychain for a known network.
  networksetup -setairportnetwork "$WIFI_DEV" "$BACKUP_SSID" >/dev/null 2>&1 \
    && log "Issued join for '$BACKUP_SSID' (known-network / keychain)" \
    || log "WARN: join for '$BACKUP_SSID' failed and no FRENCHIE_FAM_PSK configured"
fi

# Give association + DHCP time, then re-check (up to ~30s).
for _ in 1 2 3 4 5 6; do
  sleep 5
  internet_up && break
done

if internet_up; then
  SSID="$(current_ssid "$WIFI_DEV")"
  log "Failover SUCCESS — internet via '${SSID:-$BACKUP_SSID}'"
  if [ "$SSID" = "$FORBIDDEN_SSID" ]; then
    # Shouldn't happen (we only ever join the backup), but guard anyway.
    log "WARN: associated to forbidden SSID '$FORBIDDEN_SSID' — re-joining '$BACKUP_SSID'"
    networksetup -setairportnetwork "$WIFI_DEV" "$BACKUP_SSID" "$PSK" >/dev/null 2>&1 || true
  fi
  rearm_tailscale
  slack_alert "🔁 ECHO Mac failed over to backup Wi-Fi" \
    "The wired/FrontierDC uplink was DOWN. The Mac is now online via *${SSID:-$BACKUP_SSID}* and reachable again; Tailscale Funnel re-armed on port $FUNNEL_PORT. *Action:* check the primary wired connection when you get a chance."
  write_state "FAILOVER"
  exit 0
fi

# 3) Both paths down.
log "Failover FAILED — still no internet after joining '$BACKUP_SSID'"
if [ "$PREV" != "DOWN" ] || [ $(( NOW - PREV_TS )) -ge "$REALERT_SECONDS" ]; then
  slack_alert "🚨 ECHO Mac OFFLINE — failover failed" \
    "Both the wired uplink AND the backup Wi-Fi '*$BACKUP_SSID*' are unreachable. The Mac mini has no path to the internet. A physical check is needed."
fi
write_state "DOWN"
exit 1
