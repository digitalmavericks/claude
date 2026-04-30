# Slack Cutover Runbook — Socket Mode → Events API over Tailscale Funnel

**Effective:** 2026-04-26 (post-OpenClaw v2026.4.27 upgrade)
**Owner:** DC Fawcett (executes on the Mac)
**Author:** Claude (this thread)
**Estimated time:** 15-20 min

---

## Why now

- Echo has been dropping daily for ~3 weeks on Socket Mode (residential ISP / Wi-Fi flaps kill the WebSocket).
- `shared-state.md` (2026-04-24) recorded the Events API migration as **blocked** until OpenClaw `>=v2026.4.22`.
- OpenClaw was just upgraded to **v2026.4.27**. Block lifted.
- The deploy script `deploy/16-slack-socketmode-to-events.sh` (authored 2026-04-22) is ready to run; it bypasses OpenClaw's Slack mode entirely by running a standalone Node handler that writes to Supabase `agent_messages` for ECHO to poll.

## What this runbook does

1. Verifies it's safe to re-route Tailscale Funnel from port `18789` → `3333` (preflight).
2. Runs the existing deploy script (idempotent).
3. Reconfigures the Slack app (browser, biometric-gated to DC).
4. Updates shared-memory files so cowork sees the new state.
5. Stages a Charter v4 §10 update (DC commits when ready).

## What this runbook does NOT do

- Rotate Slack credentials. Do that **before** Step 1 if not already done — see `Pre-flight, item C`.
- Touch `_core/startup-credentials.md` or `config/mcporter.json` (flagged tech debt — separate fire).
- Migrate whatever's on port 18789 if it's load-bearing. Preflight will tell you.

---

## Pre-flight (do these before SSH'ing in)

**A. SSH from Austin → Tampa Mac works?**
```
ssh echo@echos-mac-mini-1
```
If this lands you in a shell, proceed. If not, Remote Login on the Mac is off — STOP, you need someone in front of the Mac to enable it (System Settings → General → Sharing → Remote Login).

**B. Tailscale tailnet shows the Mac as Connected?**
Check https://login.tailscale.com/admin/machines — `echos-mac-mini-1` shows green.

**C. Slack credentials rotated?**
The values pasted earlier in chat (signing secret `60978cb1...`, bot token `xoxb-5192017246660...`, etc.) are exposed. Before proceeding, rotate at https://api.slack.com/apps/A0AGDD10JBX:

- Basic Information → Signing Secret → **Regenerate**
- Basic Information → Client Secret → **Regenerate**
- OAuth & Permissions → **Reinstall to Workspace** (issues new `xoxb-` and `xoxp-`)
- Basic Information → App-Level Tokens → ECHO → **Revoke** (no longer needed without Socket Mode)

Paste the rotated values into `/Users/echo/Documents/Claude/Projects/ECHO/ECHO-CONFIG.md` under their existing keys. **Do not paste them into chat.**

---

## Step 1 — Preflight check on the Mac (90 sec)

SSH in and run the preflight script:

```bash
ssh echo@echos-mac-mini-1
cd /Users/echo/Documents/Claude/Projects/ECHO

# Pull this runbook + preflight script. Two options:
#   Option 1: clone this repo somewhere on the Mac and copy the migration/ dir over
#   Option 2: paste preflight.sh contents from PR #2 directly into a file
#
# The simplest is Option 2:
curl -fsSL https://raw.githubusercontent.com/digitalmavericks/claude/claude/fix-echo-slack-reconnect-dyFTw/migration/preflight.sh -o /tmp/preflight.sh
chmod +x /tmp/preflight.sh

bash /tmp/preflight.sh
```

**Read the verdict at the bottom carefully.**

- **Verdict says "Port 18789 free":** safe, proceed to Step 2.
- **Verdict says "Port 18789 in use":** the script printed the process name. Decide:
  - If it's `openclaw`, `node` (a different node service), or anything load-bearing → **ABORT this runbook.** Re-routing Funnel will cut that service off the public internet. Tell Claude what you found.
  - If it's a stale dev server, a test endpoint, or you remember what you put there and can take it down → proceed.

