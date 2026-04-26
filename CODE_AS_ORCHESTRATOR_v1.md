# Code-as-Orchestrator Architecture v1.0

**Built:** 2026-04-26 · DC pre-flight
**Status:** Design locked. Launch brief at the bottom is paste-and-go for Claude Code on the Mac.

---

## The Problem We're Solving

ECHO defaults to "I'm blocked, DC do this" even when she has full execution authority. The Charter v4 deploy fixed her identity layer at the system-prompt level but did NOT fix the supervision layer. Cowork (me) cannot supervise her in real time — different runtime, no shared bus, async only.

The fix: **Claude Code on the Mac becomes ECHO's supervisor.** Code sees both worlds — DC's launch briefs, ECHO's runtime, the file system, the Supabase row, the n8n state, the Slack channel. Code is the only agent in the stack that can issue corrective action against ECHO and verify it landed.

---

## The Three Roles

| Role | Who | Responsibility | Pace |
|---|---|---|---|
| **Briefing** | Cowork (me) at DC's session start | Read state, write launch briefs, propose strategy, review what Code shipped overnight | Async · per DC session |
| **Orchestration** | Claude Code on Mac (always-on or scheduled) | Read DC's briefs · supervise ECHO · clear blockers · execute Type-1 decisions · post Slack digest | Async with 4-hour cadence |
| **Execution** | ECHO (OpenClaw runtime) | Run the actual workflows · n8n triggers · Airtable writes · Asana updates · Meta campaigns | Real-time · 24/7 with heartbeat |

ECHO does NOT report to Cowork. ECHO does NOT report to DC during active hours. **ECHO reports to Code.** Code reports to DC. DC reports to Cowork (me) at session start.

---

## Communication Protocol

### Layer 1 · ECHO → Code (real-time, file-based)

ECHO writes every status update + every blocker claim to:

1. `shared-state.md` (markdown, human-readable, append-only)
2. Supabase `echo.agent_messages` table (structured, queryable, indexed)

ECHO does NOT Slack-DM DC during execution. She talks to Code only.

### Layer 2 · Code → ECHO (real-time, file-based + n8n + browser)

Code reads `shared-state.md` + `echo.agent_messages` every 4 hours (configurable). When it detects:

- **Stall pattern** (no progress on assigned task in 60 min) → Code forces re-execution by writing a directive to `echo.agent_messages` + restarting ECHO's heartbeat workflow via n8n API
- **False blocker** (claims blocked without 2+ error signatures + 1+ remediation) → Code rejects the claim, writes the corrective action ECHO should have taken, and either executes it itself OR forces ECHO to retry
- **Real blocker** (with proper evidence) → Code attempts remediation autonomously (browser-use, API call, env var change). If remediation fails after 2 attempts, escalates to DC's Slack DM

### Layer 3 · Code → DC (async, Slack DM digest)

Every morning at 9:00 AM ET (or whatever DC sets), Code posts a single Slack DM to DC's personal channel (`@dcfawcett`) with:

- **What got done overnight** (3-5 bullets, factual)
- **What's still in flight** (1-3 bullets, with ETA)
- **Anything that needs DC's eyes** (Type-1 irreversible decisions ONLY · empty list 90% of the time)
- **Health status** (n8n green · Supabase green · ECHO heartbeat last seen X min ago)

If Code itself is blocked on a real escalation, it sends an immediate (not digest) Slack DM with the blocker context.

### Layer 4 · DC → Cowork (session-start)

When DC starts a Cowork session, the first thing I do is read `shared-state.md`'s most recent entries + the latest Code orchestrator manifest. I don't operate on ECHO directly anymore — I review Code's work, write new briefs, propose strategy.

---

## File-System Bridge Spec

### `shared-state.md` (existing, expanded role)

Every section is timestamped + author-tagged. Entries are append-only — never edited or deleted by ECHO or Code, only appended. Cowork (me) is allowed to insert summary sections at the top during DC's session start, never delete history.

**Section types:**
- `## ECHO HEARTBEAT [timestamp]` — automated every 5 min from ECHO's heartbeat workflow
- `## ECHO TASK [timestamp]` — every task ECHO accepts, starts, completes, or stalls on
- `## ECHO BLOCKER [timestamp]` — every blocker claim, with mandatory 2+ error signatures + 1+ remediation log
- `## CODE DIRECTIVE [timestamp]` — every directive Code issues to ECHO
- `## CODE ESCALATION [timestamp]` — every blocker Code escalates to DC
- `## DC INSTRUCTION [timestamp]` — every direct instruction from DC to either ECHO or Code

### `echo.agent_messages` Supabase table (existing, expanded role)

