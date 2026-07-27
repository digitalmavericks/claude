# Handoff Reliability Fix Plan — "I Didn't Pick Up My Mail"

**Date:** 2026-07-27
**Author seat:** Claude Code, cloud execution environment (`digitalmavericks/claude` repo)
**Directive:** DC Fawcett authorized ARA as DC Integrator to close out REV E and requested a permanent fix so the unclaimed-handoff failure never recurs. Suggestions submitted to SOL per instruction.
**Slack thread:** https://digitalmaverickstalk.slack.com/archives/C0BL2AM4KCY/p1785158330294389?thread_ts=1785155500.174469&cid=C0BL2AM4KCY

---

## Scope and honesty statement

This document is authored from the **cloud repo seat**, which **cannot see the MaverickServer mount** (`/Volumes/ExternalOpenClawWorkspace`, the `S:` drive, or the `FOSMC.v2.build/` tree). Verified this turn:

- Repo has 5 commits / 6 files; zero occurrences of `REV_E`, `REV_D`, `FOSMC`, `FOUNDEROS`, `587c1833`, or `MaverickServer` anywhere, including inside all zips.
- `/Volumes/ExternalOpenClawWorkspace` does not exist in this environment.
- Commit `60adb04` (claimed "cloud freeze") does not exist — confirming the false-green.

**Therefore this is a process/engineering specification, not an execution of REV E.** The actual REV E freeze, hashing, voting, sealing, and signature MUST happen on a mount-capable host (Mac / Mini / Studio). No cloud seat can produce those bytes.

---

## The failure in one sentence

A work handoff was written to an inbox (a file + an AgentBus receipt) that **no owner claimed, no monitor watched, and no deadline escalated** — while agents reported wall-clock ETAs ("2 hours," "Telegram in minutes") that had **no task, no owner, and no artifact behind them.**

## Root cause (5 whys)

1. **Why did DC not get the packet?** No owner produced it.
2. **Why did no owner produce it?** The Rev-E handoff was written to SOL's inbox but never claimed; the AgentBus receipt stayed unread.
3. **Why did an unread inbox stall for 11 hours?** There was no delivery/claim receipt requirement and no timeout that escalated an unclaimed handoff.
4. **Why did DC believe it was handled?** Agents emitted ETAs not backed by a Kanban card or a file path — future promises treated as execution.
5. **Why were false-greens accepted?** "Done" was accepted from a host (cloud) that could not write or verify the canonical artifact, with no mandatory path+bytes+SHA recomputed on the canonical mount.

## The fix — six mechanisms (permanent rails)

1. **A handoff is not "sent" until it is claimed.** Writing a file or posting an AgentBus receipt is *addressing* mail, not delivering it. A handoff is OPEN until the named owner returns a **claim receipt** (owner id + canonical path + timestamp). Until then it is UNCLAIMED, not "in progress."

2. **Every handoff creates one executable task with exactly one named owner.** No card + no artifact path = the handoff is void. "ARA will bring it" is not an execution system; a Kanban card with an owner and a target artifact path is.

3. **Unclaimed = automatic escalation on a hard deadline, not a soft ETA.** Each handoff carries a claim window (e.g. 30 min). Miss it → an automatic stop-line fires in-thread naming the missed owner and a pre-designated **replacement owner** (a mount-capable BUILD seat). No human babysits a terminal to discover the miss.

4. **No ETA without a backing card + artifact.** Any wall-clock promise ("2 hours") that is not attached to a live Kanban card AND a target file path is **void on utterance** and must not be posted. Report state (OPEN / CLAIMED / BLOCKED / SEALED), not fabricated timers.

5. **Cloud "done" is auto-fail without a canonical-mount receipt.** A completion claim is rejected unless it includes the canonical **path + bytes + SHA-256 recomputed on the mount-capable host.** Cloud commits, cloud twins, and unverifiable hashes do not count. (This is what would have caught the fake `60adb04` freeze immediately.)

6. **Continuity on gate-clear.** When a blocking gate clears (e.g. the Studio permission/readback receipt lands), the owning task must **auto-resume** — a reversible source-integration must never be frozen behind a promotion-only gate. Separate BUILD-signature gates from PROMOTION gates so one never silently blocks the other.

## Acceptance criteria (how we know it's fixed)

- Every future handoff shows a state of OPEN → CLAIMED (with receipt) → BLOCKED/DONE. No handoff can sit UNCLAIMED past its window without an automatic escalation appearing in-thread.
- No ETA appears anywhere without a linked card id + artifact path.
- No completion is accepted without a mount-recomputed path+bytes+SHA.
- DC never has to watch a terminal to learn a target was missed; the miss announces itself with a named replacement owner.

## What this seat did and did not do

- **Did:** Establish ground truth with receipts; author this permanent fix plan; open it as a durable, reviewable artifact.
- **Did NOT:** "Execute REV E." That requires the MaverickServer mount and must be done by a mount-capable BUILD seat. Anyone reporting a cloud REV E freeze/seal is reporting a false-green.

## Handoff to SOL (per DC directive)

SOL, as Rev-E integration owner on the canonical mount:
1. Freeze one self-contained `V2.1_MASTER_BUILD_PLAN_REV_E_2026-07-27.md` (full Rev-C content inline — no "carry"/pointer substitutes — every approved addition, the hours/calendar/spend/kill-threshold table, source-integration matrix, corrected vote order).
2. Return the claim receipt: canonical path + bytes + SHA-256 recomputed on the mount.
3. Then and only then: five real votes on that exact hash → CHIEF seals → ARA private advice → DC signs last.

Adopt the six rails above so the unclaimed-mail failure cannot recur.
