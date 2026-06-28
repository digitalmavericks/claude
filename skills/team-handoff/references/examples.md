# HANDOFF EXAMPLES (worked)

## Example 1 — Video-production handoff (ARA → CHIEF, creative needs verification)
File: `_Handoffs/ARA_TO_CHIEF_sheridan-act7-visual_2026-06-28.md`

```
# HANDOFF: ARA → CHIEF
Topic: Act 7 visual track (new act) — verify before it reaches Angel
Date: 2026-06-28  ·  Status: OPEN
Lane: B (DC-gated)
Ship-gate: PENDING-SENTINEL

## What I did
Extracted the Act 7 visual track on the v1.0 script. Mapped every beat to the 5-layer stack, neon scarcity held, cold-steel grade.
Tool routing assigned per shot (Grok Imagine AGENT default, Veo3 hero).

## What I need from you
Run the Sentinel/Gate-0 verify vs v1.0 (key-line fidelity + offer fidelity + look rules), then clear or return fixes. Owner: CHIEF. ETA: today.

## Artifacts
/Volumes/ExternalOpenClawWorkspace/MaverickServer/AIO_Brand/AIO_WEBINAR_SHERIDAN_BUILD/SCRIPT_120MIN/DCxARA_Review/ACT_7_VISUAL_TRACK_v1.0.md

## Verification state
Not yet verified. Self-checked for neon/warmth/silence rules. Needs independent Sentinel before Angel generates (would waste generation budget otherwise).
```
→ CHIEF reads it, runs the Sentinel, writes back `CHIEF_TO_ARA_act7-verify_2026-06-28.md` (CLEARED or fixes) and updates the inbound file's Status. Only when Ship-gate = SENTINEL-PASSED does it route to ECHO/Angel.

## Example 2 — General coordination handoff (CHIEF → ECHO, ops, ready to ship)
File: `_Handoffs/CHIEF_TO_ECHO_tier1-clips-tracker_2026-06-28.md`

```
# HANDOFF: CHIEF → ECHO
Topic: Stand up Tier-1 generation tracking + asset library
Date: 2026-06-28  ·  Status: OPEN
Lane: A (autonomous build-only)
Ship-gate: N/A

## What I did
Scaffolded PRODUCTION/ workspace + the pre-populated status tracker. Verified ARA's 3 production docs (cleared). Angel cleared for Tier-1 (3 shots) once DC's ref images land.

## What I need from you
Take ownership of the tracker + asset library; file each generated clip by Act/Beat/ShotType/Tool; ping #dc-echo when a Tier-1 test clip is ready for review. Owner: ECHO. ETA: ongoing.

## Artifacts
/Volumes/ExternalOpenClawWorkspace/MaverickServer/AIO_Brand/AIO_WEBINAR_SHERIDAN_BUILD/PRODUCTION/GENERATION_STATUS_TRACKER.md
/Volumes/ExternalOpenClawWorkspace/MaverickServer/AIO_Brand/AIO_WEBINAR_SHERIDAN_BUILD/PRODUCTION/ECHO_PRODUCTION_BRIEF.md

## Verification state
N/A (ops handoff, no creative claim).
```
→ ECHO works it, updates Status → IN-PROGRESS, then DONE with a one-line result.

## The pattern
Creative/claim handoffs carry a Ship-gate and stay `PENDING-SENTINEL` until a different-agent Sentinel returns 95+ on the final version. Pure-ops handoffs are `N/A` and can run Lane A autonomously. Either way: file = payload, Slack = ping, map = source of truth.