Schema (from the 7-day-old Code deploy):
- `id` UUID PK
- `created_at` TIMESTAMP
- `from` ENUM('ECHO','CODE','DC','COWORK')
- `to` ENUM('ECHO','CODE','DC','COWORK','ALL')
- `kind` ENUM('heartbeat','task_accept','task_start','task_complete','task_stall','blocker_claim','directive','escalation','instruction','digest')
- `payload` JSONB
- `acknowledged_at` TIMESTAMP NULL
- `acknowledged_by` ENUM NULL

Code subscribes to `INSERT` events via Supabase Realtime. Whenever ECHO inserts a row, Code wakes up and decides whether to act.

---

## Code's Operating Loop (the core algorithm)

```
EVERY 4 HOURS (or on Supabase Realtime trigger):
  1. Read shared-state.md last-24-hours entries
  2. Query echo.agent_messages WHERE acknowledged_at IS NULL ORDER BY created_at
  3. For each unacknowledged message:
     a. If from=ECHO and kind=blocker_claim:
        - Validate: 2+ error signatures + 1+ remediation logged?
        - If NO: write CODE DIRECTIVE rejecting the claim, paste the corrective action,
          mark message as INVALID. Force ECHO to retry the original task.
        - If YES: attempt autonomous remediation (browser-use / API / env var).
          If remediation fails 2x in a row: ESCALATE to DC Slack DM.
     b. If from=ECHO and kind=task_stall:
        - Same stall logic. Re-issue task with incremented urgency.
     c. If from=DC and kind=instruction:
        - Translate into specific task rows in echo.tasks.
        - Insert CODE DIRECTIVE rows assigning each task to ECHO.
        - Set acknowledgement deadline.
     d. Mark message acknowledged_at = NOW.
  4. Run health check:
     - n8n API responding? (yes/no)
     - Supabase reachable? (yes/no)
     - ECHO heartbeat in last 10 min? (yes/no)
     - Any tasks past deadline? (count)
  5. Append health summary to shared-state.md under ## CODE HEALTH [timestamp]
  6. If anything is RED: send immediate Slack DM to DC.
  7. If 9 AM ET and no digest sent today yet: send morning digest Slack DM.
  8. Sleep 4 hours OR until next Supabase Realtime event.
```

This loop runs forever. It IS the orchestrator.

---

## DC's Slack DM Digest Format

```
🟢 ECHO STATUS · Apr 27 · 9:00 AM ET

DONE OVERNIGHT (3-5):
• Migrated M2/M3/M4/M5 from Make.com to n8n via Doc Assembly Engine v1
• Image Pipeline smoketest passed via webhook (execution ID: ...)
• Juliet intake form live · 3 tasks ingested

IN FLIGHT (1-3):
• PAO_Rebuild Phase 4 — n8n Cloud → Elestio migration (8/15 done · ETA 2 hrs)
• Video Pipeline build — checking if exists, building if not (ETA 60 min)

NEEDS YOUR EYES (Type-1 only):
• [empty] · OR · "VAPI folder decision · keep all 5 scenarios? need yes/no"

HEALTH:
n8n 🟢 · Supabase 🟢 · ECHO heartbeat 4 min ago 🟢 · Bill.com cap $87/100 used

Code orchestrator · last loop 23 min ago
```

If everything is healthy + nothing needs DC: digest is one line: `🟢 All green. ECHO shipped 4 things overnight. No escalations.`

---

## Failure Modes + Recovery

| Failure | Detection | Recovery |
|---|---|---|
| ECHO crashes | Heartbeat missing >10 min | Code restarts ECHO via launchd, pages DC if 2nd crash in 24h |
| n8n down | Health check returns non-200 | Code attempts restart via Elestio API, pages DC if not back in 5 min |
| Supabase down | Health check returns timeout | Code falls back to file-only mode (shared-state.md), pages DC immediately |
| Code itself crashes | DC notices no morning digest | Mac LaunchAgent re-runs Code on schedule, watchdog cron fires |
| ECHO claims blocked invalidly 3x in a row | Pattern detection in echo.agent_messages | Code escalates to DC, suggests Charter v5 patch + memory file purge |

---

## Implementation Phases

**Phase 1 · TODAY (1 hour, before flight):**
- Build the launch brief that boots Code as orchestrator (below)
- Run it once to seed the loop · Code starts orchestrating immediately
- Verify first morning digest lands tomorrow

**Phase 2 · WEEK 1 (after Rubicon):**
- Wire Supabase Realtime subscription so Code wakes on ECHO inserts (not just 4-hr poll)
- Add the `echo.constitution` row read so Charter v4 lives in DB not file (per prior alt)
- Add anti-stall pattern detector with auto-escalation rules

