#!/usr/bin/env bash
# Compares the repo's directory tree against tools/expected-tree.txt.
# Directories are derived from git's view: every tracked or untracked-but-not-ignored file's
# ancestors. Generated, gitignored directories (dist, node_modules, .vite, sdcard manifests)
# therefore never count, and refs/ and docs/business/ are excluded by .gitignore itself.
# Exit 0 on match, 1 with a diff otherwise.
set -u
cd "$(dirname "$0")/.."
actual=$(git ls-files -co --exclude-standard -z \
  | tr '\0' '\n' \
  | awk -F/ 'NF>1 { p=$1; print p; for (i=2;i<NF;i++) { p=p"/"$i; print p } }' \
  | LC_ALL=C sort -u)
if diff <(printf '%s\n' "$actual") tools/expected-tree.txt; then
  echo "verify-tree: OK ($(printf '%s\n' "$actual" | wc -l | tr -d ' ') directories match tools/expected-tree.txt)"
else
  echo "verify-tree: FAIL (lines with '<' exist but are undeclared; '>' are declared but missing)"
  exit 1
fi
