# CHIEF Slack Identity Install Pack

Status: build and technical-test package only. Nothing in this directory is a live receipt.

This package implements DC's 2026-07-26 ruling for a dedicated CHIEF Slack identity:

- Phase 1: post outbound messages under CHIEF's own Slack bot UID.
- Phase 2: receive strict `@CHIEF` app mentions and atomically mirror them into `_AgentBus/chief/`.
- Relay only: this package does not route prompts to an LLM, start a Hermes gateway, or make cloud Claude/Codex become CHIEF.

The repository is public. Never put tokens, signing secrets, internal messages, live receipts, or machine-specific topology in this repository.

## What it installs

```text
~/.hermes/profiles/chief/
  RELAY_ONLY
  config.yaml
  bin/chief-send
  lib/
  events-bridge/
  logs/
  state/

~/.local/bin/chief-send
~/Library/LaunchAgents/com.digitalmavericks.chief-slack-events.plist  # Phase 2
```

Secrets are written only to `~/.hermes/.env` with mode `0600`. DC must also store the bot token and Phase 2 signing secret in 1Password. They are never accepted as command-line arguments.

## Slack app setup

Create a new Slack app specifically for CHIEF. Do not reuse ECHO's, ARA's, DC's, Claude's, or Codex's token.

Phase 1 needs:

- Bot token scope: `chat:write`
- `CHIEF_SLACK_BOT_TOKEN`
- `CHIEF_SLACK_BOT_USER_ID`
- `CHIEF_SLACK_TEAM_ID`
- `CHIEF_SLACK_DEFAULT_CHANNEL_ID`

Phase 2 additionally needs:

- Bot token scope: `app_mentions:read` (keep Phase 1 `chat:write`)
- Bot event: `app_mention`
- `CHIEF_SLACK_SIGNING_SECRET`
- `CHIEF_SLACK_API_APP_ID`
- `CHIEF_SLACK_ALLOWED_CHANNEL_IDS`
- `CHIEF_SLACK_ALLOWED_USER_IDS`
- `CHIEF_AGENTBUS_ROOT`, whose final path component must be `_AgentBus`
- A public HTTPS Request URL that securely forwards only `/slack/events` to the loopback listener

Reinstall the Slack app after adding scopes, then invite the CHIEF bot to `#rogue-ops` (`C0BL2AM4KCY`). The installer fails closed unless that channel is the default and appears in the inbound/outbound allowlist.

The signed law names only the bot token. Slack Events API also requires the dedicated signing secret. Phase 2 is blocked until DC creates and stores that secret.

## Build checks

Run before review:

```bash
./tests/run.sh
```

The test suite is offline. It uses synthetic events and temporary directories only.

## Phase 1 install

On the Mac mini, from this directory:

```bash
./install.sh --phase 1
```

The installer:

1. Runs the offline tests.
2. Creates a relay-only CHIEF profile.
3. Prompts without echo for the bot token if it is not already in `~/.hermes/.env`.
4. Prompts for non-secret identity values if missing.
5. Installs `chief-send` without starting a gateway or sending a message.

It does not post the acceptance receipt automatically.

### Phase 1 acceptance

After CHIEF review and DC's token setup:

```bash
printf '%s\n' 'CHIEF dedicated Slack identity Phase 1 receipt' \
  | chief-send --channel "$CHIEF_SLACK_DEFAULT_CHANNEL_ID"
```

`chief-send` first calls Slack `auth.test`, fails closed unless the returned bot UID and team ID match the configured CHIEF identity, then posts. Its JSON receipt contains the Slack timestamp, channel, bot UID, and message SHA-256. It never prints the token or message body.

PASS requires:

1. The Slack message appears under a new CHIEF UID, not DC's or ECHO's.
2. A CHIEF-origin mention of ECHO generates a real notification/readback.

The second condition is a human/recipient readback, not something this sender can self-certify.

## Phase 2 install

Before installation, inventory live ports, LaunchAgent labels, and the current Tailscale Funnel configuration. Do not assume the default port is free.

```bash
./install.sh --phase 2
```

This installs but does not start the LaunchAgent. To start only after review:

```bash
./install.sh --phase 2 --activate
```

The HTTP listener binds to `127.0.0.1` only. Configure a dedicated HTTPS ingress, such as an approved Tailscale Funnel route, to forward `/slack/events` to the selected local port. Do not expose the health route as an authorization signal; it proves only that the relay process is running.

Set the Slack Event Subscriptions Request URL to:

```text
https://<approved-host>/<dedicated-chief-path>/slack/events
```

The bridge:

- verifies Slack HMAC-SHA256 against the raw request body;
- rejects an invalid, missing, non-positive, or oversized request body before parsing;
- caps request workers, bounds the listen backlog, and applies a five-second connection/read timeout before HMAC work;
- rejects timestamps outside five minutes;
- uses constant-time signature comparison;
- allowlists the Slack team, app, channel, and human sender;
- accepts only `app_mention`;
- requires the exact configured CHIEF bot mention in the event text;
- rejects bot/subtype/self events;
- deduplicates durably by Slack `event_id`;
- writes one deterministic AgentBus file atomically;
- reconstructs that exact file from the signed retry if the durable ledger says delivered but the file is missing, and fails closed if the same event ID carries changed content;
- deliberately does **not** append the shared `_AgentBus/_log.jsonl`; current producers do not share one locking protocol, so this pack treats the atomic inbox file plus its private SQLite dedupe ledger as the safe Phase 2 contract;
- never posts a Slack reply or invokes an LLM.

### Phase 2 acceptance

PASS requires an authorized user to mention CHIEF in the allowed channel and a verifier to prove:

- one file appeared under `_AgentBus/chief/`;
- the file contains the expected Slack `event_id`, team, app, channel, sender, and mention;
- the same Slack retry produces no second file;
- a non-mention, wrong channel, wrong user, wrong workspace/app, stale request, invalid signature, and bot-authored event each produce no file.

## Rollback

This pack does not delete live state.

To stop Phase 2:

```bash
launchctl bootout "gui/$(id -u)/com.digitalmavericks.chief-slack-events"
```

Then restore the timestamped backups printed by `install.sh`. Do not remove the profile, event database, inbox records, logs, or root `.env` until a separate retention/deletion decision is signed.

Root `.env` updates also create mode-`0600` pre-mutation copies under `~/.hermes/.env.backups/chief-slack/`. Those contain the same secrets as the source and must remain in the approved secret boundary.

## Non-claims

- A successful install is not a live CHIEF route.
- A successful Slack post is not proof that ECHO read it.
- A received Slack event is not proof that CHIEF consumed it.
- A cloud `@Claude` or `@Codex` response is not CHIEF.
- This relay does not change current CHIEF inbox law or create a resident Fable worker.
- Relay-only inheritance against the installed Hermes version remains a Mac acceptance test; offline source inspection cannot certify local runtime behavior.
