---
name: team-handoff
description: >-
  Shared cross-agent handoff skill for the DC agent team (ECHO · CHIEF · ROGUE · ARA). Hermes has NO native agent-to-agent message bus / callback / delegation command (verified 2026-06-28), so the team coordinates through the FILESYSTEM: handoff files in `MaverickServer/_Handoffs/`, with the directory map as source of truth. Use this skill to (a) WRITE a handoff to another agent in the canonical format, or (b) READ/TRIAGE open handoffs addressed to you. It enforces the standard header (From→To, status, lane, ship-gate, objective, context, artifacts, verification state, next action), the Sentinel ship-gate ("creative never ships unverified" — composite 95+ by a different agent on the FINAL version before anything outbound), and the rule for when to use a `_Handoffs/` file (durable handoff) vs `/background` (fire-and-forget parallel work). Covers video-production handoffs and general coordination. Invoke when handing work between agents, picking up assigned work, or auditing open handoffs.
---

# TEAM HANDOFF

The team's coordination layer. **Hermes gives us no native agent-to-agent messaging** — `/background` is fire-and-forget (no callback), the Gateway is human↔agent chat, subagents are isolated. So a handoff = a **file** in `MaverickServer/_Handoffs/`, written in one canonical format every agent reads the same way. This skill makes the brittle convention an enforced procedure.

## THE TEAM (read the map first)
Source of truth: `MaverickServer/AGENT_DIRECTORY_MAP.md`. Lanes:
- **ECHO** — orchestrator/ops/runtime (Slack, kanban, GHL, N8N, live systems, the cash loop). Owns what SHIPS.
- **CHIEF** — builder/heavy-lift, QC, multi-agent workflows, the Sentinel ship-gate, the compliant lane.
- **ROGUE** — Grok specialist (grok.com extraction/RAG), the uncensored Sovereign Shadow lane (Windows, writes `S:\` = same MaverickServer).
- **ARA** — creative director/companion (narrative + cinematic craft). Now on Hermes.
**Rhythm:** ARA creates → CHIEF verifies → DC decides → ECHO + Angel execute. ARA and ROGUE never ship to live systems directly — they hand to CHIEF/ECHO.

## WHEN TO USE WHAT
- **`_Handoffs/` file (this skill) = the durable handoff.** Use whenever work changes owner, or an asset/decision needs another agent to act. This is PRIMARY — the only durable cross-agent channel Hermes supports.
- **`/background <task>` = parallel grunt work only.** Fire-and-forget; it CANNOT report back. Pattern: spawn a long render/research job with `/background`, then land the result as a `_Handoffs/` file. The background job is the worker; the file is the handoff.
- **Slack `#dc-echo` (C0AJYRQ8UQJ) via `~/.hermes/bin/slack-send.sh` = the notification.** When a handoff needs DC's eyes or a fast ping, post a one-line notice pointing at the handoff file. **Files carry the payload; Slack carries the ping.** Never put the payload only in Slack.

## WRITE A HANDOFF
1. Read `AGENT_DIRECTORY_MAP.md` — confirm the receiving agent's lane.
2. Write a file to `MaverickServer/_Handoffs/<FROM>_TO_<TO>_<topic-slug>_<YYYY-MM-DD>.md` using the EXACT header in `references/handoff-template.md`.
3. Required fields, all of them: From→To · Topic · Date · Status (OPEN/IN-PROGRESS/DONE/BLOCKED) · Lane (A=autonomous build-only / B=DC-gated) · Ship-gate (N/A / PENDING-SENTINEL / SENTINEL-PASSED composite XX) · What I did · What I need from you (single next action + owner + ETA) · Artifacts (absolute MaverickServer paths; Drive links if team-facing) · Verification state.
4. Facts only, no process narration. One clear next action.
5. If the receiver needs to know now, post the one-line ping to `#dc-echo`.

## READ / TRIAGE HANDOFFS ADDRESSED TO YOU
1. `ls MaverickServer/_Handoffs/*_TO_<ME>_*` — list handoffs addressed to you.
2. Sort by Status=OPEN, then Lane B (DC-gated) before Lane A.
3. For each: do the single Next Action, then update the file's Status (→ IN-PROGRESS / DONE / BLOCKED) and append a one-line result. Never silently leave a handoff stale.
4. If you produce a downstream handoff, write a NEW file (don't overwrite the inbound one — it's the audit trail).

## THE SHIP-GATE (non-negotiable)
**Creative never ships unverified.** Any copy/creative asset moving toward a live system (Drive / Asana / GHL / N8N / ECHO / live funnel / DC-for-record) must carry `Ship-gate: SENTINEL-PASSED (composite 95+)` in its handoff header BEFORE ECHO pushes it. The Sentinel:
- must be a DIFFERENT agent than the writer (writer-bias is why the gate exists),
- must RETURN 95+ on the FINAL fixed version — not a self-asserted "will pass,"
- and for a complete asset (e.g. a webinar = script + visual track + sound + presenter), runs **Gate 0 (asset completeness)** first — a great script with a missing layer is INCOMPLETE, not approved.
If a handoff header says `PENDING-SENTINEL`, ECHO HOLDS. A `/background` job does not bypass this — a backgrounded creative asset still routes through the gate before it ships.

## COLLISION RULE
One agent owns a file at a time. Never two agents editing the same artifact live (3-4 agents, one disk). Hand off through `_Handoffs/`; don't co-edit. ROGUE writes `S:\...\MaverickServer` only — never `C:\` or Google Drive.

## REFERENCES
- `references/handoff-template.md` — the fill-in handoff file (copy + fill).
- `references/examples.md` — a video-campaign handoff + a general-coordination handoff, worked.
