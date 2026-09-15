#!/usr/bin/env bash
# Gate test for the core-semantic boundary. Two halves, both required:
#   1. the clean tree passes dependency-cruiser (otherwise half 2 proves nothing)
#   2. a planted core-semantic -> domains/commerce import is rejected, naming the rule
# The planted import is reverted on every exit path.
set -u
cd "$(dirname "$0")/.."
target=packages/core-semantic/src/index.ts
[ -f "$target" ] || { echo "depcruise-gate: FAIL ($target missing)"; exit 1; }

if ! pnpm exec depcruise --config .dependency-cruiser.cjs packages >/dev/null 2>&1; then
  echo "depcruise-gate: FAIL (clean tree does not pass; the negative test would be vacuous)"
  pnpm exec depcruise --config .dependency-cruiser.cjs packages 2>&1 | grep -E 'error|warn' | head -5
  exit 1
fi

cp "$target" "$target.bak"
trap 'mv "$target.bak" "$target"' EXIT
printf '\nimport "../../domains/commerce/src/index";\n' >> "$target"
out=$(pnpm exec depcruise --config .dependency-cruiser.cjs packages 2>&1)
status=$?
if [ "$status" -eq 0 ]; then
  echo "depcruise-gate: FAIL (planted core-semantic -> domains import was NOT caught)"
  exit 1
fi
if ! grep -q "core-semantic-must-not-import-domains" <<<"$out"; then
  echo "depcruise-gate: FAIL (rejected, but not by the boundary rule)"
  grep -E 'error' <<<"$out" | head -5
  exit 1
fi
echo "depcruise-gate: OK (clean tree passes; planted import rejected by core-semantic-must-not-import-domains)"
