#!/usr/bin/env bash
# Negative test for the no-domain-vocabulary rule: core-semantic must not know what a cart is.
set -u
cd "$(dirname "$0")/.."
fail() { echo "vocab-gate: FAIL ($1)"; exit 1; }
pnpm exec eslint packages/core-semantic >/dev/null 2>&1 || fail "clean core-semantic fails eslint; negative test would be vacuous"
plant=packages/core-semantic/src/__vocab_gate_plant__.ts
printf 'export const cartTotal = 1;\n' > "$plant"
trap 'rm -f "$plant"' EXIT
out=$(pnpm exec eslint packages/core-semantic 2>&1) && fail "commerce vocabulary in core-semantic was NOT caught"
grep -q "__vocab_gate_plant__.ts" <<<"$out" || fail "eslint failed but did not name the planted file"
grep -qi "domain vocabulary" <<<"$out" || fail "eslint failed but not with the no-domain-vocabulary message"
echo "vocab-gate: OK (commerce vocabulary in core-semantic rejected by file name)"
