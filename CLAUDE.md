# RTL Environments — standing brief

Read this every session. Then read `progress.md`. Do not read the plan in full.

## What this is
RTL agentic environments and evals sold to frontier labs, environment vendors and
data foundries. Hebrew e-commerce first, Arabic second. Fork of MobileGym (Apache-2.0);
all MobileGym bundled content is CC BY-NC, deleted at fork time, blocked forever by CI.

Four layers. Only the first three are fixed:
1. **Semantic layer** (`packages/core-semantic`, `packages/domains/*`) — headless domain
   model: entities, operations, invariants, state machine. No UI, no language, no
   commerce vocabulary in the core.
2. **Surface generator** (`packages/surface-gen`, `packages/rtl-primitives`, `sim/`) —
   renders a domain as unlimited synthetic RTL interfaces, sampled from a parameter
   space grounded in a survey of real stores.
3. **Verification engine** (`bench/rtlenv/judge`) — judges rollouts by diffing structured
   state. Deterministic. No LLM-as-judge, ever.
4. **Domain + form factor** — parameters. Commerce is the first implementation of an
   interface, never an assumption. Viewport is a config value, not a product.

**Pathology library** (`packages/pathology`, `bench/tasks/*/pathology`) is the actual
product: bidi truncation, numeral direction leaks, unmirrored affordances,
script-mixed input rejection. Everything else is plumbing.

## Operator constraint
The operator reads Python and ML, not TypeScript. They verify by running commands and
reading output, never by reading diffs. Every sub-chunk ends with something runnable.
Never say "this should work." Run it. If it cannot be verified here, mark it MANUAL.

## Non-negotiables (check before every commit)
- [ ] One seeded PRNG: `Rng` from `rng.ts` / `rng.py` (sfc32, byte-identical across languages), named child seeds per subsystem. `Math.random()` / unseeded `random` forbidden elsewhere; ESLint + ruff S311 + pytest lint enforce it.
- [ ] Money is `{ minor: integer, currency }` with a per-currency exponent table. Cross-currency arithmetic throws. No floats in any money path.
- [ ] CSS logical properties only (`margin-inline-start`, never `margin-left`).
- [ ] No hardcoded Hebrew or Arabic in components. All strings from `res/strings.*.json`.
- [ ] `packages/core-semantic` imports nothing from `packages/domains/*`. CI-enforced.
- [ ] Every asset under `content/` has a provenance manifest entry, or the build fails.
- [ ] Every task has `unchanged_subtrees` and `cheat_surface`. Every task ships ≥5 fixtures
      (1 correct, 1 clearly wrong, ≥3 plausibly wrong). Matchers are mutation-tested.
- [ ] Deterministic under a fixed seed. Same seed, same output, tested.
- [ ] Licence allowlist: MIT, Apache-2.0, BSD-*, ISC, SIL OFL, CC0, Unlicense. Ask before adding any dependency.
- [ ] Nothing NC-licensed, nothing brand-derived, nothing from `refs/` ships. Brand terms live in `tools/licence/brandlist.txt`; waivers in `policy.yaml` always carry a reason and an expiry.
- [ ] No emoji in code or commits. `🔧` in docs marks manual steps only.

## Token discipline
- Read `progress.md` first. It is the state. Do not explore the repo to rediscover it.
- The plan is `docs/plan/rtl-implementation-plan.md`. Find the current sub-chunk with
  `rg -n "Sub-chunk X.Y.Z" docs/plan/rtl-implementation-plan.md` and read only that section (to the next `#### Sub-chunk`). Never read the plan in full.
- Read specific line ranges. Never dump a file you are not editing.
- Prefer `rg` to answer "where is X."
- Summarise outputs to the operator; give them the command to run instead of pasting output.
- Multi-file tasks: list the plan, get confirmation, then execute.
- One sub-chunk per session unless told otherwise. Finish, update `progress.md`, give
  verification commands, stop.

## Working rules
- Ask before installing any dependency (justify it, check licence allowlist).
- Ask before touching files outside the current sub-chunk's Files list.
- If the plan is wrong, say so and propose a change. Never deviate silently.
- Uncertain? Say "I have not verified this." Never assert.
- Write the failing test first, show it failing, then make it pass.
- Judges are security-critical. Default assumption: the judge is too permissive.

## Skill routing
`subchunk` is the outer loop for every sub-chunk. `verify` always runs at the end.
The middle four trigger on what you TOUCH (check paths before editing), not on the
sub-chunk's name. More than one can apply: a pathology injector is `rtl` + `determinism`.

| Skill | Trigger |
|---|---|
| `subchunk` | Starting any sub-chunk from the plan |
| `judge` | `bench/rtlenv/judge/`, any rubric, matcher, reward function, task fixture |
| `rtl` | bidi, layout, numerals, typography, shaping, any Hebrew/Arabic rendering |
| `provenance` | Any file under `content/`, any new dependency |
| `determinism` | Randomness, generation, sampling, seeding |
| `verify` | Writing acceptance criteria or verification for any sub-chunk |

## Commands (root `Makefile`)
Node is pinned to 24 LTS in `.npmrc`; always go through `pnpm`, never bare `node`. TypeScript stays on 5.x.
Filtered pnpm calls always take `--fail-if-no-match`. A gate must pass clean before its negative test counts.
| Command | Does |
|---|---|
| `make setup` | Install JS (pnpm) and Python (uv) workspaces from lockfiles |
| `make verify` | Full local gate: verify-tree + gates + lint + test (+ licence from 1.1.3, provenance from 4.1.1) |
| `make verify-tree` | Directories from git's file view diffed against `tools/expected-tree.txt` |
| `make gates` | Negative tests: each gate must pass clean, then reject a planted violation (boundary, tree, licence x3, entropy x2, vocabulary) |
| `make test` | vitest + pytest |
| `make lint` | dependency-cruiser, ESLint (`eslint.config.mjs`: recommended on packages/, entropy ban), tsc, ruff (S311) |
| `make provenance` | Audit `content/MANIFEST.json` against every file under `content/` |
| `make licence` | `scan.py --mode all`: NC guard + content manifest, dependency licences, brand guard. Same command as CI |
| `make purge-audit` | Local only: purge manifest equals upstream minus `sim/` (needs `refs/upstream/mobilegym`) |
| `make sbom` | CycloneDX 1.5 for both ecosystems into `dist/sbom.cdx.json`, validated |
| `make smoke` | Built simulator serves `/` and `/cdn/` (same script as the CI e2e-smoke job) |
| `make release` | Local dry run: wheel, SBOM, container. The real release is `git tag vX.Y.Z && git push --tags` |

## Layout (see plan Appendix A for the full tree)
`packages/` TS workspace · `sim/` MobileGym fork (`UPSTREAM.md`; never edit `refs/upstream`) · `bench/` Python bench + tasks ·
`packages_py/` shipped wheel · `content/` provenance-tracked assets · `refs/` gitignored
survey captures · `tools/` CLIs · `docs/` · `.github/workflows/`

## Current phase
**Phase 2 of 12 — Semantic Layer & Verification Engine.** Next sub-chunk: **2.2.2 Partial Credit & Reward Shaping.**
Authoritative state lives in `progress.md`; update that, not this line, unless the phase changes.
