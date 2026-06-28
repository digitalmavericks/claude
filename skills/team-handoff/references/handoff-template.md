# HANDOFF TEMPLATE — copy, fill, save to `MaverickServer/_Handoffs/<FROM>_TO_<TO>_<topic-slug>_<YYYY-MM-DD>.md`

```
# HANDOFF: <FROM> → <TO>
Topic: <one line>
Date: <YYYY-MM-DD>  ·  Status: OPEN | IN-PROGRESS | DONE | BLOCKED
Lane: A (autonomous build-only) | B (DC-gated)
Ship-gate: N/A | PENDING-SENTINEL | SENTINEL-PASSED (composite XX)

## What I did
<2-4 lines, facts only, no process narration>

## What I need from you
<the single next action + owner + ETA>

## Artifacts
<absolute paths under MaverickServer; Drive links if team-facing>

## Verification state
<for any creative/claim asset: Sentinel status, claim classes A/B/C/D, compliance flags. "N/A" for pure-ops handoffs.>
```

## Field rules
- **FROM/TO** — agent names from `AGENT_DIRECTORY_MAP.md`: ECHO / CHIEF / ROGUE / ARA (or a human: DC / ANGEL).
- **Status** — start OPEN. The receiver flips it as they work. Never leave stale.
- **Lane** — A = the agent may complete autonomously (build-only). B = needs DC's decision before it ships or spends. When unsure, B.
- **Ship-gate** — `N/A` for pure ops. `PENDING-SENTINEL` = creative not yet verified (ECHO HOLDS). `SENTINEL-PASSED (composite XX)` = cleared by a different-agent Sentinel on the final version; only then may it go outbound.
- **What I need from you** — exactly ONE next action. If there are three things, that's three handoffs or a numbered checklist with one owner.
- **Artifacts** — absolute `MaverickServer/...` paths so any agent on any machine resolves them (Rogue sees them as `S:\...`). Drive links only for team-facing assets.

## Naming
`<FROM>_TO_<TO>_<topic-slug>_<YYYY-MM-DD>.md` — e.g. `ARA_TO_CHIEF_sheridan-act7-visual_2026-06-28.md`. Matches the existing `_Handoffs/` convention.
