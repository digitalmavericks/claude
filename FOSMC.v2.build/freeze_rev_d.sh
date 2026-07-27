#!/usr/bin/env bash
# Freeze the FounderOS v2.1 Rev D master plan and bind the ratification ballot to its hash.
# Refuses to re-bind a ballot that already carries a DIFFERENT (already-voted) plan hash.
set -euo pipefail
cd "$(dirname "$0")"

PLAN="FOUNDEROS_V2_1_REV_D_MASTER_PLAN.md"
BALLOT="FOUNDEROS_V2_1_REV_D_RATIFICATION_BALLOT.md"
SUMS="FOUNDEROS_V2_1_REV_D_SHA256SUMS.txt"

sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }

for f in "$PLAN" "$BALLOT"; do
  [ -f "$f" ] || { echo "ERROR: missing $f" >&2; exit 1; }
done

HASH="$(sha256 "$PLAN")"
echo "Rev D master-plan SHA-256: $HASH"

EXISTING="$(grep -oE '[0-9a-f]{64}' "$BALLOT" | head -n1 || true)"
if [ -n "$EXISTING" ] && [ "$EXISTING" != "$HASH" ]; then
  echo "REFUSING: ballot is bound to a different plan hash ($EXISTING)." >&2
  echo "A vote may already be cast against that hash. Resolve manually." >&2
  exit 2
fi

sed -i -E "s|^(PLAN_SHA256:).*$|\1 $HASH|" "$BALLOT"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$PLAN" "$BALLOT" > "$SUMS"
else
  shasum -a 256 "$PLAN" "$BALLOT" > "$SUMS"
fi
echo "Wrote $SUMS"
echo "Verify with: sha256sum --check $SUMS   (or: shasum -a 256 -c $SUMS)"