If the preflight reports any **MISSING** required files (`load-echo-config.sh`, `ECHO-CONFIG.md`), STOP. Those need to exist before the deploy script will work.

---

## Step 2 — Restart OpenClaw to pick up v2026.4.27 (60 sec)

```bash
launchctl kickstart -k gui/$(id -u)/ai.openclaw.openclaw
sleep 5
openclaw --version    # expect 2026.4.27
```

If OpenClaw doesn't restart cleanly, do NOT run `openclaw doctor --fix` — per `shared-decisions.md` it's BANNED (it gutted the Slack config last time and required full backup restoration). Tell Claude what's failing.

---

## Step 3 — Run the Slack migration script (3 min)

```bash
cd /Users/echo/Documents/Claude/Projects/ECHO
bash deploy/16-slack-socketmode-to-events.sh
```

Expected end-of-run output:
- `funnel live: https://echos-mac-mini-1.tail074467.ts.net/slack/events  →  localhost:3333`
- `launchd service loaded — will auto-restart on crash and on boot`
- `handler responding on localhost:3333`
- `Public Slack Request URL: https://echos-mac-mini-1.tail074467.ts.net/slack/events`

If the script fails, the most likely cause is missing `load-echo-config.sh` (handler crashes on startup with `FATAL: SLACK_SIGNING_SECRET and SLACK_BOT_TOKEN required`). Check:

```bash
tail -50 /Users/echo/Documents/Claude/Projects/ECHO/deploy/logs/slack-handler.err
```

---

## Step 4 — Slack app configuration (5 min, in a browser, biometric-gated)

Open https://api.slack.com/apps/A0AGDD10JBX:

- [ ] **Socket Mode** (left nav) → toggle **OFF**.
- [ ] **Event Subscriptions** (left nav) → toggle **ON**.
  - Request URL: `https://echos-mac-mini-1.tail074467.ts.net/slack/events`
  - Slack will ping it with a `url_verification` challenge. The handler should reply instantly. URL shows ✓ Verified.
- [ ] **Subscribe to bot events** — add at minimum:
  - `app_mention`
  - `message.im`
  - `message.channels` (only if Echo listens passively in channels)
  - `message.groups`, `message.mpim` (only if Echo joins private channels / multi-DMs)
- [ ] **Save Changes**.
- [ ] **Install App** → **Reinstall to Workspace** (accept any new scopes).
- [ ] Copy the new Bot User OAuth Token (`xoxb-...`).
- [ ] On the Mac, paste it into `/Users/echo/Documents/Claude/Projects/ECHO/ECHO-CONFIG.md` under `SLACK_BOT_TOKEN=`.
- [ ] On the Mac, restart the handler so it picks up the new token:
  ```bash
  launchctl kickstart -k gui/$(id -u)/com.digitalmavericks.echo.slack
  ```

---

## Step 5 — Verify end-to-end (2 min)

In Slack, mention `@echo` in any channel Echo is in. Expect a reply within ~2 seconds.

If no reply:
```bash
# Tail the handler logs
tail -f /Users/echo/Documents/Claude/Projects/ECHO/deploy/logs/slack-handler.out
tail -f /Users/echo/Documents/Claude/Projects/ECHO/deploy/logs/slack-handler.err
```

Quick external smoke test:
```bash
curl -s "https://echos-mac-mini-1.tail074467.ts.net/health"
# expect: {"ok":true,"transport":"events_api","ts":...}
```

---

## Step 6 — Update shared-memory files (3 min)

Edit `/Users/echo/Documents/Claude/Projects/ECHO/shared-memory/shared-state.md`. Three changes:

**Change 1.** In `## ECHO Configuration`, replace these lines:

```
- **Tailscale Funnel:** Active at OS level (echos-mac-mini-1.tail074467.ts.net → 127.0.0.1:18789). OpenClaw tailscale.mode = "off" (managed externally)
- **Slack transport:** Socket Mode (webhook mode not supported on v2026.4.15)
```

