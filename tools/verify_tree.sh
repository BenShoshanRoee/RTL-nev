#!/usr/bin/env bash
# Compares the repo's directory tree against tools/expected-tree.txt.
# Exit 0 on match, 1 with a diff otherwise. No external tools beyond find/sort/diff.
set -u
cd "$(dirname "$0")/.."
actual=$(find . -type d \
  -not -path '.' \
  -not -path './.git' -not -path './.git/*' \
  -not -path '*/node_modules' -not -path '*/node_modules/*' \
  -not -path './refs' -not -path './refs/*' \
  -not -path './docs/business' -not -path './docs/business/*' \
  -not -path '*/dist' -not -path '*/dist/*' \
  -not -path '*/__pycache__' -not -path '*/__pycache__/*' \
  -not -path '*/.venv' -not -path '*/.venv/*' \
  -not -path '*/.pytest_cache' -not -path '*/.pytest_cache/*' \
  -not -path '*/.ruff_cache' -not -path '*/.ruff_cache/*' \
  -not -path '*/*.egg-info' -not -path '*/*.egg-info/*' \
  | sed 's|^\./||' | LC_ALL=C sort)
if diff <(printf '%s\n' "$actual") tools/expected-tree.txt; then
  echo "verify-tree: OK ($(printf '%s\n' "$actual" | wc -l | tr -d ' ') directories match tools/expected-tree.txt)"
else
  echo "verify-tree: FAIL (lines with '<' exist but are undeclared; '>' are declared but missing)"
  exit 1
fi
