---
name: determinism
description: Use when touching anything involving randomness, sampling, generation, seeding, shuffling, id generation, timestamps in generated data, or parallel ordering. Covers rng.ts, rng.py, surface-gen, pathology injectors, catalog/copy generators, task setup, rollout runners. One seeded PRNG, named child seeds, same-seed-same-output test required.
---

# determinism — same seed, same bytes

Reproducibility is a vendor-review requirement. A run must be reproducible from its seed.

## Rules
1. **One source of randomness.** `packages/core-semantic/src/rng.ts` and `bench/rtlenv/rng.py`.
   `Math.random()`, `crypto.getRandomValues` for non-security use, Python `random.*` without a
   seeded instance, `numpy.random.*` module functions, `uuid4()`, `Date.now()` in generated
   content: all forbidden outside `rng.*`. ESLint and the pytest lint enforce it.
   Check: `rg -n "Math\.random\(" packages/ sim/src/` returns only `rng.ts`.
   Check: `rg -n "^\s*import random|from random import|np\.random\.(rand|choice|shuffle|seed)" bench/ tools/ packages_py/` returns only `rng.py`.
2. **Named child seeds, never a shared stream.** Derive `child(root, "namespace")` via
   SHA-256(`seed:namespace`) → uint32. Each subsystem (catalog, copy, images, surface,
   pathology, task-setup, rollout) gets its own named child. Adding a draw in one subsystem
   must not change another's output.
3. **No ordering dependence.** Iterate sorted keys, not object/dict insertion order or
   filesystem order. Parallel workers derive seeds from `(root, task_id, rollout_index)`,
   never from worker id or completion order.
4. **No hidden entropy.** No wall-clock in generated data (inject a fixed clock), no
   hash-randomised set iteration (`PYTHONHASHSEED` irrelevant if you sort), no
   `Object.keys` order assumptions, no floating-point accumulation order differences.
5. **Ids are derived**, not random: `hash(namespace, seed, index)` or sequential from the
   child stream.
6. Log the root seed and every child namespace at the top of every run.

## Required tests (write before implementing)
- **Same seed, same output:** generate twice with the same seed, assert deep equality of the
  full output (JSON-serialised, sorted keys). Do this for 3 different seeds.
- **Different seed, different output:** at least one field differs.
- **Isolation:** add an extra draw in namespace A; namespace B's output is byte-identical.
- **Cross-language parity** where both exist (rng.ts / rng.py): 1000 child-seed draws match.
- **Order independence:** run generation over inputs in shuffled order; output sorted by id
  is identical.

## Report
Give the operator the test command and the seeds used. Say "I have not verified this" for
any path where you could not run the same-seed test.
