# FounderOS v2.1 — Rev D Master Plan (Canonical, Self-Contained)

**Status:** FROZEN CANDIDATE — awaiting Council five-seat ratification and DC sovereign signature
**Artifact type:** Single, self-contained master plan. This is the one document the five-seat vote is cast against. Its SHA-256 is recorded in `FOUNDEROS_V2_1_REV_D_SHA256SUMS.txt` and referenced by the ratification ballot.

## 0. Provenance note (read this first)

This Rev D was authored fresh and committed directly to the `digitalmavericks/claude`
repository so that a real, verifiable artifact exists on the real remote. Prior
"frozen / committed 60adb04" reports did not land in this repository: that commit,
the `FOSMC.v2.build/` directory, and every file it referenced were absent from every
branch, the reflog, the object store, and the filesystem. The work had been produced
in ephemeral sandboxes and never pushed. See the PR description for the incident write-up.

The source documents referenced in the Council thread — Rev C, the individual approved
addenda, the sealed five-vote bundle, DC High Agency Directive #3, and the SOL Studio
onboarding receipt — were **not present in this repository**. Where their content is
required below, this document states the requirement in self-contained form and marks a
slot with `>>> PASTE CANONICAL SOURCE TEXT HERE <<<`. If canonical text for any source
exists elsewhere, paste it into the marked slot and re-run `freeze_rev_d.sh` before the
vote so the frozen hash covers the real text.

## 1. Scope and non-goals

In scope: one owner, one plan, one frozen hash, one five-seat vote, one DC BUILD
signature, and a separate live-promotion authorization. Out of scope: approving further
isolated addenda. No fragment is ratified on its own after this freeze — only this whole
document is.

## 2. Governance — the five Council seats

The five accountable seats are: ECHO, ARA, SOL, Chief, ROGUE. Ratification requires all
five to vote APPROVE against the exact frozen master-plan hash (see the ballot). A vote
cast against any other hash is void.

>>> PASTE CANONICAL SOURCE TEXT HERE (Rev C governance section) <<<

## 3. Autonomous Identities — least-privilege controls

Every autonomous identity runs under least privilege: scoped credentials, auditable
execution, explicit and bounded autonomous-action limits, and no standing
`danger-full-access`. Any elevation is time-boxed, logged, and revoked on completion.

>>> PASTE CANONICAL SOURCE TEXT HERE (Autonomous Identities addendum) <<<

## 4. DC High Agency Directive #3

DC escalation conditions and stop-the-line authority are consolidated here so the plan is
self-contained.

>>> PASTE CANONICAL SOURCE TEXT HERE (DC High Agency Directive #3) <<<

## 5. Studio BUILD readiness

BUILD-readiness facts to be confirmed by receipt before build start: M4 Max Studio online;
Tailscale running; model runtime live; canonical MaverickServer mount read/write proven;
ping/pong proven. These establish BUILD readiness only — not promotion clearance.

>>> PASTE CANONICAL SOURCE TEXT HERE (SOL Studio onboard receipt) <<<

## 6. BUILD vs live PROMOTION — hard separation

BUILD (architecture, code, tests, offline assembly) may proceed the moment DC signs the
BUILD authorization. Live PROMOTION is separately gated and never implied by BUILD
authorization or by any terminal reporting "green."

## 7. Promotion gates (all must be closed before live promotion)

1. Permission scopes narrowed to least privilege; no residual `danger-full-access`.
2. Independent Mini byte readback verified.
3. Independent ThinkStation byte readback verified.
4. Reproducibility of the build from the frozen inputs.
5. Rollback path proven.
6. Observability in place.
7. Security review signed off.
8. Five-seat vote recorded against this exact hash.
9. DC's separate live-promotion authorization signed.

## 8. Controlled build sequence

Freeze this plan -> five-seat vote against the hash -> DC BUILD authorization -> SOL begins
controlled BUILD offline -> promotion gates closed in parallel -> DC live-promotion
authorization -> promote.

## 9. Stop-the-line

Any seat may stop the line on a genuine safety, security, or integrity signal. Operator
burnout is an explicit stop-the-line signal, not a reason to push harder.

## 10. Ratification

The ratification ballot is `FOUNDEROS_V2_1_REV_D_RATIFICATION_BALLOT.md`. It is bound to
this document's SHA-256 by `freeze_rev_d.sh`. Verify integrity at any time with
`sha256sum --check FOUNDEROS_V2_1_REV_D_SHA256SUMS.txt` (or `shasum -a 256 -c` on macOS).
