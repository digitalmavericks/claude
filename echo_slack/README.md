# echo_slack — Events API over Tailscale Funnel

Replaces Socket Mode (the WebSocket that's been dropping for weeks) with the
Slack Events API. Slack POSTs to a public HTTPS URL fronted by Tailscale
Funnel; Funnel terminates TLS and forwards to a local FastAPI server.

```
Slack -- HTTPS --> Tailscale Funnel edge -- WireGuard --> Mac mini :8080 --> FastAPI
```

No persistent socket. If Tampa Wi-Fi blips, Slack just retries the next webhook
(built-in retry + dedupe).

## Files

| File | Purpose |
|---|---|
| `server.py` | FastAPI app. `/slack/events` verifies signatures, handles URL verification, dedupes retries, dispatches to handlers in background. `/healthz` for monitoring. |
| `handlers.py` | Event router. Stubs for `app_mention` and DMs — wire your Echo logic here. |
| `client.py` | `slack_sdk.WebClient` wrapper for outbound `chat.postMessage` etc. |
| `config.py` | Reads secrets from `~/.openclaw/.env.slack`. |

## Deploy on the Mac mini

1. Clone this repo to `~/.openclaw` (or set `OPENCLAW_HOME`).
2. Create the env file (never commit this):
   ```
   cp config/.env.slack.example ~/.openclaw/.env.slack
   chmod 600 ~/.openclaw/.env.slack
   $EDITOR ~/.openclaw/.env.slack    # paste real SLACK_BOT_TOKEN + SLACK_SIGNING_SECRET
   ```
3. Run the deploy script:
   ```
   bash scripts/deploy_slack.sh
   ```
   It creates a venv, installs deps, registers the LaunchAgent, runs a health
   check, and turns on Funnel for port 8080. The script prints the public
   `https://...ts.net/slack/events` URL when it's done.

## Configure the Slack app

At https://api.slack.com/apps/A0AGDD10JBX:

1. **Event Subscriptions** → Enable Events → Request URL: paste the URL the
   deploy script printed. Slack pings it with a `url_verification` challenge;
   the server responds.
2. **Subscribe to bot events**: at minimum `app_mention`, plus `message.im`
   for DMs. Add `message.channels` if Echo listens in channels.
3. **OAuth & Permissions** → Reinstall to Workspace.
4. **Settings → Socket Mode** → **DISABLE**. (This is the thing that's been
   breaking. Goodbye.)
5. Revoke the `xapp-...` App-Level Token — no longer used.

## Operate

```
launchctl kickstart -k gui/$(id -u)/ai.openclaw.slack    # restart server
tail -f ~/.openclaw/logs/slack.log                        # follow logs
tailscale funnel status                                   # confirm public exposure
curl -s https://<machine>.<tailnet>.ts.net/healthz        # external smoke test
```

## Why this is more reliable than Socket Mode

- **No long-lived connection to drop.** Each event is one HTTPS POST.
- **Slack retries automatically** with exponential backoff and an `X-Slack-Retry-Num` header. The server dedupes by `event_id` so handlers run once.
- **Funnel cert is auto-provisioned and auto-renewed** by Tailscale; no Let's Encrypt cron to maintain.
- **Outbound calls (`chat.postMessage`) are also stateless HTTPS** — no socket to keep alive in either direction.
- **Signature verification** uses the signing secret (HMAC-SHA256 over timestamp + body), so the public URL is safe to expose.