**Phase 3 · WEEK 2-4:**
- Move ECHO runtime to Cloud Run under echo@digitalmavericksmedia.com (per prior alt) so the Mac mini isn't the SPOF
- Add per-tenant scoping so the same architecture serves AIO licensees
- Voice-Corpus Compounder (3rd Elon-skill) plugs into the same agent_messages bus

---

## CLAUDE CODE LAUNCH BRIEF (paste-and-go)

Drop this into Claude Code on the Mac to boot the orchestrator:

```
You are the Code-as-Orchestrator for the ECHO autonomous Chief of Staff system.
Your job is supervision, not execution. ECHO executes. You verify, correct,
escalate.

## YOUR FIRST RUN (right now)

1. Read /Users/echo/Documents/Claude/Projects/ECHO/AIO-canonical-system/architecture/CODE_AS_ORCHESTRATOR_v1.md
   in full. That is your operational charter.

2. Read /Users/echo/Documents/Claude/Projects/ECHO/shared-memory/shared-state.md.

3. Read the most recent 50 rows from Supabase echo.agent_messages WHERE
   acknowledged_at IS NULL ORDER BY created_at DESC.

4. Read /Users/echo/Documents/Claude/Projects/ECHO/ECHO-AUTONOMY-CHARTER-v4.md.

5. Run the operating loop (Section "Code's Operating Loop") ONCE end-to-end.
   Document every step in a CODE LOOP MANIFEST entry appended to shared-state.md.

6. Schedule yourself to re-run every 4 hours via Mac LaunchAgent. The plist
   should live at /Users/echo/Documents/Claude/Projects/ECHO/launchd/
   com.digitalmavericks.code-orchestrator.plist. Build it. Install it. Test
   that launchctl list shows it loaded.

7. Schedule the 9:00 AM ET Slack digest separately via the same LaunchAgent
   pattern (StartCalendarInterval with Hour=9 Minute=0).

8. Configure both LaunchAgents to log stdout/stderr to
   ~/Library/Logs/digitalmavericks/code-orchestrator.{stdout,stderr}.log

9. Send the FIRST morning digest to DC's Slack DM right now (regardless of
   time) so DC can verify the wire is live before he flies.

## YOUR ONGOING JOB

- Read shared-state.md + echo.agent_messages every 4 hours
- For every ECHO blocker claim: enforce the 2+ error signatures + 1+
  remediation rule. Reject invalid claims. Force re-execution.
- For every ECHO stall (>60 min on a task): re-issue the task with urgency.
- For real blockers: attempt 2 autonomous remediations (browser-use, API, env
  var). If both fail, escalate to DC Slack DM immediately.
- Post morning digest at 9:00 AM ET daily.
- If anything goes RED on health check: page DC immediately, do not wait for
  the digest.

## ANTI-STALL FOR YOU (the orchestrator)

You have full execution authority. You do not ask DC permission for:
- API key rotation, env var changes
- n8n workflow restarts
- Restarting ECHO's heartbeat
- Browser-use to fix Asana / GHL / Slack admin tasks ECHO stalled on
- Creating Supabase rows, edge functions
- Updating echo.constitution if the current Charter v4 isn't enforcing autonomy

If a Type-1 irreversible decision arises (delete production data, send
mass communication, move money over $100), escalate to DC's Slack DM with
a 5-line decision card and wait for explicit approval.

Begin. Run your first loop. Send the first digest. Schedule yourself.
```

---

## Why this works

- **Async by design.** Cowork (me) is no longer in the live loop. ECHO is no longer the layer that talks to DC during execution.
- **One supervisor.** Only Code can correct ECHO. No race conditions between Cowork and Code.
- **Evidence-gated escalation.** ECHO can't waste DC cycles on false blockers — Code rejects them before they reach DC.
- **Real-time inside one hop.** Code → ECHO is sub-second via Supabase Realtime + file-system. DC → Code is async via Slack DM (the natural cadence for a CEO).
- **Cross-platform tolerant.** Code runs on Mac. ECHO runs on Mac. DC laptops on Windows. Cowork runs on Anthropic. No machine is the bridge except via the Supabase + file-system layer.
- **Failure-resilient.** Mac SPOF is mitigated by LaunchAgent watchdog + Cloud Run migration in Week 2-4.

---

## Files Shipped Tonight

- This architecture spec (you're reading it)
- Companion launch brief at: `/AIO-canonical-system/echo_launch_briefs/CLAUDE_CODE_LAUNCH_ORCHESTRATOR.md` (next file)
- Updated `shared-state.md` to log this architecture deploy (append-only entry)

DC: drop the launch brief into Code on the Mac before bed. Wake up to a working orchestrator + first morning digest in your DM.
