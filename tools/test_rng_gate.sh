#!/usr/bin/env bash
# Negative tests for the randomness ban. Each half requires a clean pass first, then plants
# one violation and asserts the linter rejects it, naming the file.
#   1. ESLint: Math.random() in a package source file
#   2. pytest lint + ruff S311: `import random` used in a bench module
set -u
cd "$(dirname "$0")/.."
fail() { echo "rng-gate: FAIL ($1)"; exit 1; }

pnpm exec eslint . >/dev/null 2>&1 || fail "clean tree fails eslint; negative test would be vacuous"
uv run pytest bench/tests/test_no_unseeded_random.py -q >/dev/null 2>&1 || fail "clean tree fails the pytest randomness lint"
uv run ruff check . >/dev/null 2>&1 || fail "clean tree fails ruff"

plant_ts=packages/pathology/src/__rng_gate_plant__.ts
printf 'export const leak = Math.random();\n' > "$plant_ts"
trap 'rm -f "$plant_ts"' EXIT
out=$(pnpm exec eslint . 2>&1) && fail "Math.random() in a package was NOT caught by eslint"
grep -q "__rng_gate_plant__.ts" <<<"$out" || fail "eslint failed but did not name the planted file"
grep -qi "Math.random" <<<"$out" || fail "eslint failed but did not mention Math.random"
rm -f "$plant_ts"; trap - EXIT
echo "rng-gate: OK eslint (Math.random() in packages/ rejected by file name)"

plant_py=bench/rtlenv/__rng_gate_plant__.py
printf 'import random\n\nVALUE = random.random()\n' > "$plant_py"
trap 'rm -f "$plant_py"' EXIT
out=$(uv run pytest bench/tests/test_no_unseeded_random.py -q 2>&1) && fail "import random in bench was NOT caught by the pytest lint"
grep -q "__rng_gate_plant__.py:1" <<<"$out" || fail "pytest lint failed but did not name file and line"
out=$(uv run ruff check "$plant_py" 2>&1) && fail "random.random() was NOT caught by ruff S311"
grep -q "S311" <<<"$out" || fail "ruff failed but not with S311"
rm -f "$plant_py"; trap - EXIT
echo "rng-gate: OK python (import random in bench/ rejected by pytest lint and ruff S311)"
