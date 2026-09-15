#!/usr/bin/env bash
# End-to-end smoke: the built simulator serves its page and the content root. Used by
# make smoke locally and by the e2e-smoke CI job; the two must stay identical.
set -u
cd "$(dirname "$0")/.."
port=${SMOKE_PORT:-3000}
fail() { echo "smoke: FAIL ($1)"; exit 1; }
[ -f sim/dist/index.html ] || fail "sim/dist/index.html missing; run pnpm --filter @rtl/sim build first"
pnpm --filter @rtl/sim --fail-if-no-match exec vite preview --port "$port" --strictPort >/tmp/smoke-preview.log 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null' EXIT
code=$(curl -s -o /tmp/smoke-index.html -w '%{http_code}' --retry 30 --retry-delay 1 --retry-connrefused --retry-all-errors "http://localhost:$port/")
[ "$code" = "200" ] || fail "GET / returned $code"
grep -q 'id="root"' /tmp/smoke-index.html || fail "page has no #root mount point"
code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$port/cdn/MANIFEST.json")
[ "$code" = "200" ] || fail "GET /cdn/MANIFEST.json returned $code (content root not served)"
echo "smoke: OK (GET / 200 with #root; /cdn/MANIFEST.json 200)"
