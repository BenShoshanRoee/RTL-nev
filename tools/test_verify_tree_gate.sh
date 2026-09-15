#!/usr/bin/env bash
# Negative test for verify-tree: an undeclared directory must make it fail with a diff.
set -u
cd "$(dirname "$0")/.."
tools/verify_tree.sh >/dev/null || { echo "verify-tree-gate: FAIL (clean tree does not pass; negative test would be vacuous)"; exit 1; }
rogue=packages/__verify_tree_gate_rogue__
mkdir -p "$rogue"
trap 'rmdir "$rogue"' EXIT
if out=$(tools/verify_tree.sh 2>&1); then
  echo "verify-tree-gate: FAIL (undeclared directory was NOT caught)"; exit 1
fi
grep -q "$rogue" <<<"$out" || { echo "verify-tree-gate: FAIL (failed, but diff did not name the rogue directory)"; exit 1; }
echo "verify-tree-gate: OK (clean tree passes; undeclared directory rejected and named)"
