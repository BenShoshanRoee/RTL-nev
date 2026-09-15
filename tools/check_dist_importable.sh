#!/usr/bin/env bash
# Every built workspace package must load in plain Node (no bundler, no Vite resolution).
# A buyer's runtime and the Python bench call these through Node; extensionless ESM imports
# would pass vitest and fail there.
set -u
cd "$(dirname "$0")/.."
status=0
for pkg in packages/core-semantic packages/domains/* packages/rtl-primitives packages/pathology packages/surface-gen; do
  [ -f "$pkg/dist/index.js" ] || { echo "dist-import: MISSING $pkg/dist/index.js (run pnpm -r build)"; status=1; continue; }
  if pnpm node --input-type=module -e "await import('./$pkg/dist/index.js')" 2>/tmp/dist-import.err; then
    echo "dist-import: OK $pkg"
  else
    echo "dist-import: FAIL $pkg"; head -3 /tmp/dist-import.err; status=1
  fi
done
exit $status
