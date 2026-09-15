#!/usr/bin/env bash
# Negative tests for the licence firewall. Each half requires the clean tree to pass first,
# then plants one violation and asserts the scanner rejects it, naming the offender.
#   1. brand guard:   a file named shufersal-logo.png under content/
#   2. NC guard:      an asset under content/ with no manifest entry
#   3. dependency:    a GPL-3.0 workspace package installed offline from tools/licence/testdata
# Every plant is reverted on every exit path.
set -u
cd "$(dirname "$0")/.."
scan="uv run python tools/licence/scan.py"
fail() { echo "licence-gate: FAIL ($1)"; exit 1; }

$scan --mode brand >/dev/null 2>&1 || fail "clean tree fails brand mode; negative test would be vacuous"
$scan --mode nc    >/dev/null 2>&1 || fail "clean tree fails nc mode; negative test would be vacuous"
$scan --mode deps  >/dev/null 2>&1 || fail "clean tree fails deps mode; negative test would be vacuous"

# 1. brand guard on a file name
plant=content/shufersal-logo.png
: > "$plant"
trap 'rm -f "$plant"' EXIT
out=$($scan --mode brand 2>&1) && fail "brand-named file was NOT caught"
grep -q "shufersal-logo.png" <<<"$out" || fail "brand mode failed but did not name shufersal-logo.png"
echo "licence-gate: OK brand (shufersal-logo.png rejected by name)"

# 2. NC guard: unlisted asset (the same planted file has no manifest entry)
out=$($scan --mode nc 2>&1) && fail "unlisted content file was NOT caught"
grep -q "unlisted-asset: content/shufersal-logo.png" <<<"$out" || fail "nc mode failed but did not name the unlisted asset"
rm -f "$plant"; trap - EXIT
echo "licence-gate: OK nc (unlisted content asset rejected by name)"

# 3. dependency licence: install a local GPL-3.0 package offline, expect a named failure
cp package.json package.json.bak; cp pnpm-lock.yaml pnpm-lock.yaml.bak
restore() { mv package.json.bak package.json; mv pnpm-lock.yaml.bak pnpm-lock.yaml; pnpm install --prefer-offline --frozen-lockfile --silent >/dev/null 2>&1; }
trap restore EXIT
# link: install; --prefer-offline uses the local store and only reaches the registry if a
# package is missing from it (a cold CI store), so the test behaves the same everywhere.
if ! add_out=$(pnpm add -Dw --prefer-offline ./tools/licence/testdata/gpl-fixture 2>&1); then
  echo "$add_out" | tail -5
  fail "could not install the GPL fixture"
fi
out=$($scan --mode deps 2>&1) && fail "GPL-3.0 dependency was NOT caught"
grep -q "gpl-fixture" <<<"$out" || fail "deps mode failed but did not name gpl-fixture"
grep -q "GPL-3.0" <<<"$out" || fail "deps mode failed but did not name the licence"
echo "licence-gate: OK deps (GPL-3.0 fixture rejected by package name and licence)"