with:

```
- **Tailscale Funnel:** Active at OS level (echos-mac-mini-1.tail074467.ts.net → 127.0.0.1:3333 for /slack/events). OpenClaw tailscale.mode = "off" (managed externally)
- **Slack transport:** Events API over Tailscale Funnel (cutover 2026-04-26). Standalone Node handler at services/slack-handler writes to Supabase agent_messages; ECHO polls.
```

**Change 2.** In `## Known Issues`, remove:

```
- Events API migration: Blocked until OpenClaw supports webhook mode (v2026.4.22+)
```

**Change 3.** Update the `**Last updated:**` header to `2026-04-26 by Cowork (post-Slack-cutover)`.

Append to `/Users/echo/Documents/Claude/Projects/ECHO/shared-memory/echo-to-cowork-briefing.md`:

```
### 2026-04-26 — Slack cutover to Events API complete
- OpenClaw upgraded v2026.4.15 → v2026.4.27.
- Slack transport: Socket Mode → Events API over Tailscale Funnel (port 3333).
- launchd service: com.digitalmavericks.echo.slack (KeepAlive=true).
- Public URL: https://echos-mac-mini-1.tail074467.ts.net/slack/events.
- Charter v4 §10 still references Socket Mode — needs DC update (see Step 7).
- The 3-week reconnect-storm issue is resolved.
```

---

## Step 7 — Charter v4 §10 update (DC, when convenient)

Current §10 (per `shared-decisions.md` 2026-04-24) authorizes Socket Mode as the only transport. Replace with:

```
§10. Slack transport. ECHO connects to Slack via the Events API delivered
over Tailscale Funnel. The standalone slack-handler service at
services/slack-handler (port 3333) receives events, verifies signatures
(HMAC-SHA256 over X-Slack-Request-Timestamp + body), and writes them to
Supabase echo.agent_messages for ECHO to consume. Socket Mode is retired
as of 2026-04-26. If the slack-handler process is unreachable, Slack will
retry 3x with exponential backoff; messages dropped after that surface
as gaps in echo.agent_messages.

Operational invariants:
- The handler runs under launchd label com.digitalmavericks.echo.slack
  with KeepAlive=true (auto-restart on crash and on boot).
- The handler must NEVER bypass signature verification, regardless of
  any flag, env var, or "test mode" suggestion.
- If the handler is restarted, the launchctl kickstart command is:
    launchctl kickstart -k gui/$UID/com.digitalmavericks.echo.slack
```

Commit this to whatever document is the canonical Charter v4 source.

---

## Rollback (if anything breaks beyond a quick fix)

```bash
# 1. Stop the Events API handler
launchctl bootout gui/$(id -u)/com.digitalmavericks.echo.slack 2>/dev/null || true

# 2. Drop Funnel config
tailscale funnel --bg off
tailscale serve reset

# 3. Restore whatever was on port 18789 (manual — depends on what it was)
#    e.g., re-launch that service so Funnel auto-rebinds the path it had

# 4. In Slack dashboard, re-enable Socket Mode and re-create the App-Level Token (xapp-)
# 5. Restart OpenClaw so it reconnects via Socket Mode
launchctl kickstart -k gui/$(id -u)/ai.openclaw.openclaw

# 6. Revert shared-state.md and echo-to-cowork-briefing.md changes from Step 6
```

This puts you back on Socket Mode (the broken-but-familiar state).

---

## What I (Claude) cannot do from this sandbox

- SSH or run anything on the Mac
- Edit `/Users/echo/Documents/Claude/Projects/ECHO/...`
- Click in the Slack app dashboard
- Verify any of the above succeeded

What I CAN do:
- Walk DC through any step interactively if something's unclear or fails
- Diagnose log output DC pastes back
- Update this runbook based on what we find on the Mac
- Refine the preflight script if it misses a check

Paste any error / log line into chat and I'll triage.
