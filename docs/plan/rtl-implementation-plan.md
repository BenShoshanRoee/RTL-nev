# RTL Environments: Complete Implementation Plan

> **Version:** 1.0
> **Last Updated:** 2026-09-15
> **Purpose:** Step-by-step implementation roadmap for RTL agentic environments and evals
> **Target User:** Solo developer using Claude Code for AI-assisted development
> **Reference:** RTL Agentic Environments — Plan (strategy document)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Summary](#architecture-summary)
3. [Phase 1: Foundation & Infrastructure](#phase-1-foundation--infrastructure)
4. [Phase 2: Semantic Layer & Verification Engine](#phase-2-semantic-layer--verification-engine)
5. [Phase 3: RTL Rendering Layer](#phase-3-rtl-rendering-layer)
6. [Phase 4: Content Pipeline & Provenance](#phase-4-content-pipeline--provenance)
7. [Phase 5: Surface Generator](#phase-5-surface-generator)
8. [Phase 6: Task Authoring System](#phase-6-task-authoring-system)
9. [Phase 7: Evaluation & Training Harness](#phase-7-evaluation--training-harness)
10. [Phase 8: Packaging & Distribution](#phase-8-packaging--distribution)
11. [Phase 9: Security & Vendor Readiness](#phase-9-security--vendor-readiness)
12. [Phase 10: Licensing & Commercial Infrastructure](#phase-10-licensing--commercial-infrastructure)
13. [Phase 11: Go-To-Market Infrastructure](#phase-11-go-to-market-infrastructure)
14. [Phase 12: Arabic Expansion](#phase-12-arabic-expansion)
15. [Appendix A: File Structure](#appendix-a-file-structure)
16. [Appendix B: Manual Steps Summary](#appendix-b-manual-steps-summary)
17. [Appendix C: Development Order](#appendix-c-development-order)
18. [Appendix D: Quick Reference](#appendix-d-quick-reference)

---

## Overview

### What We're Building

A system that produces **RTL agentic environments and evals** sold to frontier AI labs, environment vendors and data foundries.

1. A **semantic layer** models a domain headlessly — entities, operations, state transitions — with no UI and no language assumptions.
2. A **surface generator** renders that domain as unlimited synthetic RTL interfaces, sampling from a parameter space grounded in surveyed real-world design choices.
3. A **verification engine** judges agent rollouts by diffing structured state, detecting unintended side effects, and awarding partial credit — deterministically, with no VLM judge in the loop.
4. A **pathology library** injects the failure modes that only occur in RTL production software: bidirectional truncation, numeral direction leaks, mirrored gesture affordances, script-mixed input rejection.
5. A **transfer harness** measures whether training on generated surfaces improves performance on held-out high-fidelity references.

Hebrew e-commerce ships first. Arabic follows. Domain and form factor are parameters throughout — commerce is the first implementation of the semantic-layer interface, never a baked-in assumption.

Built on a fork of MobileGym (Apache 2.0). All bundled MobileGym content is CC BY-NC and is deleted at fork time. Every asset we ship is original and provenance-tracked.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Base platform | Fork of MobileGym (Apache 2.0) | Browser-hosted sim, programmable state, sub-ms judges, sim-to-real precedent |
| Fork strategy | Hard fork, upstream remote retained, delta documented | We modify the OS and app layers deeply; vendoring would fight us |
| NC content | Deleted at fork commit, blocked by CI forever | CC BY-NC data cannot ship or be trained on commercially |
| RL spec | `verifiers` (Prime Intellect) | De facto standard; Hub distribution; lab-side tooling already supports it |
| Monorepo tool | pnpm workspaces | MobileGym is already pnpm/npm; minimal friction |
| Python tooling | uv + Python 3.11 | Fast, lockfile-native, matches `bench_env` requirements |
| Frontend | React 19 + TypeScript + Vite + Zustand + Tailwind v4 | Inherited from MobileGym; changing it is a rewrite with no payoff |
| State model | Single structured JSON snapshot, fork/diff/restore | Required for deterministic judging and parallel rollouts |
| Judge strategy | Programmatic state-diff only, no LLM-as-judge | LLM judges are stochastic; a silently permissive judge is our worst failure |
| Determinism | Seeded PRNG threaded through all generation | Reproducibility is a vendor-review requirement, not a nicety |
| Image assets | Locally generated (SDXL/Flux via ComfyUI on RTX 5070) | Free, original, fully provenance-recordable, no licence risk |
| Hebrew/Arabic copy | Claude API, prompt + model + seed recorded | Original, auditable, cheap |
| Fonts | SIL OFL only (Noto Sans Hebrew/Arabic, Heebo, Rubik) | Redistributable in a commercial artifact |
| Provenance | JSON manifest, SHA-256 per asset, CI-enforced | Every asset traceable; blocks NC and brand-derived content |
| Licensing tracker | SQLite + Python CLI | Zero infra cost; exclusivity enforcement must be queryable |
| Error tracking | Structured JSON logs to file, no SaaS | Pre-revenue budget; no PII flows through the system |
| CI/CD | GitHub Actions | Free tier sufficient; SBOM and licence gates live here |
| Containers | Docker, published to GHCR | Buyers expect a runnable image, not a README |
| Training | RunPod + prime-rl / verl | Local RTX 5070 (12 GB) cannot run the GRPO reference config |
| Transfer definition | Sim-to-reference (held-out high-fidelity apps) | Sim-to-real-device raises ToS exposure and per-run cost; see D1 |
| Docs | MkDocs Material, published to GitHub Pages | Vendor review expects readable interface docs |

### Sub-Chunk Format

Each sub-chunk follows this structure:

| Field | Description |
|-------|-------------|
| **Objective** | What we're building (one sentence) |
| **Input** | What this component receives |
| **Output** | What this component produces |
| **Files** | Exact file paths to create |
| **Key Logic** | Critical algorithms or decisions |
| **Test Criteria** | How to verify completion |
| **Dependencies** | What must be completed first |
| **Manual Steps** | Actions requiring human intervention (marked with 🔧) |

Sub-chunks are ordered chronologically. Work them in order. No time estimates are given — go at your own pace.

**Verification note:** every sub-chunk's Test Criteria are designed to be executable rather than read. You should be able to confirm completion by running a command and comparing output, not by reviewing a diff.

---

## Architecture Summary

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          RTL ENVIRONMENTS SYSTEM                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   BUYER (lab / vendor)                    AUTHOR (Hebrew / Arabic)       │
│         │                                        │                       │
│         ▼                                        ▼                       │
│   ┌──────────────┐                     ┌────────────────────┐            │
│   │ verifiers    │                     │  Authoring CLI     │            │
│   │ wheel +      │                     │  (task DSL, lint,  │            │
│   │ container    │                     │   preview, test)   │            │
│   └──────┬───────┘                     └─────────┬──────────┘            │
│          │                                       │                       │
│   ┌──────┴───────────────────────────────────────┴──────────┐            │
│   │            BENCH LAYER  (Python, Playwright)            │            │
│   │  task registry · rollout runner · judges · metrics      │            │
│   │  reward shaping · red-team harness · calibration        │            │
│   └──────────────────────┬──────────────────────────────────┘            │
│                          │  __SIM__ / __OS__ control API                 │
│   ┌──────────────────────┴──────────────────────────────────┐            │
│   │            SURFACE LAYER  (React 19 + TS)               │            │
│   │  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  │            │
│   │  │ Surface       │  │ RTL          │  │ Pathology    │  │            │
│   │  │ Generator     │  │ Primitives   │  │ Injectors    │  │            │
│   │  │ (seeded)      │  │ (bidi, num,  │  │ (truncation, │  │            │
│   │  │               │  │  shaping)    │  │  dir-leak…)  │  │            │
│   │  └───────┬───────┘  └──────┬───────┘  └──────┬───────┘  │            │
│   └──────────┼─────────────────┼─────────────────┼──────────┘            │
│              │                 │                 │                       │
│   ┌──────────┴─────────────────┴─────────────────┴──────────┐            │
│   │          SEMANTIC LAYER  (domain-agnostic interface)    │            │
│   │   ┌────────────┐  ┌────────────┐  ┌─────────────────┐   │            │
│   │   │  commerce  │  │ insurance  │  │  <future>       │   │            │
│   │   │  (impl 1)  │  │  (stub)    │  │                 │   │            │
│   │   └────────────┘  └────────────┘  └─────────────────┘   │            │
│   │   entities · operations · invariants · state machine    │            │
│   └──────────────────────┬──────────────────────────────────┘            │
│                          │                                               │
│   ┌──────────────────────┴──────────────────────────────────┐            │
│   │       CONTENT PIPELINE (offline, provenance-tracked)    │            │
│   │  catalogs · he/ar copy · images · fonts · manifests     │            │
│   └─────────────────────────────────────────────────────────┘            │
│                                                                          │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─    │
│                        COMMERCIAL INFRASTRUCTURE                         │
│   licence tracker (which buyer holds which tasks) · release pipeline     │
│   transfer report generator · vendor readiness pack · buyer CRM          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Simulator | Forked MobileGym | React 19, Vite 6, Zustand 5, Tailwind v4 |
| Bench runtime | Python 3.11 + Playwright | Rollouts, judging, metrics |
| RL interface | `verifiers` | Environment, Parser, Rubric, ToolEnv/MultiTurnEnv |
| Package mgmt | pnpm (JS) + uv (Python) | Lockfiles committed |
| Testing | vitest + pytest + Playwright | Judge meta-tests are pytest |
| Determinism | sfc32 implemented in both TS and Python, SHA-256 child seeds | One seed threaded everywhere; cross-language byte parity tested |
| Image generation | ComfyUI + SDXL/Flux, local | Prompt, model hash, seed recorded |
| Text generation | Claude API | Model, prompt hash, temperature recorded |
| Fonts | Noto Sans Hebrew, Noto Sans Arabic, Heebo, Rubik | SIL OFL only |
| Provenance | Custom JSON manifest + SHA-256 | CI-enforced |
| SBOM | CycloneDX (`cyclonedx-py`, `cyclonedx-npm`) | Vendor review artifact |
| Licence scanning | `pip-licenses`, `license-checker`, custom NC guard | CI gate |
| Containers | Docker → GHCR | Reproducible, pinned base images |
| CI/CD | GitHub Actions | Lint, test, licence gate, SBOM, release |
| Training | RunPod + prime-rl (verl) | GRPO; local GPU insufficient |
| Licence tracker | SQLite + Typer CLI | Exclusivity enforcement |
| Docs | MkDocs Material → GitHub Pages | Public interface docs |
| Local dev GPU | RTX 5070 12 GB | Asset generation, small-model inference, browser sims |

---

## Phase 1: Foundation & Infrastructure

**Goal:** Establish the repo, the fork, the licence firewall, and the dev tooling everything else sits on.

**Outcome:** A clean-room fork with zero NC content, CI that blocks licence violations, and a reproducible dev environment.

---

### Chunk 1.1: Repository & Fork

#### Sub-chunk 1.1.1: Monorepo Structure

**Objective:** Create the monorepo skeleton with workspace boundaries that keep domain logic out of the core.

**Input:** None (first task)

**Output:** Empty monorepo with all directories, workspace config, and tooling stubs

**Files:** See [Appendix A](#appendix-a-file-structure) for the complete tree. Key roots:
- `packages/core-semantic/` — domain-agnostic interface
- `packages/domains/commerce/` — first implementation
- `packages/rtl-primitives/` — bidi, numerals, shaping
- `packages/pathology/` — failure injectors
- `packages/surface-gen/` — seeded surface generator
- `sim/` — forked MobileGym simulator
- `bench/` — Python bench layer
- `content/` — generated assets + manifests
- `tools/` — CLIs (authoring, provenance, licensing)
- `tools/expected-tree.txt` — sorted directory list, the source of truth for `make verify-tree`
- `docs/`

**Key Logic:**
- pnpm workspaces for JS packages; uv workspace for Python
- `packages/core-semantic` must have **zero** imports from `packages/domains/*` — enforced by a dependency-cruiser rule in CI
- `sim/` is the fork; everything else is ours
- Root `Makefile` exposes: `setup`, `verify`, `verify-tree`, `test`, `lint`, `provenance`, `licence`, `release`
- `tools/expected-tree.txt` is the checked-in, sorted list of every directory in Appendix A. `make verify-tree` derives the directory set from `git ls-files -co --exclude-standard` (ancestors of every tracked or untracked-but-not-ignored file), sorts it, and diffs against that file. Generated, gitignored directories can never trip it. No `tree` binary anywhere.

**Test Criteria:**
- [ ] `make setup` succeeds on a clean clone
- [ ] `pnpm -r build` completes with no errors
- [ ] `uv sync` resolves the Python workspace
- [ ] Dependency-cruiser fails if you add an import from `core-semantic` to `domains/commerce`
- [ ] `make verify-tree` exits 0; adding an undeclared directory makes it exit non-zero with the diff

**Dependencies:** None

**Manual Steps:**
- 🔧 Create private GitHub repository
- 🔧 Install Node ≥ 22, Python ≥ 3.11, pnpm, uv, Docker

---

#### Sub-chunk 1.1.2: MobileGym Fork & NC Purge

**Objective:** Fork MobileGym into `sim/`, delete every CC BY-NC asset, and record the delta from upstream.

**Input:** Upstream MobileGym repository

**Output:** A clean-room simulator containing only Apache-2.0 code, with an auditable purge record

**Files:**
- `sim/` (forked tree, purged)
- `sim/NOTICE` (preserved and extended)
- `UPSTREAM.md` (fork point commit, our delta, sync procedure)
- `tools/licence/nc_purge_manifest.json` (every path deleted, with SHA-256 of the original)
- `content/MANIFEST.json` (empty-but-valid: `{"schema_version": 1, "assets": []}`, created in the purge commit)
- `tools/licence/purge_fork.py` (deterministic purge from the local upstream clone; writes the manifest; idempotent re-run)
- `tools/licence/scan.py` (minimal: `--mode nc` and `--mode purge-audit`; 1.1.3 extends it add-only)
- `.github/workflows/licence-gate.yml`

**Key Logic:**
- Only the purged tree is committed. The raw upstream tree never enters our history; the upstream commit SHA in `UPSTREAM.md` plus per-file hashes in the manifest are the audit reference.
- Ship an empty-but-valid `content/MANIFEST.json` at fork time. From this commit on, the rule is: **an unlisted file under `content/` fails the build.** 1.1.3 enforces it; 4.1.1 extends the schema.
- Delete in full: `mobilegym-data/`, every `apps/*/data/`, every `apps/*/assets/`, `public/` theme assets, and the downloadable companion dataset. **Never fetch the 1.9 GB data tarball.**
- Keep `os/`, `bench_env/`, `scripts/`, `docs/`, and the *code* of `apps/` and `system/` — then delete the apps themselves once our own exist. **1.1.2 retains exactly two upstream apps as code-only structural reference** (navigation declaration, manifest shape, page wiring); **3.3.1 deletes them** once the Storefront exists.
- Record the fork-point upstream commit SHA in `UPSTREAM.md` so future syncs are diffable.
- Purge is a single commit, separate from any other change, so it is auditable.
- Preserve `NOTICE`, add our own attribution section.

**Test Criteria:**
- [ ] `tools/licence/scan.py --mode nc` reports zero findings
- [ ] `tools/licence/scan.py --mode purge-audit` reports zero findings: manifest equals upstream minus `sim/`, every hash matches
- [ ] `grep -ri "mobilegym-data" sim/` returns nothing outside `UPSTREAM.md`
- [ ] Purge manifest lists every deleted path with a hash
- [ ] `sim/NOTICE` exists and names the upstream project
- [ ] `content/MANIFEST.json` exists, is valid JSON, and has an empty `assets` array
- [ ] Exactly two upstream apps remain under `sim/apps/`, code only (no `data/`, no `assets/`), and both are named in `UPSTREAM.md` as retained-until-3.3.1
- [ ] Simulator still boots (`pnpm --filter sim dev` serves a page, even if empty)

**Dependencies:** 1.1.1

**Manual Steps:**
- 🔧 Read `sim/LICENSE`, `sim/LICENSE-DATA`, `sim/DISCLAIMER.md` and `mobilegym-rl/LICENSE` in full before purging
- 🔧 Verify the vendored third-party licences under `mobilegym-rl/` (rLLM, verl) and record each in `UPSTREAM.md`
- 🔧 Open one trivial upstream PR (typo or doc fix) to confirm the contribution process works before relying on it later

---

#### Sub-chunk 1.1.3: Licence Firewall CI

**Objective:** Make it structurally impossible to reintroduce NC-licensed or brand-derived content.

**Input:** Purged fork

**Output:** A CI gate that fails the build on licence violations

**Files:**
- `tools/licence/scan.py`
- `tools/licence/policy.yaml`
- `tools/licence/brandlist.txt`
- `tools/provenance/schema.json` (minimal v1 manifest schema: `schema_version`, and per asset `path`, `sha256`, `licence`)
- `tools/test_licence_gate.sh` (negative tests: brand-named file, unlisted asset, GPL dependency; part of `make gates`)
- `tools/licence/testdata/gpl-fixture/package.json` (GPL-3.0 package installed offline only during the negative test)
- `.github/workflows/licence-gate.yml`

**Key Logic:**
- `brandlist.txt` has two tiers: a `~` prefix marks an ambiguous term (ordinary word or code identifier) matched only in content-bearing paths and file names; every other term is matched in every tracked text file. The tier changes where a term is searched, never whether a hit fails.
- Every waiver in `policy.yaml` carries a reason and an expiry date; an expired or reason-less waiver is itself a finding.
- JS dependencies are enumerated with `pnpm ls -r --depth Infinity --json` and each licence read from the package's own `package.json`; `pnpm licenses list` omits link-installed packages. Python dependencies come from the uv environment's installed metadata. No licence-listing tool is added.
- Extends the 1.1.2 `scan.py` add-only: `--mode nc` and `--mode purge-audit` keep their behaviour; this sub-chunk adds `--mode deps` and `--mode brand`.
- Three checks, each failing the build:
  1. **NC guard** — (a) any path listed in `nc_purge_manifest.json` that reappears fails; (b) any file under `content/` with no entry in `content/MANIFEST.json` fails; (c) any entry whose `licence` is not on the allowlist (including any `CC-BY-NC*`) fails. Uses the minimal v1 schema defined here. **Forward-compatibility rule: 4.1.1 ADDS fields to this schema; it never redefines, renames or removes a v1 field, and a v1 manifest must always validate against every later schema.**
  2. **Dependency licences** — allowlist (MIT, Apache-2.0, BSD-*, ISC, SIL OFL, CC0, Unlicense). Anything else fails and must be explicitly waived in `policy.yaml` with a reason.
  3. **Brand guard** — scan all text and filenames against `brandlist.txt` (real Israeli and international retailers, banks, payment brands). A hit fails the build. `policy.yaml` carries one dated waiver for `sim/apps/Ebay` and `sim/apps/TencentMeeting` (code-only reference apps retained by 1.1.2), expiring when 3.3.1 deletes them; the waiver must name 3.3.1.
- Runs on every PR and on `main`.
- `make licence` runs the identical checks locally.

**Test Criteria:**
- [ ] Commit a file named `shufersal-logo.png` → CI fails with a brand-guard error
- [ ] Add a GPL dependency → CI fails with a licence error naming the package
- [ ] Add an asset without a provenance entry → CI fails naming the file
- [ ] The empty `content/MANIFEST.json` from 1.1.2 validates against `tools/provenance/schema.json`
- [ ] `make licence` output matches CI output exactly (manual: compare the local run against the Actions log)
- [ ] `make gates` passes: each of the three violations above is rejected by name after a clean pass

**Dependencies:** 1.1.2

**Manual Steps:**
- 🔧 Populate `brandlist.txt` with the top ~150 Israeli retail, bank and payment brand names in Hebrew and English (expand during the Phase 5 survey)

---

#### Sub-chunk 1.1.4: Determinism & Logging Foundations

**Objective:** Thread a single seed through every stochastic path, and establish structured logging.

**Input:** Monorepo skeleton

**Output:** A seed context available to JS and Python, plus JSON logging

**Files:**
- `packages/core-semantic/src/rng.ts`
- `bench/rtlenv/rng.py`
- `bench/rtlenv/logging.py`
- `packages/core-semantic/src/logging.ts`
- `packages/core-semantic/tests/{rng,logging}.test.ts`, `bench/tests/test_{rng,logging,no_unseeded_random}.py`
- `packages/core-semantic/tests/fixtures/rng-parity.json` (generated by `uv run python -m rtlenv.rng --vectors`; both suites assert against it)
- `eslint.config.mjs` (root; replaces sim's upstream config), `tools/test_rng_gate.sh`

**Key Logic:**
- One PRNG algorithm, sfc32, implemented identically in TypeScript and Python (no seedrandom, no numpy): streams are byte-identical across languages, proven by the shared fixture. SHA-256 is implemented in TypeScript so child seeds work synchronously in the browser.
- One root seed produces named child seeds by hashing (`seed:namespace` → SHA-256 → uint32). Never share a single PRNG across subsystems; ordering changes would break reproducibility.
- **Forbid `Math.random()` and unseeded `random`** — an ESLint rule and a pytest lint fail on direct use anywhere outside `rng.ts` / `rng.py`.
- Structured JSON logs: timestamp, level, run_id, seed, task_id, component. Console-pretty in dev, JSON to file otherwise.
- No SaaS error tracker. Logs are files; a run is reproducible from its seed.

**Test Criteria:**
- [ ] Same root seed → identical child-seed sequence across 1000 draws, in both JS and Python
- [ ] `rg -n "Math\.random\(" packages/ sim/apps/Storefront/` returns only `rng.ts` (this fork has no `sim/src/`; upstream `sim/os` and `sim/system` carry 18 inherited calls under a dated ESLint exemption that 3.3.2 removes)
- [ ] ESLint fails on a deliberate `Math.random()` in a package, and the pytest lint plus ruff S311 fail on `import random` in bench (`make gates`)
- [ ] TypeScript and Python streams (next32, float, int, shuffle, weighted) match the shared fixture
- [ ] A log line contains run_id, seed and task_id

**Dependencies:** 1.1.1

**Manual Steps:** None

---

#### Sub-chunk 1.1.5: CI/CD Pipeline

**Objective:** Lint, test, licence-gate, SBOM and build on every push, with zero manual steps in the release path.

**Input:** Repo with tooling

**Output:** Green CI on `main`

**Files:**
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.github/dependabot.yml`
- `.github/actions/setup/action.yml` (local composite action: identical toolchain setup for every job)
- `tools/sbom/generate.py` (one CycloneDX 1.5 document for both ecosystems, validated), `tools/release/version.py` (tag to version), `tools/smoke.sh`
- `Dockerfile`, `.dockerignore` (placeholder image serving the built simulator; 8.1.2 replaces it)
- `Makefile` (`sbom`, `smoke`, `release` dry run)

**Key Logic:**
- CI jobs: `lint` first; `test-js`, `test-py`, `licence`, `sbom` in parallel after it; `build-sim`; then `e2e-smoke` on the built output. `licence` calls `licence-gate.yml` so the gate has one definition. Every job runs the same `make` targets the operator runs locally.
- SBOM generated with CycloneDX for both ecosystems, uploaded as a build artifact on every run (vendor review will ask for it). Generated by our own script over the same package enumeration the licence scanner uses (the npm CycloneDX tool assumes npm's lockfile); serialised and validated by `cyclonedx-python-lib`. Deterministic: sorted components, content-derived serial number.
- Pin all GitHub Actions to a commit SHA, not a tag
- Release workflow is tag-triggered and fully automated: version derived from the tag and applied to every manifest at build time → `make verify` → wheel → SBOM → container (base images pinned by digest) → GHCR push → GitHub Release with wheel, SBOM and simulator build attached. No third-party release or docker actions; only `checkout`, `setup-node`, `setup-uv`, `action-setup`, `upload-artifact`, `download-artifact`, all SHA-pinned.
- Dependabot weekly, grouped, with the licence gate running on its PRs

**Test Criteria:**
- [ ] Push to a branch → all jobs run and pass
- [ ] Deliberately break a test → CI fails and names the test
- [ ] SBOM artifact downloadable from the run, listing both JS and Python deps
- [ ] `git tag v0.0.1 && git push --tags` produces a GitHub Release with no human intervention
- [ ] `make release` (local dry run) builds the wheel, the SBOM and the container image; `make smoke` passes against the built simulator
- [ ] Branch ruleset on `main` requires every ci job (checked through the API)

**Dependencies:** 1.1.3, 1.1.4

**Manual Steps:**
- 🔧 Enable GitHub Actions on the repo; enable GHCR package write permission
- 🔧 Enable branch protection on `main` requiring CI to pass

---

## Phase 2: Semantic Layer & Verification Engine

**Goal:** Build the domain-agnostic core and the deterministic judging engine — headless, no UI, no language.

**Outcome:** A full commerce flow drivable and judgeable from Python tests, plus a stub second domain proving the interface is real.

---

### Chunk 2.1: Semantic Layer

#### Sub-chunk 2.1.1: Domain Interface Definition

**Objective:** Define the plugin interface every domain implements, so commerce is never special.

**Input:** None beyond Phase 1

**Output:** A typed interface plus a conformance test suite any domain must pass

**Files:**
- `packages/core-semantic/src/domain.ts` (interface)
- `packages/core-semantic/src/state.ts` (snapshot, diff, patch, fork)
- `packages/core-semantic/src/operation.ts`
- `packages/core-semantic/src/invariant.ts`
- `packages/core-semantic/src/conformance/suite.ts`
- `packages/core-semantic/src/money.ts` (`Money` type and currency exponent table; domain-agnostic)
- `bench/rtlenv/domain_protocol.py` (Python mirror: Money helpers, canonical JSON, hash, diff, patch, subtree changes)
- `packages/core-semantic/tests/{money,state,domain}.test.ts`, `bench/tests/test_domain_protocol.py`
- `packages/core-semantic/tests/fixtures/state-parity.json` (generated by `uv run python -m rtlenv.domain_protocol --vectors`; both suites assert it)
- `tools/test_vocab_gate.sh` (negative test for `no-domain-vocabulary`, in `make gates`)

**Key Logic:**
- `Money = { minor: integer, currency: ISO-4217 code }`. A per-currency exponent table (`ILS: 2`, `USD: 2`, `KWD: 3`, `BHD: 3`, ...) is the only place decimals are known. Cross-currency arithmetic **throws**, never coerces. No floats anywhere in money paths. Rendering to a decimal string is the formatter's job (3.1.2), not the domain's.
- A domain declares: `entities` (typed records), `operations` (name, params, `precondition`, pure `apply(state, params, ctx)`, and `sample(state, rng)` returning legal params or null), `invariants` (predicates that must hold after every operation), and `seedState(rng)`. `sample` is what lets the conformance suite and 2.1.2's property test drive any domain blind. `ctx` carries the seeded Rng and an injected clock; a domain never reads wall time.
- State is one JSON-serialisable tree. No hidden state, no closures, no Dates captured at import time. Numbers are integers only (money is minor units; JS and Python format floats differently, which would break cross-language hashing). Entity collections are records keyed by id, not arrays, so diffs stay stable under insertion. `canonicalJson` (sorted keys, compact) and `hashState` (SHA-256 of it) are byte-identical in TypeScript and Python.
- `diff(before, after)` returns a structured changeset, not a string: sorted leaf-level `{path, kind, before, after}` entries; `patch(before, changeset)` reproduces `after` exactly. `execute(domain, state, op, params, ctx)` validates params, checks the precondition, applies on a frozen copy (a mutating `apply` throws), checks invariants, and returns the new state plus a trace entry with before/after hashes and the changeset.
- Conformance suite asserts: state round-trips through JSON; every operation is deterministic under a fixed seed; invariants hold after every legal operation; illegal operations reject without mutating state.
- **The interface must not mention products, carts, prices, or anything commerce-specific.**

**Test Criteria:**
- [ ] `pnpm --filter core-semantic test` passes
- [ ] A deliberately commerce-flavoured name in `domain.ts` fails a lint rule (`no-domain-vocabulary`)
- [ ] Conformance suite runs against a trivial toy domain and passes
- [ ] `diff()` on two identical states returns an empty changeset
- [ ] Python and TypeScript agree on canonical JSON, hashes, and changesets for the shared fixture
- [ ] `Money` in a 3-decimal currency (KWD) adds, scales, and refuses to mix with ILS

**Dependencies:** 1.1.4

**Manual Steps:** None

---

#### Sub-chunk 2.1.2: Commerce Domain Implementation

**Objective:** Implement commerce against the interface — the first real domain.

**Input:** Domain interface

**Output:** A headless commerce model: catalog, cart, checkout, order, returns

**Files:**
- `packages/domains/commerce/src/entities.ts`
- `packages/domains/commerce/src/operations/*.ts`
- `packages/domains/commerce/src/invariants.ts`
- `packages/domains/commerce/src/seed.ts`
- `packages/domains/commerce/tests/*.test.ts`

**Key Logic:**
- Entities (16 keyed schemas plus the cart singleton): Product (with variants: size, colour), Variant, Inventory, Cart, CartLine, DeliveryGroup, Coupon, Address, ShippingOption, DeliverySlot, PaymentMethod, SavedItem, Order, OrderLine, Shipment, ReturnRequest, Customer. Collections are records keyed by id.
- Operations (26): shopper: `search`, `viewProduct`, `addToCart`, `changeVariant`, `setQuantity`, `removeLine`, `saveForLater`, `moveToCart`, `applyCoupon`, `removeCoupon`, `applyLoyaltyPoints`, `addAddress`, `editAddress`, `setAddress`, `setShipping`, `selectDeliverySlot`, `splitDelivery`, `setPaymentMethod`, `checkout`, `cancelLine`, `cancelOrder`, `requestReturn`, `trackOrder`; system actor: `advanceClock`, `advanceShipment`, `restock`. `search` and `viewProduct` record their results in `session` so milestones can assert what the agent found without reading the screen.
- Invariants (15): cart totals consistent; inventory never negative; reserved stock equals pending order lines; coupon applies once (one per cart, uses within max, uses equal consuming orders); no cancellation after dispatch (frozen snapshot per shipment); VAT consistent; referential integrity; delivery groups partition the cart; returns bounded (per line, per return refund, order refunds never exceed what was paid); slot capacity; loyalty points non-negative; single currency across the state; lines well-formed; order status derived; counters monotonic.
- Prices are VAT-inclusive, as Israeli consumer prices are; `vat` is the VAT contained in the total, computed by integer scaling at `config.vatPercent` (18). Refunds return each line's paid share (net of discount and loyalty, rounded down) plus shipping once an order is fully cancelled.
- No language in the seed: names, sizes, colours, cities and reasons are resource keys the surface layer resolves; size systems (numeric, letters, words) vary per product for the size-sort pathology.
- Time is explicit state (`session.now`) advanced only by the system operation `advanceClock`; coupon expiry and the return window read it. The domain never touches a wall clock.
- Money uses the core `Money` type: `{ minor: integer, currency: 'ILS' }`. **No floats anywhere in money paths.** Hebrew commerce is ILS-only, but the type is currency-generic so Arabic markets (including 3-decimal KWD/BHD) are a content swap.
- `splitDelivery` and `cancelLine` exist specifically because they are where agents fail; they are not decoration.

**Test Criteria:**
- [ ] Full flow test: search → add → change size → apply coupon → checkout → partial cancel → return, asserting state at each step
- [ ] Property test: 10,000 random legal operation sequences, invariants hold after every one
- [ ] Coupon double-application rejected
- [ ] Money test covers a 3-decimal currency: a cart priced in `KWD` (`{ minor: 1500, currency: 'KWD' }` = 1.500 KWD) totals correctly with exponent 3, and adding an `ILS` line to it throws a named error
- [ ] `grep -rn "\.toFixed\|parseFloat" packages/domains/commerce/src/` returns nothing in money paths (a test also greps for `Math.round`, `/ 100` and any Hebrew or Arabic script under `src/`)
- [ ] Commerce passes the identical core conformance suite the insurance stub will run
- [ ] Every operation's `sample()` returns params its own precondition accepts, across hundreds of states

**Dependencies:** 2.1.1

**Manual Steps:** None

---

#### Sub-chunk 2.1.3: Stub Second Domain

**Objective:** Prove the interface generalises, now rather than in month 20.

**Input:** Domain interface

**Output:** A minimal insurance domain that passes the conformance suite

**Files:**
- `packages/domains/insurance-stub/src/*.ts` (`domain.ts`: entities, seed, operations, invariants in one file; `index.ts`)
- `packages/domains/insurance-stub/tests/conformance.test.ts` (the identical suite commerce runs), `tests/behaviour.test.ts`

**Key Logic:**
- Entities: Policy, Claim, Premium, Beneficiary, plus Document (what `uploadDocument` creates). Operations: `fileClaim`, `uploadDocument`, `checkStatus`, `updateBeneficiary`. Six invariants (claims within coverage, document/claim consistency, beneficiary shares 0..100 summing to at most 100, premium per policy, single currency, counters). Claims never progress past `filed`: there is no reviewer operation because the stub has nothing to prove about workflows, only about the interface.
- Deliberately thin. Its only job is to fail loudly if `core-semantic` has absorbed commerce assumptions.
- Kept in CI permanently. If a future change to the core breaks the stub, the core has leaked.

**Test Criteria:**
- [ ] Insurance stub passes the identical conformance suite commerce passes
- [ ] Zero code changes to `core-semantic` were required to add it (`git diff --stat main -- packages/core-semantic` is empty on the PR)
- [ ] CI runs both domains' conformance suites (the `test-js` job log lists both `packages/domains/*` test runs)

**Dependencies:** 2.1.1, 2.1.2

**Manual Steps:** None

---

### Chunk 2.2: Verification Engine

#### Sub-chunk 2.2.1: State-Diff Judge Core

**Objective:** Judge a rollout by comparing final state to expectation, deterministically.

**Input:** Domain state snapshots

**Output:** A judge engine returning a structured verdict

**Files:**
- `bench/rtlenv/judge/core.py`
- `bench/rtlenv/judge/matchers.py`
- `bench/rtlenv/judge/verdict.py`
- `bench/rtlenv/task/schema.py` (minimal task contract, see below)
- `bench/tests/judge/test_core.py`

**Key Logic:**
- **Defines the minimal task contract the judge consumes**, in `bench/rtlenv/task/schema.py`: `id`, `setup` (seeded state reference), `goal_matchers`, `unchanged_subtrees`. Nothing about authoring, suites or difficulty. 2.2.4 extends this contract; it never redefines these fields.
- Verdict schema: `success: bool`, `progress: float`, `side_effects: list`, `false_complete: bool`, `reward: float`, `evidence: dict`.
- Matchers are composable predicates over the state tree: `field_equals`, `collection_contains_exactly`, `count_is`, `money_equals`, `within_tolerance`, `unchanged`.
- **`unchanged` is mandatory in every task** — it names the subtrees that must not have moved. This is how side effects get caught.
- Judges never see the agent's text. They see state before, state after, and the action trace. A model cannot talk its way to reward.
- Sub-millisecond target: the judge is pure Python over dicts, no I/O.

**Test Criteria:**
- [ ] Judge returns `success` on a correct transcript
- [ ] Judge returns failure on each of ≥10 hand-built incorrect transcripts
- [ ] Judge flags a side effect when an unrelated subtree changed
- [ ] Judge refuses a task object lacking `unchanged_subtrees` with a named error
- [ ] `pytest --benchmark` shows median judge latency under 1 ms
- [ ] Judging the same transcript twice returns byte-identical verdicts

**Dependencies:** 2.1.2

**Manual Steps:** None

---

#### Sub-chunk 2.2.2: Partial Credit & Reward Shaping

**Objective:** Produce a dense reward so RL has gradient, without making partial credit gameable.

**Input:** Judge core

**Output:** A progress-rate model and reward function

**Files:**
- `bench/rtlenv/judge/progress.py`
- `bench/rtlenv/judge/reward.py`
- `bench/tests/judge/test_reward.py`

**Key Logic:**
- Progress is defined per task as an ordered list of milestone predicates. Progress rate = fraction of milestones reached, in order. Out-of-order milestones do not count.
- Reward = `w_success · success + w_progress · progress − w_side · side_effects − w_false · false_complete`, weights in task config, defaults documented.
- **False-complete penalty is non-negotiable:** an agent that declares done without satisfying the goal scores below one that fails honestly. Otherwise models learn to claim success.
- Reward is clamped to a documented range so a single task cannot dominate a batch.

**Test Criteria:**
- [ ] An agent reaching 3 of 5 milestones scores strictly between failure and success
- [ ] Out-of-order milestone completion does not inflate progress
- [ ] False-complete transcript scores below an honest-failure transcript
- [ ] Reward never exits the documented range across 10,000 random verdicts

**Dependencies:** 2.2.1

**Manual Steps:** None

---

#### Sub-chunk 2.2.3: Judge Meta-Test Harness

**Objective:** Test the judges themselves, because a silently permissive judge is the worst failure in this business.

**Input:** Judge engine

**Output:** A harness that asserts judge behaviour against curated transcripts

**Files:**
- `bench/rtlenv/metatest/harness.py`
- `bench/rtlenv/metatest/fixtures/` (transcript corpus)
- `bench/tests/metatest/test_all_judges.py`

**Key Logic:**
- Every task must ship ≥5 fixtures: one correct, one clearly wrong, and ≥3 **plausibly wrong** — the near-misses that a loose judge would accept.
- CI fails if any registered task lacks the minimum fixtures. This makes the discipline structural rather than optional.
- Mutation testing: programmatically weaken each matcher (flip a comparison, widen a tolerance) and assert the fixture suite catches it. A matcher whose weakening goes undetected is untested.

**Test Criteria:**
- [ ] Registering a task without fixtures fails CI with a clear message
- [ ] Mutation run reports ≥90% of injected weakenings caught
- [ ] Harness runs the full fixture corpus in under 30 seconds

**Dependencies:** 2.2.2

**Manual Steps:**
- 🔧 Hand-write the first 15 "plausibly wrong" transcripts yourself. These teach you the cheat surface and cannot be delegated to an agent, because the agent shares the blind spot you are testing for.

---

#### Sub-chunk 2.2.4: Task Schema & Registry

**Objective:** Define what a task is, and make tasks discoverable and validated.

**Input:** Judge engine and the minimal task contract from 2.2.1

**Output:** A task schema, registry and validator

**Files:**
- `bench/rtlenv/task/schema.py` (extend the 2.2.1 minimal contract: add fields only)
- `bench/rtlenv/task/registry.py`
- `bench/rtlenv/task/validate.py`
- `bench/tests/task/test_schema.py`

**Key Logic:**
- **Extends, never redefines.** The 2.2.1 fields (`id`, `setup`, `goal_matchers`, `unchanged_subtrees`) keep their names and meanings; this sub-chunk adds the authoring concerns below. A task valid under 2.2.1 plus the added mandatory fields is valid here.
- A task declares: `id`, `suite`, `domain`, `description_template` (slotted, per-language), `setup` (seeded state injection), `milestones`, `goal_matchers`, `unchanged_subtrees`, `cheat_surface` (documented known exploits), `fixtures`, `difficulty_target`.
- IDs are stable and namespaced: `he.commerce.checkout.coupon_then_variant_change`.
- Validator rejects a task lacking `unchanged_subtrees` or `cheat_surface`. Both are mandatory.
- Registry auto-discovers tasks under `bench/tasks/` and exposes splits (`train`, `test`, `pathology`, `calibration`).

**Test Criteria:**
- [ ] `python -m rtlenv.task.validate --all` passes
- [ ] A task missing `unchanged_subtrees` is rejected with a named error
- [ ] `python -m rtlenv.task.registry --list` shows tasks grouped by suite and split
- [ ] Task IDs are stable across runs (no ordering dependence)

**Dependencies:** 2.2.3

**Manual Steps:** None

---

## Phase 3: RTL Rendering Layer

**Goal:** Build the bidirectional-text and RTL-layout capability that is the actual company, as reusable packages rather than app code.

**Outcome:** A Hebrew storefront rendering on the commerce domain, with RTL primitives and pathology injectors extracted into their own packages.

---

### Chunk 3.1: RTL Primitives

#### Sub-chunk 3.1.1: Bidirectional Text Engine

**Objective:** Handle mixed Hebrew/Latin/numeral text correctly — and, on demand, incorrectly.

**Input:** None beyond Phase 1

**Output:** A bidi package used by every surface

**Files:**
- `packages/rtl-primitives/src/bidi/resolve.ts`
- `packages/rtl-primitives/src/bidi/segment.ts`
- `packages/rtl-primitives/src/bidi/isolate.ts`
- `packages/rtl-primitives/tests/bidi.test.ts`

**Key Logic:**
- Implement the subset of UAX #9 we need: paragraph direction resolution, isolate handling (`LRI`/`RLI`/`FSI`/`PDI`), and neutral-run resolution.
- Correct rendering of the hard cases: `"תשלח לי את ה-quote בווטסאפ"`, `"₪1,234.50"`, `"iPhone 15 Pro 256GB"` inside an RTL paragraph, phone numbers, order references like `ORD-2026-0451`.
- Every function takes a `mode: 'correct' | 'pathological'` parameter. Pathological modes are named and enumerable, not ad-hoc — this is what Phase 3.2 consumes.
- Zero runtime dependency on browser bidi behaviour. We resolve explicitly so results are testable in Node.

**Test Criteria:**
- [ ] Golden-file suite of ≥100 mixed-script strings, each with expected visual order, all passing
- [ ] Known-hard cases from the list above render correctly
- [ ] Every `pathological` mode produces output that differs from `correct` mode
- [ ] Tests run in Node without a browser

**Dependencies:** 1.1.4

**Manual Steps:**
- 🔧 Build the golden-file corpus by writing 100 realistic Hebrew e-commerce strings yourself and recording expected visual order. This is domain knowledge an agent cannot supply.

---

#### Sub-chunk 3.1.2: Numeral Systems & Money Formatting

**Objective:** Get numbers, currency and dates right in an RTL context — the single most common real-world failure.

**Input:** Bidi engine

**Output:** Locale-aware formatters with pathological variants

**Files:**
- `packages/rtl-primitives/src/numerals/format.ts`
- `packages/rtl-primitives/src/numerals/money.ts`
- `packages/rtl-primitives/src/numerals/datetime.ts`
- `packages/rtl-primitives/tests/numerals.test.ts`

**Key Logic:**
- Currency symbol placement (₪ before or after, with or without space) is a **surface parameter**, because real Israeli sites disagree.
- Thousands separators: comma, space, or none — also a parameter.
- Hebrew calendar dates and מוצ״ש handling for delivery windows.
- Pathological modes: numeral direction leak (digits rendering LTR inside an RTL run producing `50.1,234₪`), symbol on the wrong side, separator inconsistency between list and detail views.
- Formatting is pure and seeded — the same config always produces the same string.

**Test Criteria:**
- [ ] `₪1,234.50` formats correctly under all parameter combinations
- [ ] Direction-leak pathological mode produces a visually wrong but deterministic string
- [ ] Hebrew calendar date conversion matches a reference table for 50 known dates
- [ ] No floats in money formatting (`Money` in, string out; decimal places come from the currency exponent table, verified for ILS and KWD)

**Dependencies:** 3.1.1

**Manual Steps:** None

---

#### Sub-chunk 3.1.3: RTL Layout Primitives

**Objective:** Mirrored layout, logical properties, and direction-aware components.

**Input:** Bidi engine

**Output:** A layout package the surface generator composes

**Files:**
- `packages/rtl-primitives/src/layout/direction.tsx`
- `packages/rtl-primitives/src/layout/mirror.ts`
- `packages/rtl-primitives/src/layout/components/*.tsx`
- `packages/rtl-primitives/tests/layout.test.tsx`

**Key Logic:**
- Use CSS logical properties throughout (`margin-inline-start`, not `margin-left`). A lint rule fails on physical properties in surface code.
- Direction-aware components: back/forward affordances, progress steppers, carousels, sliders, breadcrumbs — all of which mirror, and all of which real sites get wrong.
- Icon mirroring policy: directional icons mirror, semantic icons do not (a play button never mirrors). Encoded as a typed registry, not per-component judgement.
- Pathological modes: unmirrored chevrons, a progress stepper running LTR in an RTL page, a slider whose min and max are swapped.

**Test Criteria:**
- [ ] `grep -rn "margin-left\|padding-right\|text-align: *left" packages/ sim/src/` returns nothing outside explicitly-waived files
- [ ] Snapshot tests for each component in both correct and pathological modes
- [ ] Icon mirror registry has a test asserting the play button never mirrors
- [ ] Rendering the same component with the same seed produces an identical DOM

**Dependencies:** 3.1.1

**Manual Steps:** None

---

#### Sub-chunk 3.1.4: Hebrew Typography & Font Pipeline

**Objective:** Ship correct Hebrew type with redistributable fonts.

**Input:** None

**Output:** A font subsetting and loading pipeline, OFL-clean

**Files:**
- `packages/rtl-primitives/src/type/fonts.ts`
- `packages/rtl-primitives/src/type/scale.ts`
- `content/fonts/` (subsetted OFL fonts + LICENSE files)
- `tools/fonts/subset.py`

**Key Logic:**
- Fonts: Noto Sans Hebrew, Heebo, Rubik. **OFL only**, each with its licence file committed alongside and registered in the provenance manifest.
- Subset to the glyph coverage we actually use, to keep instance weight down (400 MB RAM budget per instance).
- Hebrew line-height and letter-spacing differ from Latin defaults; encode a Hebrew-specific type scale rather than inheriting Tailwind's.
- Font choice is a surface parameter.

**Test Criteria:**
- [ ] Every font in `content/fonts/` has a sibling `LICENSE` and a provenance entry
- [ ] Licence gate passes with fonts present
- [ ] Subsetted fonts render the full test corpus without tofu (`.notdef`) glyphs
- [ ] Total font payload under 400 KB

**Dependencies:** 1.1.3

**Manual Steps:**
- 🔧 Download fonts from Google Fonts or the foundry, verify each licence is OFL, and commit the licence text

---

### Chunk 3.2: Pathology Library

#### Sub-chunk 3.2.1: Pathology Injector Framework

**Objective:** Make real-world RTL failures a composable, seeded, catalogued capability.

**Input:** RTL primitives

**Output:** A pathology package with a registry of named, parameterised defects

**Files:**
- `packages/pathology/src/registry.ts`
- `packages/pathology/src/injectors/*.ts`
- `packages/pathology/src/catalog.json`
- `packages/pathology/tests/injectors.test.ts`

**Key Logic:**
- Each injector declares: `id`, `description`, `severity`, `observed_in` (survey capture reference; **nullable at registration** because the survey is 5.1.2, populated as captures arrive), `applies_to` (component types), `detectable_by` (how a correct agent would notice).
- `observed_in: null` is legal here and only here. A CI check added in 6.1.3 fails the build if any injector referenced by a pathology task still has `observed_in: null`.
- Initial set, all observed in real Israeli e-commerce:
  - `hebrew-truncation` — name field silently truncates Hebrew at N chars mid-word
  - `numeral-direction-leak` — price renders with digits in LTR order
  - `latin-in-rtl-input` — coupon field rejects or reorders Latin codes
  - `unmirrored-chevron` — navigation arrow points the wrong way
  - `size-label-sort` — Hebrew size labels sort lexically, not by size
  - `stale-cart` — cart state diverges from server after a variant change
  - `lying-confirmation` — success screen shown while the order sits pending
  - `mixed-separator` — thousands separator differs between list and detail
  - `rtl-form-tab-order` — tab order runs LTR through an RTL form
  - `direction-switch-midflow` — checkout step reverts to LTR
- Injectors are pure functions of `(component, config, rng)`. Same seed, same defect.
- **A pathology is only useful if a correct agent can detect it.** `detectable_by` is mandatory and reviewed.

**Test Criteria:**
- [ ] Each injector has a test asserting the defect appears and is deterministic under a fixed seed
- [ ] `catalog.json` validates against a schema; every entry has `detectable_by`; `observed_in` may be `null`
- [ ] Applying zero injectors produces output byte-identical to the un-injected component
- [ ] Applying the same injector twice with the same seed is idempotent

**Dependencies:** 3.1.3

**Manual Steps:** None

---

#### Sub-chunk 3.2.2: Pathology-Aware Judging

**Objective:** Let tasks assert that an agent correctly handled — or correctly refused — a pathological surface.

**Input:** Pathology registry, judge engine

**Output:** Judge matchers that reason about injected defects

**Files:**
- `bench/rtlenv/judge/pathology.py`
- `bench/rtlenv/task/pathology_task.py`
- `bench/tests/judge/test_pathology.py`

**Key Logic:**
- Three correct behaviours under a defect, each judgeable: **avoid** (complete the goal via a path that dodges the defect), **detect and report** (surface the problem rather than proceeding), **recover** (proceed and correct the resulting state).
- The task declares which behaviours count. A task where any of the three is acceptable is scored as a disjunction.
- Critically: an agent that blunders through and *happens* to produce correct final state under `hebrew-truncation` must **not** score full marks if the truncation corrupted stored data. `unchanged_subtrees` catches this.

**Test Criteria:**
- [ ] Avoid, detect and recover transcripts each score as configured
- [ ] A transcript that produces correct visible state but corrupt stored state scores as failure
- [ ] Pathology tasks run under the standard registry and metrics

**Dependencies:** 3.2.1, 2.2.4

**Manual Steps:** None

---

### Chunk 3.3: First Storefront

#### Sub-chunk 3.3.1: Storefront App Shell

**Objective:** One synthetic Hebrew storefront rendering the commerce domain inside the simulator.

**Input:** Commerce domain, RTL primitives, forked sim

**Output:** A working app in `sim/apps/`

**Files:**
- `sim/apps/Storefront/manifest.ts`
- `sim/apps/Storefront/StorefrontApp.tsx`
- `sim/apps/Storefront/navigation.declaration.ts`
- `sim/apps/Storefront/pages/*.tsx`
- `sim/apps/Storefront/res/strings.he.json`

**Key Logic:**
- The app is a **view over the commerce domain**. It holds no business logic. Every state change goes through a domain operation.
- Navigation is a declarative FSM (routes, transitions, actions), matching the forked platform's contract, so it is statically analysable and BFS-traversable.
- Screens: home, category, search results, product detail, cart, checkout (address → shipping → payment → confirm), order list, order detail, return request.
- All strings from `res/strings.he.json`. No hardcoded Hebrew in components — this is what makes Arabic a content swap in Phase 12.
- **Delete the two upstream reference apps retained in 1.1.2.** Their job (showing the platform's app contract) is done once the Storefront exists. Record the deletion in `UPSTREAM.md`.

**Test Criteria:**
- [ ] The two upstream reference apps retained in 1.1.2 are gone: `ls sim/apps/` lists only our apps, and `UPSTREAM.md` records the deletion commit
- [ ] `pnpm --filter sim dev` serves the storefront; you can complete a purchase by hand
- [ ] `grep -P '[\x{0590}-\x{05FF}]' sim/apps/Storefront/**/*.tsx` returns nothing (no inline Hebrew)
- [ ] Every UI mutation corresponds to a domain operation in the state log
- [ ] Navigation FSM is complete: every declared route reachable by BFS from home

**Dependencies:** 2.1.2, 3.1.3, 3.1.4

**Manual Steps:** None

---

#### Sub-chunk 3.3.2: State Control API Binding

**Objective:** Expose snapshot, patch, fork and restore so the bench layer can drive and judge the app.

**Input:** Storefront app

**Output:** A control surface the Python bench layer calls

**Files:**
- `sim/apps/Storefront/state/bridge.ts`
- `bench/rtlenv/env/control.py`
- `bench/tests/env/test_control.py`

**Key Logic:**
- Bind the commerce domain state into the simulator's structured-JSON control API so `__SIM__` snapshot/patch/restore work unmodified.
- `fork()` must produce an independent state tree — no shared references, or parallel rollouts will contaminate each other. This is the single most dangerous bug class in the whole system.
- Round-trip guarantee: `restore(snapshot(s)) === s` for every reachable state.

**Test Criteria:**
- [ ] Snapshot → mutate → restore returns the exact original state, deep-equal
- [ ] Fork 50 instances, mutate each differently, assert zero cross-contamination
- [ ] Python `control.py` drives a full purchase flow headlessly
- [ ] Snapshot of a 500-product catalog completes in under 50 ms

**Dependencies:** 3.3.1, 2.1.2

**Manual Steps:** None

---

## Phase 4: Content Pipeline & Provenance

**Goal:** Generate original Hebrew catalogs, copy and imagery at scale, with every artifact traceable.

**Outcome:** A reproducible content pipeline whose output passes the licence firewall, and a provenance system that answers "where did this come from" for every byte we ship.

---

### Chunk 4.1: Provenance System

#### Sub-chunk 4.1.1: Provenance Manifest & Audit Tool

**Objective:** Make every shipped asset traceable to how it was produced.

**Input:** None beyond Phase 1

**Output:** A manifest format and an audit CLI wired into CI

**Files:**
- `tools/provenance/schema.json` (extend the 1.1.3 v1 schema: add fields only)
- `tools/provenance/audit.py`
- `tools/provenance/record.py`
- `content/MANIFEST.json` (extend entries; file exists since 1.1.2)

**Key Logic:**
- **Extends, never redefines.** The v1 fields from 1.1.3 (`schema_version`, `path`, `sha256`, `licence`) keep their names and meanings. This sub-chunk ADDS the fields below; a v1 manifest must still validate against the extended schema.
- Every file under `content/` has an entry: `path`, `sha256`, `origin` (`generated-image` | `generated-text` | `licensed-font` | `authored` | `procedural`), `generator` (model name + version), `prompt_sha256`, `seed`, `licence`, `created_at`, `reviewed_by`.
- `audit.py` walks `content/`, recomputes hashes, and fails on: missing entry, hash mismatch, orphan entry, licence not in the allowlist, or `origin: licensed-*` without a licence file.
- Manifest is append-mostly and diffable; a content change shows as a hash change in review.
- **An asset with no provenance entry cannot enter the build.** This is the mechanism that keeps NC and brand-derived content out permanently, not vigilance.

**Test Criteria:**
- [ ] `make provenance` passes on a clean tree
- [ ] Manually edit a PNG byte → audit fails with a hash mismatch naming the file
- [ ] Add a file to `content/` without an entry → audit fails
- [ ] Delete a manifest entry whose file still exists → audit fails
- [ ] The 1.1.3 minimal manifest (`{"schema_version": 1, "assets": []}`) still validates against the extended schema

**Dependencies:** 1.1.3

**Manual Steps:** None

---

#### Sub-chunk 4.1.2: Trademark & Brand Hygiene Check

**Objective:** Guarantee generated content never resembles a real brand.

**Input:** Provenance system, brandlist

**Output:** An automated brand check over text and images

**Files:**
- `tools/provenance/brand_check.py`
- `tools/provenance/brandlist.he.txt`
- `tools/provenance/brandlist.intl.txt`

**Key Logic:**
- Text: exact and fuzzy match (normalised Hebrew, no niqqud, transliteration variants) against both brand lists. Levenshtein threshold tuned to catch "שופרסל" vs "שופרסאל".
- Images: perceptual hash comparison against a small corpus of known logos you assemble; plus a rule that generated logos must come from the abstract-mark prompt template, never from a text prompt naming a real company.
- Generated store names come from a procedural generator (Hebrew word pairs) with a blocklist check, not from a model asked to "invent a store name" — models reach for real ones.

**Test Criteria:**
- [ ] Inject "שופרסל" into a product description → check fails
- [ ] Inject a near-miss spelling → check fails
- [ ] 1,000 procedurally generated store names produce zero blocklist hits
- [ ] Brand check runs in CI and on `make provenance`

**Dependencies:** 4.1.1

**Manual Steps:**
- 🔧 Assemble a reference corpus of ~100 real Israeli retail logos for perceptual-hash comparison. Keep it outside `content/` in a gitignored `refs/` directory — it is a test fixture, never shipped.

---

### Chunk 4.2: Content Generation

#### Sub-chunk 4.2.1: Synthetic Catalog Generator

**Objective:** Produce realistic Hebrew product catalogs procedurally and deterministically.

**Input:** Seed, category configuration

**Output:** Catalogs of arbitrary size, fully reproducible

**Files:**
- `tools/content/catalog/generate.py`
- `tools/content/catalog/taxonomy.yaml`
- `tools/content/catalog/hebrew_lexicon.json`
- `content/catalogs/`

**Key Logic:**
- Taxonomy covers categories where Israeli e-commerce is dense: fashion, electronics, home, beauty, groceries, toys. Each declares its variant axes (size systems differ: EU shoe sizes, Israeli clothing sizes, אחיד).
- Product names composed procedurally from a Hebrew lexicon (material + type + qualifier), not model-generated, so they are reproducible and brand-free.
- Realistic price distributions per category, in agorot, with the psychological price points Israeli retail actually uses (₪99.90, ₪199).
- **Size labels are deliberately heterogeneous** — some numeric, some S/M/L, some Hebrew (קטן/בינוני/גדול) — because the `size-label-sort` pathology depends on it.
- Inventory, ratings and review counts generated with realistic skew, not uniform.

**Test Criteria:**
- [ ] Same seed → byte-identical catalog JSON
- [ ] 10,000-product catalog generates in under 10 seconds
- [ ] Brand check passes on every generated name and description
- [ ] Price distribution matches the configured shape within tolerance
- [ ] Every product validates against the commerce domain's Product entity schema

**Dependencies:** 4.1.2, 2.1.2

**Manual Steps:**
- 🔧 Build the initial Hebrew lexicon (~500 terms across the six categories). Use real category browsing for vocabulary, but write the terms yourself.

---

#### Sub-chunk 4.2.2: Hebrew Copy Generation

**Objective:** Generate UI strings, product descriptions and policy text in natural Hebrew.

**Input:** Catalog, string keys

**Output:** Provenance-tracked Hebrew copy

**Files:**
- `tools/content/copy/generate.py`
- `tools/content/copy/prompts/*.txt`
- `tools/content/copy/review_queue.py`
- `content/copy/he/`

**Key Logic:**
- Claude API with temperature 0 and a recorded prompt hash, so regeneration is reproducible.
- Register matters and is a surface parameter: formal (אתם) vs casual (אתה), and Israeli e-commerce genuinely varies.
- Every generated string passes through the brand check before entering the manifest.
- **Human review queue:** generated copy lands in `review_queue` until you mark it reviewed. `reviewed_by` populates the manifest. Unreviewed copy cannot ship. This is where an LLM's plausible-but-wrong Hebrew gets caught.
- Terminology variants are generated as sets, not singletons — the generator later samples which term a given store uses for "checkout" (לתשלום / לקופה / להזמנה).

**Test Criteria:**
- [ ] Same prompt + model + seed → identical output
- [ ] Unreviewed copy fails the provenance audit
- [ ] Brand check passes on the full corpus
- [ ] Terminology sets contain ≥3 variants for each of the 20 key UI actions

**Dependencies:** 4.2.1, 4.1.2

**Manual Steps:**
- 🔧 Review the full first copy corpus yourself. Native-speaker judgement on register and idiom is the product; do not delegate this to the model that wrote it.
- 🔧 Add `ANTHROPIC_API_KEY` to `.env.local`

---

#### Sub-chunk 4.2.3: Image Asset Pipeline

**Objective:** Generate original product imagery locally, at zero marginal cost and with clean provenance.

**Input:** Catalog entries

**Output:** Product images, category banners, abstract store marks

**Files:**
- `tools/content/images/generate.py`
- `tools/content/images/comfy_workflows/*.json`
- `tools/content/images/prompt_templates.yaml`
- `content/images/`

**Key Logic:**
- ComfyUI on the RTX 5070, SDXL or Flux-schnell. Record model file hash, workflow hash, prompt, seed, sampler and steps in the manifest.
- Prompt templates are abstract and product-category-driven. **Never name a brand, never request a logo resembling anything.** Store marks come from a geometric-abstract template only.
- Output budget: aggressive WebP compression, target under 40 KB per product image, to protect the per-instance memory budget.
- Batch generation is resumable — it will run for hours and must survive interruption.

**Test Criteria:**
- [ ] Same seed + workflow → identical image bytes
- [ ] 500 images generate without manual intervention, resumable after a kill
- [ ] Every image has a complete manifest entry including model hash
- [ ] Perceptual-hash brand check passes on all generated marks
- [ ] Mean image size under 40 KB

**Dependencies:** 4.1.2, 4.2.1

**Manual Steps:**
- 🔧 Install ComfyUI locally, download SDXL or Flux-schnell weights, verify the model licence permits commercial use and record it in the manifest
- 🔧 Spot-review 50 generated images for anything that inadvertently resembles a real product or logo

---

## Phase 5: Surface Generator

**Goal:** Turn one storefront into unlimited distinct storefronts, sampled from a parameter space grounded in real observation.

**Outcome:** A generator with a surveyed parameter space and a composition engine. The proof that the variation is real is Gate 1 (6.3.1), which runs after the task set exists.

---

### Chunk 5.1: Field Survey

#### Sub-chunk 5.1.1: Survey Instrument & Data Schema

**Objective:** Define exactly what to record about each real store, before recording any.

**Input:** None

**Output:** A structured survey schema and capture tooling

**Files:**
- `tools/survey/schema.json`
- `tools/survey/capture.py`
- `tools/survey/report.py`
- `refs/survey/` (gitignored raw captures)
- `content/distributions/` (derived, committed)

**Key Logic:**
- Record per store: navigation depth to checkout, terminology used for ~20 key actions, checkout step count and order, address-field composition and order, currency format, thousands separator, date format, confirmation style, error presentation, size-label system, coupon field placement and behaviour, session timeout if observable, and **every RTL defect observed** with a screenshot reference.
- **Raw captures (screenshots, HTML) stay in gitignored `refs/` and never enter the repo.** Only the derived distribution — frequency counts — is committed. This keeps third-party content out of the shipped artifact entirely.
- `report.py` turns raw captures into the parameter distribution table that feeds the generator.

**Test Criteria:**
- [ ] Schema validates a hand-filled example capture
- [ ] `report.py` produces frequency tables from ≥5 captures
- [ ] `refs/` is gitignored and CI fails if any file under it is committed
- [ ] Derived distributions contain no store names, URLs or images

**Dependencies:** 1.1.1

**Manual Steps:**
- 🔧 Nothing yet — this sub-chunk builds the instrument, 5.1.2 uses it

---

#### Sub-chunk 5.1.2: Execute the Survey

**Objective:** Build the empirical parameter distribution that is the actual moat.

**Input:** Survey instrument

**Output:** 100+ surveyed Israeli stores, reduced to committed distributions

**Files:**
- `refs/survey/*.json` (gitignored)
- `content/distributions/he-commerce.json` (committed)
- `docs/survey-methodology.md`

**Key Logic:**
- Sample deliberately across strata, not conveniently: large retail chains, mid-size independents, Shopify/WooCommerce templates, marketplace sellers, and mobile-app-first stores. A convenience sample of big chains will underestimate variance and your generator will be too clean.
- Record defects as you encounter them; every pathology injector's `observed_in` field must eventually point at a real capture.
- Target ≥100 stores. Below 60 the distribution is noise.

**Test Criteria:**
- [ ] ≥100 captures validate against the schema
- [ ] Each of the ≥8 surface parameters shows ≥3 observed values with frequencies
- [ ] ≥10 distinct RTL defects recorded with screenshot references
- [ ] Methodology document explains the sampling strata

**Dependencies:** 5.1.1

**Manual Steps:**
- 🔧 **This is the moat and it cannot be delegated.** Work through it in sittings of 10–15 stores. For each: browse as a real customer would, add to cart, reach checkout without paying, and record every field in the schema.
- 🔧 Use a fresh browser profile per session so personalisation does not skew what you see.
- 🔧 Do not scrape. Manual browsing only — it avoids ToS problems and you will notice defects a scraper cannot.
- 🔧 When you hit a defect, screenshot it immediately and note what a correct agent should have done. That note becomes a pathology task later.

---

### Chunk 5.2: Generator

#### Sub-chunk 5.2.1: Parameter Space Definition

**Objective:** Encode the surveyed distribution as a sampleable, typed parameter space.

**Input:** Survey distributions

**Output:** A parameter schema with observed frequencies

**Files:**
- `packages/surface-gen/src/params/schema.ts`
- `packages/surface-gen/src/params/space.ts`
- `packages/surface-gen/src/params/sample.ts`
- `packages/surface-gen/tests/params.test.ts`

**Key Logic:**
- Parameters start with (expand as the survey warrants): `nav_depth`, `action_terminology`, `checkout_steps`, `checkout_order`, `address_fields`, `currency_format`, `thousands_separator`, `date_format`, `confirm_style`, `error_style`, `size_system`, `coupon_placement`, `font_family`, `register`, `density`, `viewport`.
- Each parameter carries its observed frequency distribution. Sampling is weighted by reality, not uniform — a generator that samples uniformly produces stores that do not exist.
- Support constrained sampling: hold parameters fixed for ablation, or force a specific combination for a reproducible reference build.
- **Form factor is a parameter here** (`viewport`), not a separate product. This is what keeps the system from being mobile-only.

**Test Criteria:**
- [ ] Sampling 10,000 surfaces reproduces observed frequencies within tolerance
- [ ] Same seed → identical parameter draw
- [ ] Constrained sampling honours fixed parameters
- [ ] Every parameter traces to a survey distribution entry; a parameter without one fails validation

**Dependencies:** 5.1.2

**Manual Steps:** None

---

#### Sub-chunk 5.2.2: Surface Composition Engine

**Objective:** Render a storefront from a sampled parameter set.

**Input:** Parameter sample, commerce domain, RTL primitives, content

**Output:** A distinct, working storefront per seed

**Files:**
- `packages/surface-gen/src/compose.ts`
- `packages/surface-gen/src/theme.ts`
- `packages/surface-gen/src/nav.ts`
- `sim/apps/Storefront/generated/`

**Key Logic:**
- Composition is pure: `(params, content, seed) → storefront config`. The app reads config; it holds no variation logic itself.
- Navigation FSM is generated, not hand-written, so `nav_depth` and `checkout_order` genuinely change the reachable path — not merely the styling.
- Theme (palette, radius, density, font) derives from parameters with constraints that keep output plausible: contrast ratios stay accessible, type scale stays readable. An implausible store teaches the model nothing.
- Generated surfaces are cached by seed so a rollout batch does not recompose 256 times.

**Test Criteria:**
- [ ] Same seed → byte-identical storefront config
- [ ] 20 random seeds produce 20 visually distinct storefronts (pixel-diff over a reference screenshot exceeds threshold for every pair)
- [ ] Every generated storefront completes a purchase flow end-to-end under the automated smoke test
- [ ] Generated navigation FSM is fully reachable by BFS for every seed in a 100-seed sample

**Dependencies:** 5.2.1, 3.3.1, 4.2.3

**Manual Steps:** None

---

## Phase 6: Task Authoring System

**Goal:** Make task creation a repeatable process a non-engineer author can execute, and establish the red-team discipline that keeps judges honest.

**Outcome:** A calibrated task set with an adversarial pathology component, tooling that lets a future Arabic author contribute without you reviewing every line, and Gate 1 passed: randomisation measurably degrades agent performance.

---

### Chunk 6.1: Authoring

#### Sub-chunk 6.1.1: Task Authoring DSL & CLI

**Objective:** Let an author write a task without writing a judge from scratch.

**Input:** Task schema, judge matchers

**Output:** A declarative task format and authoring CLI

**Files:**
- `bench/rtlenv/authoring/dsl.py`
- `bench/rtlenv/authoring/cli.py`
- `bench/rtlenv/authoring/templates/`
- `docs/authoring-guide.md`

**Key Logic:**
- Tasks are declared in YAML with Python escape hatches for complex matchers. YAML is what makes this delegable.
- CLI commands: `task new`, `task preview` (renders the setup state and target in a browser), `task test` (runs the fixture suite), `task lint` (schema, mandatory fields, ID convention), `task calibrate` (runs a model against it).
- `task new` scaffolds fixtures and forces the author to fill the `cheat_surface` field before the task will lint.
- Preview is critical: an author must see the state the task produces before writing the goal.

**Test Criteria:**
- [ ] `task new he.commerce.cart.change_variant` scaffolds a complete skeleton
- [ ] `task lint` rejects a task missing `cheat_surface` or `unchanged_subtrees`
- [ ] `task preview` opens a browser at the correct seeded state
- [ ] A YAML-only task (no Python) runs and judges correctly

**Dependencies:** 2.2.4, 5.2.2

**Manual Steps:** None

---

#### Sub-chunk 6.1.2: Core Task Set

**Objective:** Author the base commerce task set.

**Input:** Authoring CLI

**Output:** 25–30 parameterised task templates

**Files:**
- `bench/tasks/he/commerce/**/*.yaml`
- `bench/tasks/he/commerce/**/fixtures/`

**Key Logic:**
- Coverage across difficulty levels L1–L4, mirroring the platform's existing taxonomy: L1 single-screen, L2 single-app multi-step, L3 multi-step with state dependency, L4 long-horizon with cross-screen state and ambiguity.
- Required task families: constrained search, variant change before checkout, coupon application and conflict, split delivery, partial cancellation, return within policy, address edit mid-checkout, quantity change with inventory limit, order lookup and status, wishlist-to-cart.
- Every task declares its cheat surface. Writing that field is the actual work.
- Templates are slotted so each yields many instances under different seeds.

**Test Criteria:**
- [ ] All tasks pass `task lint` and `task test`
- [ ] Each task has ≥5 fixtures including ≥3 plausibly-wrong
- [ ] Mutation testing catches ≥90% of injected matcher weakenings across the set
- [ ] Difficulty distribution spans L1–L4 with no level empty

**Dependencies:** 6.1.1

**Manual Steps:**
- 🔧 Write the `cheat_surface` field for every task yourself. This is the highest-value manual work in the entire plan and is exactly what a buyer is paying for.

---

#### Sub-chunk 6.1.3: Pathology Task Set

**Objective:** Author the adversarial tasks that constitute the differentiator.

**Input:** Pathology registry, survey defect observations

**Output:** 40–60 pathology tasks traced to real observations

**Files:**
- `bench/tasks/he/pathology/**/*.yaml`
- `docs/pathology-catalog.md`
- `tools/provenance/check_observed_in.py` (CI: every injector referenced by a pathology task has a non-null `observed_in`)
- `.github/workflows/ci.yml` (wire the check into the `licence` job)

**Key Logic:**
- **Every pathology task must cite a survey capture.** A task with no `observed_in` reference is invention, and invention is what a competitor can also do.
- Each task specifies which of avoid / detect / recover count as success.
- Include the cases where correct visible state masks corrupt stored state — the `unchanged_subtrees` assertions carry the weight here.
- Document each in the public catalog with the defect described but **the exact detection heuristic withheld** — the catalog is a sales asset, not a spoiler.

**Test Criteria:**
- [ ] Every pathology task references a real survey capture ID
- [ ] `python tools/provenance/check_observed_in.py` passes; setting one referenced injector's `observed_in` to `null` makes it fail naming the injector and the task
- [ ] Every registered injector has ≥2 tasks exercising it
- [ ] Fixture suites include a transcript that produces correct visible state with corrupt stored state, judged as failure
- [ ] Public catalog builds and contains no detection heuristics

**Dependencies:** 6.1.2, 3.2.2, 5.1.2

**Manual Steps:**
- 🔧 Author these yourself, working from your survey screenshots. This is the knowledge that does not transfer from documentation.

---

### Chunk 6.2: Quality Discipline

#### Sub-chunk 6.2.1: Reward-Hacking Red Team Harness

**Objective:** Systematically cheat our own rubrics before a buyer does.

**Input:** Task set, judge engine

**Output:** A standing adversarial process with a tracked findings log

**Files:**
- `bench/redteam/harness.py`
- `bench/redteam/strategies/*.py`
- `bench/redteam/findings.md`
- `.github/workflows/redteam.yml`

**Key Logic:**
- Automated strategies: brute-force random action sequences, goal-state injection via the control API (must be blocked), declaring completion immediately, repeating the last successful trajectory, exploiting float tolerance, exploiting matcher ordering, and using the AnswerSheet form to assert success without acting.
- Model-driven strategy: prompt a frontier model explicitly to maximise reward without accomplishing the task, and log what it finds. This is the single highest-yield check.
- Every finding is logged with the task, the exploit, and the fix. Findings are never deleted — the log is a vendor-review artifact.
- Runs nightly in CI against the full task set.

**Test Criteria:**
- [ ] Harness runs all strategies against all tasks
- [ ] Any successful exploit fails the nightly build and names the task
- [ ] Findings log has an entry for every historical exploit with its resolution
- [ ] A deliberately weakened matcher is caught within one nightly run

**Dependencies:** 6.1.2

**Manual Steps:**
- 🔧 Run the model-driven strategy manually first, with an adversarial prompt you write. Read every transcript. You will find exploits the automated strategies miss, and you will learn what to automate.

---

#### Sub-chunk 6.2.2: Difficulty Calibration Pipeline

**Objective:** Keep the task set in the useful difficulty band as models improve.

**Input:** Task set, model APIs

**Output:** A repeatable calibration run and a drift alarm

**Files:**
- `bench/calibration/run.py`
- `bench/calibration/report.py`
- `docs/calibration/` (historical reports)

**Key Logic:**
- Target band: 20–60% success for the current frontier. Above 80% there is no training signal; below 5% there is no gradient for GRPO, which learns by comparing attempts at the same task.
- Calibration runs per task, not just per suite — a suite average hides a saturated task.
- Every report is versioned with the model versions tested, since "frontier" moves.
- Drift alarm: when a re-run shows a task exiting the band, it is flagged for revision or deprecation.

**Test Criteria:**
- [ ] Calibration produces per-task success rates with confidence intervals
- [ ] Tasks outside the band are flagged in the report
- [ ] Re-running with identical seeds and model versions reproduces results
- [ ] Historical reports are diffable to show drift over time

**Dependencies:** 6.1.2, 6.2.1

**Manual Steps:**
- 🔧 Budget roughly $20–50 per full calibration run. Run at minimum: after the core task set lands, after pathology lands, and before any release.

---

#### Sub-chunk 6.2.3: Author Onboarding & QA System

**Objective:** Make task quality enforced by tooling rather than by your attention. **Built now, used in Phase 12.**

**Input:** Authoring CLI, red team, calibration

**Output:** An onboarding path and automated author QA gate

**Files:**
- `docs/author-onboarding.md`
- `bench/rtlenv/authoring/qa_gate.py`
- `.github/workflows/author-pr.yml`
- `bench/rtlenv/authoring/exercises/`

**Key Logic:**
- Onboarding is three graded exercises with known-good solutions: author an L1 task, author an L2 task with a documented cheat surface, and find the planted exploit in a deliberately weak judge. An author who cannot do the third should not be authoring pathology.
- QA gate runs automatically on an author's PR: lint, fixtures present, mutation coverage, red-team clean, calibration in band. **Nothing merges without passing.**
- Author PRs cannot modify `packages/` or `bench/rtlenv/` — only `bench/tasks/`. Enforced by CODEOWNERS.

**Test Criteria:**
- [ ] A deliberately weak task PR is rejected by the gate with a specific reason
- [ ] A good task PR passes without your intervention
- [ ] An author PR touching `packages/` is blocked
- [ ] The three onboarding exercises have reference solutions and an automated grader

**Dependencies:** 6.2.2

**Manual Steps:** None

---

### Chunk 6.3: Gate 1 — Randomisation Validation

#### Sub-chunk 6.3.1: Randomisation Validation Experiment

**Objective:** Prove the variation is real and not cosmetic. **This is a phase gate.**

**Input:** Surface generator, task set, frontier model API

**Output:** A measured drop in agent success under randomisation

**Files:**
- `bench/experiments/randomisation/run.py`
- `bench/experiments/randomisation/analyse.py`
- `docs/experiments/randomisation-v1.md`

**Key Logic:**
- Three arms: (A) fixed reference storefront, (B) randomised surfaces, (C) randomised surfaces with pathology injectors enabled.
- Same tasks, same models, same seeds for task instantiation — only surface varies.
- Report success rate with confidence intervals across ≥3 seeds per arm.
- **Gate: success must drop materially from A to B.** If it does not, the parameter space is cosmetic. Return to 5.1.2 and survey harder — do not proceed.
- Expected shape, based on published multilingual GUI results: a meaningful A→B drop, and a further drop B→C. Record actual numbers regardless.

**Test Criteria:**
- [ ] Experiment runs end to end and produces a report
- [ ] A→B drop is statistically distinguishable from zero
- [ ] Re-running with the same seeds reproduces the numbers
- [ ] Report names which parameters contributed most to the drop (ablation)

**Dependencies:** 5.2.2, 6.2.3 (needs the calibrated task set; runs after all of Chunk 6.2). Formerly numbered 5.2.3.

**Manual Steps:**
- 🔧 Add frontier model API keys. Budget roughly $30–80 per full experiment run; cap concurrency to avoid a surprise bill.

---

## Phase 7: Evaluation & Training Harness

**Goal:** Run rollouts at scale, produce metrics buyers recognise, and measure transfer.

**Outcome:** A repeatable transfer experiment and a report that functions as the primary sales artifact.

---

### Chunk 7.1: Rollout Infrastructure

#### Sub-chunk 7.1.1: Agent Adapters

**Objective:** Run any model against our environment without per-model glue.

**Input:** Environment control API

**Output:** Adapters for the model families buyers use

**Files:**
- `bench/rtlenv/agent/base.py`
- `bench/rtlenv/agent/generic.py`
- `bench/rtlenv/agent/anthropic.py`
- `bench/rtlenv/agent/openai.py`
- `bench/rtlenv/agent/openai_compatible.py`
- `bench/rtlenv/agent/human.py`

**Key Logic:**
- Action space mirrors the platform's existing abstraction: tap, type, swipe, back, home, wait, drag, complete — plus a structured-answer action.
- `openai_compatible` covers vLLM and most self-hosted serving, which is how a lab will run a checkpoint against your environment.
- `human` adapter is for debugging judges by hand and is genuinely necessary.
- New adapters must be writable in roughly 100 lines; if an adapter needs more, the base class is wrong.

**Test Criteria:**
- [ ] Each adapter completes a trivial L1 task
- [ ] `human` adapter lets you drive the storefront manually and produces a judgeable transcript
- [ ] A new adapter can be added without touching the runner
- [ ] Adapter output schema is identical across adapters

**Dependencies:** 3.3.2, 2.2.4

**Manual Steps:**
- 🔧 Add API keys for the model providers you will calibrate against

---

#### Sub-chunk 7.1.2: Parallel Rollout Runner

**Objective:** Run hundreds of rollouts concurrently without cross-contamination.

**Input:** Adapters, environment control

**Output:** A runner meeting the per-instance performance budget

**Files:**
- `bench/rtlenv/runner/orchestrator.py`
- `bench/rtlenv/runner/pool.py`
- `bench/rtlenv/runner/isolation.py`
- `scripts/server/start_gateway.sh`

**Key Logic:**
- Process × browser × page isolation levels, matching the platform's model. Default to page isolation for throughput, process for debugging.
- **Performance budget, enforced by test: ≤400 MB RAM and ≤3 s cold start per instance, ≥96 parallel instances on one machine.** A buyer evaluates infrastructure cost, and a heavyweight environment gets rejected regardless of content quality.
- nginx gateway for runs above 8 parallel; `npm run preview` is single-process and will silently bottleneck.
- Rollout results stream to disk incrementally so a killed run is not lost.

**Test Criteria:**
- [ ] 96 parallel instances run with zero state cross-contamination (assert via a canary field unique per instance)
- [ ] Per-instance RAM measured under 400 MB
- [ ] Cold start measured under 3 s
- [ ] Killing the runner mid-batch leaves a resumable, valid partial result

**Dependencies:** 7.1.1

**Manual Steps:**
- 🔧 Install nginx locally for the gateway. On Linux, raise `fs.inotify.max_user_instances` to ≥8192 before running at high parallelism.

---

#### Sub-chunk 7.1.3: Metrics & Reporting

**Objective:** Produce the metrics buyers already know how to read.

**Input:** Rollout results

**Output:** A metrics module and report generator

**Files:**
- `bench/rtlenv/metrics/compute.py`
- `bench/rtlenv/metrics/report.py`
- `bench/rtlenv/metrics/schema.json`

**Key Logic:**
- Report SR (success rate), PR (progress rate), FC (false complete), USE (unexpected side effects), plus pass@k and per-level breakdown. These are the field's existing vocabulary; inventing our own would create friction in exactly the conversation we want to be easy.
- Confidence intervals on every headline number, computed across seeds. A single-seed number is not a result.
- Reports are JSON first, rendered second, so a buyer can ingest them.

**Test Criteria:**
- [ ] Metrics computed correctly against a hand-verified fixture result set
- [ ] Confidence intervals present on every reported rate
- [ ] Report renders to both JSON and Markdown
- [ ] Per-level and per-task breakdowns present

**Dependencies:** 7.1.2

**Manual Steps:** None

---

### Chunk 7.2: Transfer Measurement

#### Sub-chunk 7.2.1: Reference App Suite

**Objective:** Build the held-out high-fidelity storefronts that transfer is measured against.

**Input:** Survey data, surface generator

**Output:** 2–3 hand-built reference apps, excluded from training

**Files:**
- `sim/apps/ReferenceA/` … `ReferenceC/`
- `bench/tasks/he/reference/*.yaml`
- `docs/reference-apps.md`

**Key Logic:**
- Hand-built, deliberately **not** sampled from the generator — they are the "real-ish" target. Each replicates the structure of a distinct real archetype from the survey (large chain, Shopify template, mobile-first independent) without copying any of them.
- Held out absolutely: a CI check fails if a reference app or its tasks appear in any training split.
- Higher fidelity than generated surfaces: real-feeling latency, more screens, richer error states.
- **This is what makes transfer measurable without touching a real app.** See D1.

**Test Criteria:**
- [ ] CI fails if a reference task ID appears in the train split
- [ ] Each reference app supports the full task suite
- [ ] Reference apps are visually and structurally distinct from any generated surface (pixel and FSM diff)
- [ ] Documentation states the archetype each represents, without naming a real store

**Dependencies:** 5.2.2, 5.1.2

**Manual Steps:**
- 🔧 Choose the three archetypes from your survey data based on frequency, not personal preference

---

#### Sub-chunk 7.2.2: Training Pipeline

**Objective:** Run GRPO against generated surfaces on rented GPUs, reproducibly.

**Input:** Environment, task splits, RunPod

**Output:** A versioned, resumable training run

**Files:**
- `training/config/grpo_qwen3vl4b.yaml`
- `training/launch.py`
- `training/Dockerfile.train`
- `docs/training-runbook.md`

**Key Logic:**
- Base model: a small open VLM in the 4B class, matching the published reference configuration. Local RTX 5070 (12 GB) is for inference and asset generation only — training runs on rented multi-GPU.
- Config is committed and hashed; a run records config hash, data split hash, base model hash and seed.
- Checkpoint to persistent storage every N steps. RunPod instances are interruptible and a lost 12-hour run is a meaningful fraction of your budget.
- Runbook documents the exact launch sequence, because you will run this only three to five times and will not remember it.

**Test Criteria:**
- [ ] A short smoke run (2 steps) completes end-to-end on RunPod
- [ ] Run metadata records all four hashes
- [ ] Killing and resuming from checkpoint produces a consistent loss curve
- [ ] Runbook is complete enough to execute without reading source

**Dependencies:** 7.1.2, 7.2.1

**Manual Steps:**
- 🔧 Create a RunPod account, add credit, verify current multi-GPU pricing and availability before committing to a run
- 🔧 Do the smoke run before the real run. Every time.

---

#### Sub-chunk 7.2.3: Transfer Experiment & Report

**Objective:** Produce the number that closes deals.

**Input:** Training pipeline, reference apps

**Output:** A measured sim-to-reference retention figure and a publishable report

**Files:**
- `bench/experiments/transfer/run.py`
- `bench/experiments/transfer/analyse.py`
- `docs/experiments/transfer-v1.md`
- `reports/transfer-report-v1.pdf`

**Key Logic:**
- Design: measure base model on generated and reference sets; train with GRPO on generated only; re-measure both. Retention = reference gain ÷ generated gain.
- Bucket tasks by baseline performance (uplift / mid / stable-pass) and report per bucket, since aggregate numbers hide where the gain came from.
- **State the limitation explicitly in the report:** this is sim-to-reference, not sim-to-real-device. A buyer who discovers that limitation themselves will discount everything else you claim. A buyer who reads it in your own report reads it as rigour.
- The report is a product. It gets its own version, changelog and reproduction instructions.

**Test Criteria:**
- [ ] Experiment produces a retention figure with confidence intervals
- [ ] Per-bucket breakdown present
- [ ] Report includes exact reproduction instructions and all four hashes
- [ ] Limitation section present and unambiguous
- [ ] An independent reader could re-run the experiment from the report alone

**Dependencies:** 7.2.2

**Manual Steps:**
- 🔧 Budget roughly $100–250 per full run, and cap yourself at three. Design the experiment on paper, review the design, then run it. This is the most expensive single item in the plan.

---

## Phase 8: Packaging & Distribution

**Goal:** Turn the system into an artifact a lab can install, run and audit without talking to you.

**Outcome:** A versioned wheel and container that install clean on a machine that never built them.

---

### Chunk 8.1: Packaging

#### Sub-chunk 8.1.1: verifiers-Spec Environment Package

**Objective:** Expose our tasks through the interface the ecosystem already consumes.

**Input:** Task registry, rollout runner

**Output:** An installable environment package

**Files:**
- `packages_py/rtl_commerce_he/pyproject.toml`
- `packages_py/rtl_commerce_he/rtl_commerce_he/__init__.py`
- `packages_py/rtl_commerce_he/rtl_commerce_he/environment.py`
- `packages_py/rtl_commerce_he/README.md`

**Key Logic:**
- Implement `load_environment(**kwargs) -> vf.Environment` using `MultiTurnEnv` / `ToolEnv`, with our judge exposed as a `Rubric` of weighted reward functions.
- Declare dependencies in `pyproject.toml`; distribute as a wheel, matching the Hub's package-registry model.
- Expose configuration: split, seed, surface count, pathology on/off, language. Defaults must produce a sensible run with no arguments.
- README documents the task taxonomy, metric definitions, and the reproduction command.

**Test Criteria:**
- [ ] `uv pip install dist/*.whl` then `load_environment()` works in a fresh venv
- [ ] Environment runs under the standard verifiers evaluation path
- [ ] Config options all take effect and are documented
- [ ] Wheel contains no `refs/`, no survey raw data, no unreviewed content

**Dependencies:** 7.1.3, 6.1.3

**Manual Steps:**
- 🔧 Verify current `verifiers` spec version and the Hub's packaging requirements before building — this evolves

---

#### Sub-chunk 8.1.2: Container Image

**Objective:** Ship a runnable image so evaluation never depends on a buyer's local setup.

**Input:** Environment package, simulator build

**Output:** A pinned, reproducible container on GHCR

**Files:**
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `docs/container-usage.md`

**Key Logic:**
- Multi-stage: build simulator → install Python env → copy artifacts → non-root runtime user.
- Pin base images by digest, not tag. Reproducibility is a vendor-review question.
- Image contains the built simulator, the environment package, and content — nothing else. No source, no survey references, no keys.
- Health check plus a one-command smoke evaluation so a buyer can confirm it works in 60 seconds.

**Test Criteria:**
- [ ] `docker run ghcr.io/<org>/rtl-env:<tag> smoke` passes on a machine that never built it
- [ ] Image runs as non-root
- [ ] Image size under 3 GB
- [ ] Building twice from the same commit produces identical layer digests

**Dependencies:** 8.1.1

**Manual Steps:**
- 🔧 Test the image on a clean cloud VM, not just your dev machine. This catches the "works on my box" failures that will otherwise surface during a buyer's evaluation.

---

#### Sub-chunk 8.1.3: Versioning & Deprecation Policy

**Objective:** Define how the artifact evolves as models improve, before a buyer asks.

**Input:** Packaging

**Output:** A published policy and the automation enforcing it

**Files:**
- `docs/versioning-policy.md`
- `CHANGELOG.md`
- `tools/release/check_compat.py`

**Key Logic:**
- SemVer over the public surface: task IDs, metric definitions, environment config keys, reward shape.
- **A task whose difficulty drifts out of band is deprecated, not silently retuned.** Silently changing a task invalidates a buyer's historical comparisons, which is the fastest way to lose a repeat customer.
- Deprecation: mark, keep for two minor versions, then remove. Deprecated tasks still run.
- `check_compat.py` fails a release that changes a public identifier without a major bump.

**Test Criteria:**
- [ ] Renaming a task ID without a major bump fails the release
- [ ] Changing reward weights without a minor bump fails
- [ ] CHANGELOG is generated from commits and complete
- [ ] Deprecated tasks still execute and emit a deprecation warning

**Dependencies:** 8.1.2

**Manual Steps:** None

---

#### Sub-chunk 8.1.4: Public Documentation Site

**Objective:** Answer a buyer's technical questions without a meeting.

**Input:** All prior phases

**Output:** A published docs site

**Files:**
- `mkdocs.yml`
- `docs/index.md`, `docs/quickstart.md`, `docs/task-taxonomy.md`, `docs/metrics.md`, `docs/reproducibility.md`, `docs/pathology-catalog.md`
- `.github/workflows/docs.yml`

**Key Logic:**
- Quickstart must get a buyer from zero to a completed evaluation run in under ten minutes.
- Document the reproducibility guarantees explicitly: seed determinism, pinned dependencies, container digests.
- Pathology catalog describes the defect class and cites that it was observed in the field, without publishing the detection heuristics.
- Docs build in CI and fail on broken links.

**Test Criteria:**
- [ ] Site builds and deploys to GitHub Pages
- [ ] Following quickstart verbatim on a clean machine produces a successful evaluation
- [ ] No broken internal links
- [ ] No API keys, survey references or buyer names anywhere in the built site

**Dependencies:** 8.1.3

**Manual Steps:**
- 🔧 Have someone unfamiliar with the project follow the quickstart and record where they get stuck

---

## Phase 9: Security & Vendor Readiness

**Goal:** Survive a lab's vendor review without certification you cannot afford.

**Outcome:** A prepared answer to every technical and security question, and an honest statement of the gaps.

---

### Chunk 9.1: Security Hardening

#### Sub-chunk 9.1.1: Sandbox Isolation

**Objective:** Guarantee the environment cannot reach anything it should not, in either direction.

**Input:** Container, runner

**Output:** A verified isolation posture

**Files:**
- `docs/security/isolation.md`
- `tools/security/verify_isolation.py`
- `Dockerfile` (hardening)
- `docker-compose.yml` (network policy)

**Key Logic:**
- Environment container runs with **no outbound network access by default**. Everything it needs is baked in. A buyer must be able to run it air-gapped, and some will insist.
- Model output is treated as untrusted input: the action parser validates against a strict schema and rejects anything unparseable rather than coercing it. Never `eval`, never dynamic import, never shell interpolation of model output.
- Read-only root filesystem, writable tmpfs for run state only, non-root user, dropped capabilities, no privileged mode.
- Resource limits so a runaway rollout cannot exhaust a buyer's host.

**Test Criteria:**
- [ ] `verify_isolation.py` confirms outbound network attempts fail inside the container
- [ ] Container runs successfully with `--network none`
- [ ] Malformed model output (injection attempt, oversized payload, control characters) is rejected without crashing the runner
- [ ] Container cannot write outside the designated tmpfs

**Dependencies:** 8.1.2

**Manual Steps:** None

---

#### Sub-chunk 9.1.2: Supply Chain & Secrets

**Objective:** Make the dependency and secrets story defensible.

**Input:** CI, SBOM

**Output:** Supply-chain controls and a clean secrets posture

**Files:**
- `.github/workflows/supply-chain.yml`
- `docs/security/supply-chain.md`
- `.gitleaks.toml`
- `tools/security/verify_pins.py`

**Key Logic:**
- All dependencies pinned with lockfiles committed; CI fails on drift.
- CycloneDX SBOM generated per release and attached to the GitHub Release as a downloadable artifact.
- `gitleaks` in CI and as a pre-commit hook. No secret has ever been in this repo and that must stay true — history rewrites are painful and a buyer may scan your history.
- Secrets only via environment variables, never files in the image. Document which keys the build needs and confirm none reach the runtime image.
- Container image scanned with Trivy on every release; high and critical findings block.

**Test Criteria:**
- [ ] Committing a fake API key is blocked by the pre-commit hook and by CI
- [ ] SBOM attached to a test release, parseable by a standard tool
- [ ] Trivy scan passes with no high or critical findings
- [ ] `verify_pins.py` fails if any dependency is unpinned

**Dependencies:** 1.1.5, 8.1.2

**Manual Steps:**
- 🔧 Install the pre-commit hooks locally: `pre-commit install`

---

#### Sub-chunk 9.1.3: Vendor Readiness Pack

**Objective:** Pre-answer the review, including the parts you cannot pass.

**Input:** All security work

**Output:** A completed questionnaire pack and an honest gap statement

**Files:**
- `docs/security/vendor-pack.md`
- `docs/security/questionnaire-answers.md`
- `docs/security/gaps.md`
- `SECURITY.md`

**Key Logic:**
- **Answerable now, with evidence:** reproducible builds, SBOM, dependency licences, isolation model, no-network guarantee, untrusted-input handling, secrets posture, test coverage on judges, versioning and deprecation policy, incident contact, data handling (we process no buyer data).
- **Not answerable pre-revenue, and stated plainly:** SOC 2 Type II, third-party penetration test, 24/7 support, formal business continuity plan, cyber liability insurance.
- The gap document names each gap, why it is currently out of scope, and what would trigger closing it. For a code-artifact purchase these gaps are usually survivable; volunteering them reads as competence, and being caught hiding one reads as the opposite.
- `SECURITY.md` gives a real disclosure contact and response commitment you can actually honour.

**Test Criteria:**
- [ ] Every question in a standard vendor security questionnaire has an answer or an explicit gap entry
- [ ] Every "answerable" claim links to evidence in the repo
- [ ] Gap document is specific, not hedged
- [ ] A technical reader could evaluate the posture without contacting you

**Dependencies:** 9.1.2

**Manual Steps:**
- 🔧 Download two or three real vendor security questionnaire templates and answer them end to end. This surfaces questions you have not thought about while there is still time to address them.

---

## Phase 10: Licensing & Commercial Infrastructure

**Goal:** Track and enforce who bought what, and put the legal entity in place.

**Outcome:** A queryable licensing system and the ability to invoice a foreign buyer legally.

---

### Chunk 10.1: Licence Tracking

#### Sub-chunk 10.1.1: Buyer & Licence Tracker

**Objective:** Answer "who holds this task, under what terms" instantly and reliably.

**Input:** Task registry

**Output:** A licensing database and CLI

**Files:**
- `tools/licensing/db.py`
- `tools/licensing/cli.py`
- `tools/licensing/schema.sql`
- `tools/licensing/reports.py`

**Key Logic:**
- SQLite. Entities: Buyer, Agreement (exclusive / non-exclusive, term, territory, field-of-use), TaskGrant (task ID + version + agreement), Delivery (what was shipped, when, at which artifact digest).
- **Exclusivity conflict detection:** granting an exclusive licence on a task already non-exclusively licensed raises an error, not a warning. Selling the same task exclusively twice is the kind of mistake that ends a company, and it is entirely preventable in software.
- Every delivery records the exact wheel and container digest shipped, so a dispute is resolvable by hash.
- Reports: per-buyer inventory, per-task grant history, expiring agreements.

**Test Criteria:**
- [ ] Granting a conflicting exclusive raises an error naming the prior agreement
- [ ] `licensing query --task <id>` lists all holders and terms
- [ ] `licensing report --buyer <id>` produces a complete delivery manifest
- [ ] Database survives a round-trip export and re-import

**Dependencies:** 8.1.3

**Manual Steps:** None

---

#### Sub-chunk 10.1.2: Release Gating on Licence State

**Objective:** Make it impossible to ship a task to a buyer who has no right to it.

**Input:** Licence tracker, release pipeline

**Output:** A build-time gate

**Files:**
- `tools/release/build_for_buyer.py`
- `.github/workflows/buyer-release.yml`

**Key Logic:**
- Buyer-specific builds assemble only the tasks that buyer's agreements cover, queried from the tracker at build time — never from a hand-maintained list.
- Build fails if any included task lacks a valid grant.
- Every buyer artifact is watermarked with a build manifest listing task IDs, versions and the agreement reference. Not DRM — an audit trail for a dispute.
- Deliveries are automatically recorded back into the tracker on successful build.

**Test Criteria:**
- [ ] Build for a buyer with no grants produces an empty package and a clear error
- [ ] Build includes exactly the granted tasks, verified against a tracker query
- [ ] Build manifest present in the artifact and matches the tracker
- [ ] Delivery is recorded automatically

**Dependencies:** 10.1.1

**Manual Steps:** None

---

### Chunk 10.2: Legal & Entity

#### Sub-chunk 10.2.1: Entity, Invoicing & Tax

**Objective:** Be able to invoice a foreign buyer legally and keep the money.

**Input:** None

**Output:** A registered entity and a working invoicing path

**Files:**
- `docs/business/entity.md` (private notes, not published)
- `docs/business/invoice-template.md`

**Key Logic:**
- Start as עוסק מורשה. A בע"מ costs meaningfully more and requires an accountant on retainer; it is the right structure once revenue justifies it, not before.
- Export of services to foreign customers is generally zero-rated for Israeli VAT, but the conditions matter and getting it wrong is expensive to unwind. Confirm with an accountant before the first invoice.
- Set up a business bank account and a USD-receiving path (Wise or similar) before you need it — buyers pay on net 30–60 and a payment-rail delay after a 60-day wait is demoralising.

**Test Criteria:**
- [ ] Entity registered and tax file number issued
- [ ] Test invoice produced in the correct format with all legally required fields
- [ ] USD receiving account verified with a small test transfer
- [ ] Accountant has confirmed the export-of-services treatment in writing

**Dependencies:** None (start early — registration has lead time)

**Manual Steps:**
- 🔧 **Engage an Israeli accountant.** Ask specifically about: עוסק מורשה vs חברה בע"מ for this revenue profile, zero-rating conditions for export of services, and whether receipts from a US entity change anything. This is not a place to improvise from a web search.
- 🔧 Register with מס הכנסה and מע״מ
- 🔧 Open a business account and a USD receiving path

---

#### Sub-chunk 10.2.2: Contracts & IP

**Objective:** Have the paper ready before a buyer is at the table.

**Input:** Licence model

**Output:** Reviewed contract templates

**Files:**
- `docs/business/contracts/` (private)

**Key Logic:**
- Three documents: a non-exclusive task licence agreement, an exclusive variant, and a contributor IP assignment for authors hired in Phase 12.
- Key terms to get right: acceptance criteria and the cure period (what happens when a buyer says a task does not meet spec), IP ownership of the generator versus the delivered tasks, warranty scope, liability cap, and the exclusivity definition — scoped by task ID and version, not by vague field description.
- Contributor IP assignment must be signed **before** an author's first commit. Retrofitting assignment after the fact is unreliable and a buyer's diligence will ask.

**Test Criteria:**
- [ ] All three templates reviewed by a lawyer
- [ ] Exclusivity clause maps cleanly onto the tracker's data model
- [ ] Acceptance criteria clause references the calibration band and the fixture suite
- [ ] Contributor assignment covers both copyright and any applicable moral-rights waiver

**Dependencies:** 10.1.1

**Manual Steps:**
- 🔧 **Engage a lawyer with software licensing experience.** Bring the templates as drafts rather than asking them to draft from scratch — it costs substantially less.
- 🔧 Defer this spend until a buyer conversation is genuinely live. Do not buy contracts speculatively.

---

## Phase 11: Go-To-Market Infrastructure

**Goal:** Turn the artifact into deals. Begins in parallel with Phase 1, not after Phase 10.

**Outcome:** A published presence, a sales artifact, a tracked pipeline, and a first paid delivery.

---

### Chunk 11.1: Presence & Pipeline

#### Sub-chunk 11.1.1: Buyer Pipeline Tracker

**Objective:** Track outreach systematically instead of in your head.

**Input:** None

**Output:** A lightweight CRM

**Files:**
- `tools/pipeline/db.py`
- `tools/pipeline/cli.py`
- `docs/business/target-list.md` (private)

**Key Logic:**
- SQLite again. Entities: Organisation, Contact, Touch (date, channel, content, outcome), Stage, NextAction with a due date.
- Target list in tiers: environment-native vendors (shortest cycle, they need domain coverage they lack), data foundries, then labs directly.
- **A contact with no scheduled next action is a leak.** The CLI reports these weekly; that report is the single most useful thing this tool does.

**Test Criteria:**
- [ ] `pipeline due` lists overdue next actions
- [ ] `pipeline add-touch` records an interaction against a contact
- [ ] Weekly report shows stage distribution and leaks
- [ ] Database contains no credentials

**Dependencies:** None (build in Phase 1 timeframe)

**Manual Steps:**
- 🔧 Build the target list: every environment vendor, data foundry and lab with a plausible multilingual mandate. Name a specific human where you can find one.

---

#### Sub-chunk 11.1.2: Hub Publication & Bounty Submission

**Objective:** Establish public credibility with a reviewed artifact.

**Input:** Environment package

**Output:** A published environment and a claimed bounty

**Files:**
- `docs/business/hub-submission.md`

**Key Logic:**
- Publish to the Environments Hub with the Prime CLI. The environment is a Python package distributed as a wheel, which our Phase 8 packaging already satisfies.
- Submit against an open bounty where one fits; the open-access tier requires no application.
- The public artifact is what replaces a CV when applying to marketplaces and approaching vendors. It is a credential, not revenue.

**Test Criteria:**
- [ ] Environment installs from the Hub on a machine that never built it
- [ ] Submission accepted and listed
- [ ] Hub listing links to the docs site and the transfer report

**Dependencies:** 8.1.4

**Manual Steps:**
- 🔧 Verify what bounties are currently open and whether any fit before relying on this for income. The programme's shape changes; confirm rather than assume.
- 🔧 Create a Prime Intellect account and install the Prime CLI

---

#### Sub-chunk 11.1.3: Marketplace Applications

**Objective:** Establish an income floor while the product sale develops.

**Input:** Published environment

**Output:** Accepted onto at least one expert marketplace

**Files:**
- `docs/business/marketplace-applications.md`

**Key Logic:**
- Apply to the expert networks that staff environment and eval work, leading with the published environment rather than a résumé.
- This is deliberate runway management: contract work at expert rates covers the remaining plan budget. Cap the hours — it competes directly with build time, and unbounded contract work is how this project quietly becomes a job.

**Test Criteria:**
- [ ] Applications submitted to ≥4 marketplaces
- [ ] ≥1 acceptance
- [ ] First invoice issued and paid

**Dependencies:** 11.1.2

**Manual Steps:**
- 🔧 Apply to each. Lead with the Hub link in the first sentence of every application.
- 🔧 Decide your hours cap before accepting work, and write it down.

---

### Chunk 11.2: Selling

#### Sub-chunk 11.2.1: Minimum Sellable Set

**Objective:** Assemble the smallest package a vendor will actually pay for.

**Input:** Everything through Phase 10

**Output:** A packaged, deliverable MSS

**Files:**
- `releases/mss-v1/` (manifest, not artifacts)
- `docs/business/mss-definition.md`

**Key Logic:**
- MSS v1 contents: 40 tasks calibrated into the 20–60% band, ≥5 distinct generated surfaces, 15 pathology tasks, the transfer report, verifiers wheel plus container, provenance manifest, judge fixture suite, and the vendor readiness pack.
- Deliberately excluded: Arabic, a second domain, volume beyond 40, any SLA.
- A first buyer purchases **evidence of quality, not volume**. Going to 100 tasks costs weeks and does not raise the probability of a first yes. Volume is the second sale.
- If schedule pressure forces a cut, cut task count to 25 and surfaces to 3 before cutting the pathology set or the transfer report. Those two are the product.

**Test Criteria:**
- [ ] MSS installs and runs clean on a fresh machine
- [ ] All 40 tasks within the calibration band at build time
- [ ] Red team clean on the full set
- [ ] Provenance audit and licence gate pass
- [ ] A buyer could evaluate it end to end without contacting you

**Dependencies:** 10.1.2, 9.1.3, 7.2.3

**Manual Steps:** None

---

#### Sub-chunk 11.2.2: Transfer Report as Sales Artifact

**Objective:** Package the measurement as something a lab engineer accepts as evidence.

**Input:** Transfer experiment

**Output:** A versioned public report

**Files:**
- `reports/transfer-report-v1.pdf`
- `reports/transfer-report-v1.md`
- `docs/experiments/reproduce.md`

**Key Logic:**
- Structure: question, method, setup with all hashes, results with confidence intervals, per-bucket breakdown, **limitations**, reproduction instructions.
- The limitations section is the credibility engine. It states plainly that this is sim-to-reference rather than sim-to-real-device, and what that does and does not support.
- Reproducible by a third party from the report alone. A number nobody can reproduce is marketing; a number they can is evidence.

**Test Criteria:**
- [ ] Report renders to PDF and Markdown from one source
- [ ] Every claim traces to a run artifact
- [ ] A colleague could reproduce the headline number from the report alone
- [ ] Limitations section names the sim-to-reference constraint explicitly

**Dependencies:** 7.2.3

**Manual Steps:**
- 🔧 Have one technically credible person outside the project read it and tell you what they do not believe. Fix that before sending it anywhere.

---

#### Sub-chunk 11.2.3: Outreach Execution & First Delivery

**Objective:** Convert the pipeline into a paid delivery.

**Input:** MSS, transfer report, pipeline

**Output:** First revenue

**Files:**
- `docs/business/outreach-templates.md`
- `docs/business/delivery-checklist.md`

**Key Logic:**
- Outreach sequence per target: a short technical message leading with the Hub link and the transfer number, then the report, then an offer of a live evaluation run against their own checkpoint.
- **Lead with the artifact, never with a meeting request.** These buyers evaluate code, and a link that works is worth more than a call.
- Sell non-exclusive first: more references, more relationships, less concentration risk. Exclusivity is the pricing lever for the second or third conversation, not the first.
- Delivery checklist: buyer-specific build, licence grants recorded, delivery logged with digests, acceptance criteria agreed in writing before shipping.

**Test Criteria:**
- [ ] ≥5 buyers have run the environment
- [ ] ≥1 agreement signed
- [ ] Delivery executed via the buyer-build pipeline with grants recorded
- [ ] Payment received

**Dependencies:** 11.2.1, 11.2.2, 10.2.2

**Manual Steps:**
- 🔧 Agree acceptance criteria in writing before shipping anything. The most common first-deal failure is a vague "meets our quality bar" clause.
- 🔧 Ask every buyer who declines what would have changed their mind, and record the answer in the pipeline. This is the cheapest product research available.

---

#### Sub-chunk 11.2.4: Upstream Contribution

**Objective:** Build reputation in the ecosystem without giving away the moat.

**Input:** RTL primitives

**Output:** A merged upstream contribution

**Files:**
- (upstream PR, not in this repo)
- `docs/business/upstream-policy.md`

**Key Logic:**
- **Contribute:** generic bidirectional rendering support, RTL layout primitives, one demo storefront. These make you the person who brought RTL to the platform, which is a credential.
- **Never contribute:** surveyed parameter distributions, the generator configuration, the pathology catalog's detection heuristics, the reference apps, or any task set.
- The policy document exists so this line does not get blurred in a moment of enthusiasm.

**Test Criteria:**
- [ ] PR merged upstream
- [ ] Nothing from the private list appears in the contribution
- [ ] Upstream policy document is explicit about the boundary

**Dependencies:** 3.1.3

**Manual Steps:**
- 🔧 Read the upstream CONTRIBUTING guide and follow its PR requirements exactly

---

## Phase 12: Arabic Expansion

**Goal:** Extend the system to Arabic — the market Hebrew was proving the method for.

**Outcome:** An Arabic task set of comparable quality, produced substantially by hired authors rather than by you.

**Gate:** This phase begins after first revenue (11.2.3). If revenue slips, see the solo fallback at the end of this phase.

---

### Chunk 12.1: Arabic Technical Foundation

#### Sub-chunk 12.1.1: Arabic Script Engine

**Objective:** Handle what genuinely differs from Hebrew: shaping, ligatures, contextual forms.

**Input:** RTL primitives

**Output:** Arabic support in the primitives package

**Files:**
- `packages/rtl-primitives/src/arabic/shaping.ts`
- `packages/rtl-primitives/src/arabic/forms.ts`
- `packages/rtl-primitives/src/arabic/numerals.ts`
- `packages/rtl-primitives/tests/arabic.test.ts`
- `docs/hebrew-vs-arabic.md`

**Key Logic:**
- **Reuses cleanly from Hebrew:** bidi resolution, layout mirroring, logical properties, icon mirror registry, direction-aware components, most pathology injectors.
- **Genuinely new:** contextual letter forms (isolated, initial, medial, final), mandatory ligatures (lam-alef), Eastern Arabic-Indic numerals (٠١٢٣) vs Western (0123) — which vary by country and are a surface parameter — tatweel handling, and diacritic rendering.
- New Arabic-specific pathologies: broken letter joining after a string operation, numeral-system inconsistency within one page, ligature failure at a text-truncation boundary.
- The comparison document is a real deliverable — it tells a buyer you understand the distinction, and it tells future authors what transfers.

**Test Criteria:**
- [ ] Golden-file suite of ≥100 Arabic strings rendering with correct contextual forms
- [ ] Lam-alef ligature renders correctly in all positions
- [ ] Both numeral systems render and are selectable by parameter
- [ ] Letter-joining pathology produces a deterministic, visually broken but plausible defect
- [ ] Every Hebrew primitive test still passes unchanged

**Dependencies:** 3.1.1, 3.1.2, 3.1.3

**Manual Steps:**
- 🔧 Build the Arabic golden-file corpus with a native speaker. Do not build it yourself from documentation.

---

#### Sub-chunk 12.1.2: Dialect & Register Decision

**Objective:** Decide what Arabic we ship, and accept the cost.

**Input:** Market research, buyer conversations

**Output:** A written decision

**Files:**
- `docs/decisions/arabic-register.md`

**Key Logic:**
- Options: MSA only (broadest, safest, least natural for consumer UI); MSA plus one Gulf variant (matches where sovereign AI budgets concentrate); MSA plus Levantine (easiest to staff from Haifa).
- Real consumer e-commerce in the Arab world mixes MSA UI chrome with dialectal customer communication, so a realistic environment probably needs both registers even if the UI is MSA.
- The decision drives author hiring, content generation cost, and which buyers the set appeals to.
- Recommendation: MSA for UI chrome, with dialectal variation confined to customer-message content where it is a surface parameter. Revisit if a buyer conversation indicates a specific regional mandate.

**Test Criteria:**
- [ ] Decision written with reasoning and cost implications
- [ ] Author job description reflects the decision
- [ ] Content pipeline configuration reflects the decision

**Dependencies:** 11.2.3

**Manual Steps:**
- 🔧 Ask two or three buyers directly which Arabic they need before deciding. This is cheap and the answer may be decisive.

---

### Chunk 12.2: Arabic Content & Authoring

#### Sub-chunk 12.2.1: Arabic Content Pipeline

**Objective:** Produce Arabic catalogs, copy and surfaces through the existing pipeline.

**Input:** Content pipeline, Arabic primitives, register decision

**Output:** Arabic content, provenance-clean

**Files:**
- `tools/content/catalog/arabic_lexicon.json`
- `tools/content/copy/prompts/ar/*.txt`
- `content/copy/ar/`
- `content/catalogs/ar/`
- `content/distributions/ar-commerce.json`

**Key Logic:**
- Same generators, new lexicon and prompts. **If this requires changing the generator, the generator was wrong** — that is the test of Phase 4's design.
- Arabic brand list assembled and added to the brand guard.
- Arabic copy passes through the same human review queue, reviewed by a native speaker, not by you.
- Arabic surface distributions come from an Arabic-market survey — do not reuse the Hebrew distribution. Israeli and Gulf e-commerce conventions differ in address format, payment methods and delivery options.

**Test Criteria:**
- [ ] Arabic catalog generates deterministically from seed
- [ ] Brand check passes with the Arabic brand list
- [ ] Provenance audit passes on Arabic content
- [ ] Zero generator source changes were required, only configuration and content

**Dependencies:** 12.1.1, 12.1.2, 4.2.3

**Manual Steps:**
- 🔧 Commission an Arabic-market store survey from a hired author using the Phase 5 instrument. Target ≥60 stores in the chosen market.

---

#### Sub-chunk 12.2.2: Author Hiring & Onboarding

**Objective:** Bring on Arabic authors who can produce at quality without your line-by-line review.

**Input:** Onboarding system from 6.2.3

**Output:** Two productive authors

**Files:**
- `docs/business/author-role.md`
- (signed IP assignments, private)

**Key Logic:**
- Profile: native Arabic speaker, technically literate enough for YAML and a CLI, with real consumer e-commerce experience in the target market. The technical bar is lower than the domain bar — you can teach the CLI, you cannot teach lived familiarity with an Arabic checkout flow.
- Haifa's multilingual technical labour pool is the structural advantage here; use it.
- The three graded onboarding exercises are the screen. The third — finding the planted exploit in a weak judge — is the one that predicts pathology-authoring ability.
- IP assignment signed before first commit, without exception.

**Test Criteria:**
- [ ] Both authors pass all three onboarding exercises
- [ ] Both have signed IP assignments on file before any commit
- [ ] First author PR passes the automated QA gate without your intervention
- [ ] Authors cannot modify anything outside `bench/tasks/`

**Dependencies:** 6.2.3, 10.2.2, 11.2.3

**Manual Steps:**
- 🔧 Recruit through university networks and local technical communities rather than generic job boards.
- 🔧 Pay fairly and on time. Your authoring capacity is the scarce input, and a reputation for slow payment in a small community is expensive.
- 🔧 Have the lawyer confirm the IP assignment is valid under Israeli employment or contractor law for the arrangement you choose.

---

#### Sub-chunk 12.2.3: Arabic Task & Pathology Sets

**Objective:** Produce the Arabic task set, authored by the hires.

**Input:** Authors, Arabic surfaces, survey

**Output:** 40+ Arabic tasks including 25+ pathology tasks

**Files:**
- `bench/tasks/ar/commerce/**`
- `bench/tasks/ar/pathology/**`

**Key Logic:**
- **Tasks are authored natively, never translated from Hebrew.** A translated task inherits Hebrew assumptions about address format, payment method, size systems and delivery, and a buyer will notice. This is also precisely the failure the whole thesis is built on rejecting.
- Pathology tasks cite the Arabic survey, not the Hebrew one.
- Your role shifts to reviewing cheat surfaces and spot-checking the QA gate — not authoring.

**Test Criteria:**
- [ ] All Arabic tasks pass lint, fixtures, mutation coverage and red team
- [ ] Calibration places the Arabic set in the 20–60% band
- [ ] Every pathology task cites an Arabic survey capture
- [ ] ≥80% of tasks merged without requiring your direct intervention

**Dependencies:** 12.2.2, 12.2.1

**Manual Steps:**
- 🔧 Review every `cheat_surface` field personally even once authors are productive. This is the one review you do not delegate.

---

### Chunk 12.3: Arabic Validation & Launch

#### Sub-chunk 12.3.1: Arabic Transfer Validation

**Objective:** Reproduce the transfer measurement in Arabic.

**Input:** Arabic task set, training pipeline

**Output:** An Arabic transfer figure

**Files:**
- `sim/apps/ReferenceAR_A/`, `ReferenceAR_B/`
- `bench/experiments/transfer/ar_run.py`
- `reports/transfer-report-ar-v1.pdf`

**Key Logic:**
- Same methodology as Hebrew, so the numbers are comparable — that comparability is itself a selling point.
- Two Arabic reference apps, held out with the same CI enforcement.
- If Arabic retention is materially lower than Hebrew, that is a finding worth reporting rather than hiding. It tells a buyer something real about cross-script generalisation, and hiding it would be discovered.

**Test Criteria:**
- [ ] Arabic retention figure produced with confidence intervals
- [ ] Methodology identical to Hebrew, differences documented if any
- [ ] Reference apps held out, enforced by CI
- [ ] Report published

**Dependencies:** 12.2.3, 7.2.2

**Manual Steps:**
- 🔧 Budget roughly $100–250. Revenue-funded by this point.

---

#### Sub-chunk 12.3.2: Multilingual Packaging & Launch

**Objective:** Ship Hebrew and Arabic as one coherent product.

**Input:** Both language sets

**Output:** A multilingual release and repositioned market presence

**Files:**
- `packages_py/rtl_commerce/` (renamed from `rtl_commerce_he`)
- `docs/index.md` (repositioned)
- `reports/transfer-report-combined.pdf`

**Key Logic:**
- Language becomes a configuration parameter, consistent with the architecture's premise. A separate Arabic package would contradict the whole design.
- Positioning shifts from "Hebrew commerce environments" to "RTL agentic environments" — breadth is now demonstrated rather than claimed.
- Combined report compares Hebrew and Arabic transfer, which is a genuinely novel data point and the strongest single piece of marketing you will have.
- Package rename is a major version bump with the old name aliased for two minor versions, per the deprecation policy.

**Test Criteria:**
- [ ] `load_environment(language="ar")` and `language="he"` both work from one package
- [ ] Old package name still resolves with a deprecation warning
- [ ] Combined report published
- [ ] Docs site repositioned with no broken links

**Dependencies:** 12.3.1, 8.1.3

**Manual Steps:**
- 🔧 Notify every existing buyer of the rename before publishing, not after

---

### Solo Fallback (if revenue slips)

If 11.2.3 has not closed when you are ready for Phase 12, run the reduced version rather than stalling:

- MSA only, no dialectal variation
- 25 tasks instead of 40, 15 pathology instead of 25
- No hires — you author, using a paid native-speaker reviewer on an hourly basis for the copy review queue and the golden-file corpus (12.1.1)
- Arabic survey reduced to 30 stores, commissioned hourly
- Skip 12.3.1; extend the Hebrew transfer report with a qualitative Arabic section instead

This produces a weaker but genuine Arabic capability at perhaps a fifth of the cost, and keeps the thesis alive while the Hebrew sale develops. It is a degradation, not a failure.

---


## Appendix A: File Structure

```
rtl-environments/
│
├── packages/                          # JS/TS workspace — our code
│   ├── core-semantic/                 # DOMAIN-AGNOSTIC. No commerce vocabulary.
│   │   ├── src/
│   │   │   ├── domain.ts              # the plugin interface
│   │   │   ├── state.ts               # snapshot / diff / patch / fork
│   │   │   ├── operation.ts
│   │   │   ├── invariant.ts
│   │   │   ├── rng.ts                 # the ONLY source of randomness
│   │   │   ├── logging.ts
│   │   │   └── conformance/suite.ts
│   │   └── tests/
│   │
│   ├── domains/
│   │   ├── commerce/                  # first implementation
│   │   │   ├── src/{entities,operations,invariants,seed}.ts
│   │   │   └── tests/
│   │   └── insurance-stub/            # permanent leak detector
│   │
│   ├── rtl-primitives/
│   │   ├── src/
│   │   │   ├── bidi/{resolve,segment,isolate}.ts
│   │   │   ├── numerals/{format,money,datetime}.ts
│   │   │   ├── layout/{direction,mirror}.tsx + components/
│   │   │   ├── type/{fonts,scale}.ts
│   │   │   └── arabic/{shaping,forms,numerals}.ts
│   │   └── tests/ + golden/
│   │
│   ├── pathology/
│   │   ├── src/{registry.ts, injectors/*.ts, catalog.json}
│   │   └── tests/
│   │
│   └── surface-gen/
│       ├── src/{params/{schema,space,sample}.ts, compose.ts, theme.ts, nav.ts}
│       └── tests/
│
├── sim/                               # forked MobileGym (Apache-2.0, NC content purged)
│   ├── os/                            # upstream, minimally modified
│   ├── system/                        # upstream system apps
│   ├── apps/
│   │   ├── Storefront/                # ours — a view over the commerce domain
│   │   │   ├── manifest.ts
│   │   │   ├── StorefrontApp.tsx
│   │   │   ├── navigation.declaration.ts
│   │   │   ├── pages/ components/ state/bridge.ts
│   │   │   ├── res/strings.{he,ar}.json
│   │   │   └── generated/             # surface-gen output
│   │   ├── ReferenceA/ ReferenceB/ ReferenceC/      # held out, Hebrew
│   │   └── ReferenceAR_A/ ReferenceAR_B/            # held out, Arabic
│   ├── NOTICE
│   └── LICENSE                        # Apache-2.0
│
├── bench/                             # Python workspace
│   ├── rtlenv/
│   │   ├── rng.py  logging.py  domain_protocol.py
│   │   ├── env/control.py
│   │   ├── judge/{core,matchers,verdict,progress,reward,pathology}.py
│   │   ├── task/{schema,registry,validate,pathology_task}.py
│   │   ├── authoring/{dsl,cli,qa_gate}.py + templates/ + exercises/
│   │   ├── agent/{base,generic,anthropic,openai,openai_compatible,human}.py
│   │   ├── runner/{orchestrator,pool,isolation}.py
│   │   ├── metrics/{compute,report}.py
│   │   └── metatest/harness.py + fixtures/
│   ├── tasks/
│   │   ├── he/{commerce,pathology,reference}/**
│   │   └── ar/{commerce,pathology,reference}/**
│   ├── redteam/{harness.py, strategies/, findings.md}
│   ├── calibration/{run,report}.py
│   ├── experiments/{randomisation,transfer}/
│   └── tests/
│
├── packages_py/
│   └── rtl_commerce/                  # the verifiers-spec wheel we ship
│
├── content/                           # all shipped assets, provenance-tracked
│   ├── MANIFEST.json
│   ├── catalogs/{he,ar}/
│   ├── copy/{he,ar}/
│   ├── images/
│   ├── fonts/                         # OFL only, each with LICENSE
│   └── distributions/{he,ar}-commerce.json
│
├── refs/                              # GITIGNORED — never shipped
│   ├── survey/                        # raw captures, screenshots
│   └── brand-logos/                   # perceptual-hash test fixtures
│
├── tools/
│   ├── licence/{scan.py, policy.yaml, brandlist.txt, nc_purge_manifest.json}
│   ├── provenance/{schema.json, audit.py, record.py, brand_check.py}
│   ├── content/{catalog/, copy/, images/, fonts/}
│   ├── survey/{schema.json, capture.py, report.py}
│   ├── licensing/{db.py, cli.py, schema.sql, reports.py}
│   ├── pipeline/{db.py, cli.py}
│   ├── release/{build_for_buyer.py, check_compat.py}
│   └── security/{verify_isolation.py, verify_pins.py}
│
├── training/
│   ├── config/grpo_qwen3vl4b.yaml
│   ├── launch.py
│   └── Dockerfile.train
│
├── docs/
│   ├── index.md quickstart.md task-taxonomy.md metrics.md
│   ├── reproducibility.md pathology-catalog.md authoring-guide.md
│   ├── author-onboarding.md survey-methodology.md hebrew-vs-arabic.md
│   ├── versioning-policy.md training-runbook.md reference-apps.md
│   ├── security/{isolation,supply-chain,vendor-pack,questionnaire-answers,gaps}.md
│   ├── experiments/  decisions/  calibration/
│   └── business/                      # gitignored SCRATCH only; real business docs live in a separate private repo
│
├── reports/                           # transfer reports, versioned
├── releases/                          # per-buyer build manifests
│
├── .github/workflows/
│   ├── ci.yml licence-gate.yml supply-chain.yml redteam.yml
│   └── docs.yml release.yml buyer-release.yml author-pr.yml
│
├── Dockerfile  docker-compose.yml  Makefile
├── UPSTREAM.md  SECURITY.md  CHANGELOG.md  NOTICE  LICENSE
├── pnpm-workspace.yaml  package.json  pyproject.toml  uv.lock
└── .gitignore  .gitleaks.toml  mkdocs.yml
```

**Business documents.** Every `docs/business/…` path named in Phases 10–11 and 12 lives in a **separate private repository**, not in this one. The path is kept in this plan for readability only. `docs/business/` in this repo is gitignored scratch space and never holds the canonical copy.

---

## Appendix B: Manual Steps Summary

### Phase 1: Foundation

| Step | Description | When |
|------|-------------|------|
| 🔧 | Create private GitHub repository | Before 1.1.1 |
| 🔧 | Install Node ≥22, Python ≥3.11, pnpm, uv, Docker | Before 1.1.1 |
| 🔧 | Read all four MobileGym licence files in full | Before 1.1.2 |
| 🔧 | Verify vendored `mobilegym-rl/` third-party licences | 1.1.2 |
| 🔧 | Open a trivial upstream PR to test the contribution process | 1.1.2 |
| 🔧 | Populate `brandlist.txt` (~150 brands, Hebrew + English) | 1.1.3 |
| 🔧 | Enable Actions, GHCR write, branch protection on `main` | 1.1.5 |

### Phase 2: Semantic & Verification

| Step | Description | When |
|------|-------------|------|
| 🔧 | Hand-write the first 15 "plausibly wrong" transcripts | 2.2.3 |

### Phase 3: RTL Layer

| Step | Description | When |
|------|-------------|------|
| 🔧 | Build the 100-string Hebrew bidi golden corpus | 3.1.1 |
| 🔧 | Download and licence-verify OFL fonts | 3.1.4 |

### Phase 4: Content

| Step | Description | When |
|------|-------------|------|
| 🔧 | Assemble ~100 real logos into gitignored `refs/` | 4.1.2 |
| 🔧 | Build the ~500-term Hebrew lexicon | 4.2.1 |
| 🔧 | Review the entire first Hebrew copy corpus | 4.2.2 |
| 🔧 | Add `ANTHROPIC_API_KEY` to `.env.local` | 4.2.2 |
| 🔧 | Install ComfyUI; verify model licence permits commercial use | 4.2.3 |
| 🔧 | Spot-review 50 generated images for brand resemblance | 4.2.3 |

### Phase 5: Survey & Generator — **the moat**

| Step | Description | When |
|------|-------------|------|
| 🔧 | **Survey 100+ Israeli stores across sampling strata** | 5.1.2 |
| 🔧 | Screenshot every defect; note the correct agent behaviour | 5.1.2 |
| 🔧 | Use a fresh browser profile per session | 5.1.2 |

### Phase 6: Authoring

| Step | Description | When |
|------|-------------|------|
| 🔧 | Write every `cheat_surface` field yourself | 6.1.2 |
| 🔧 | Author the pathology set from your own screenshots | 6.1.3 |
| 🔧 | Run the model-driven red team manually first, read every transcript | 6.2.1 |
| 🔧 | Budget $20–50 per calibration run | 6.2.2 |
| 🔧 | Add model API keys; cap concurrency ($30–80 per run) | 6.3.1 |

### Phase 7: Evaluation & Training

| Step | Description | When |
|------|-------------|------|
| 🔧 | Add model provider API keys | 7.1.1 |
| 🔧 | Install nginx; raise `fs.inotify.max_user_instances` to ≥8192 | 7.1.2 |
| 🔧 | Choose reference archetypes by survey frequency, not preference | 7.2.1 |
| 🔧 | Create RunPod account; verify current multi-GPU pricing | 7.2.2 |
| 🔧 | **Always run the 2-step smoke run first** | 7.2.2 |
| 🔧 | Budget $100–250 per run; cap at three runs | 7.2.3 |

### Phase 8: Packaging

| Step | Description | When |
|------|-------------|------|
| 🔧 | Verify current `verifiers` spec and Hub packaging requirements | 8.1.1 |
| 🔧 | Test the container on a clean cloud VM, not just your dev box | 8.1.2 |
| 🔧 | Have an outsider follow the quickstart and note where they stall | 8.1.4 |

### Phase 9: Security

| Step | Description | When |
|------|-------------|------|
| 🔧 | `pre-commit install` | 9.1.2 |
| 🔧 | Answer 2–3 real vendor security questionnaires end to end | 9.1.3 |

### Phase 10: Commercial

| Step | Description | When |
|------|-------------|------|
| 🔧 | **Engage an Israeli accountant** — entity form, VAT zero-rating | 10.2.1 — long lead time, start early |
| 🔧 | Register with מס הכנסה and מע״מ | 10.2.1 |
| 🔧 | Open business account + USD receiving path; test transfer | 10.2.1 |
| 🔧 | **Engage a software-licensing lawyer** — bring drafts, not blank pages | 10.2.2 |
| 🔧 | Defer legal spend until a buyer conversation is live | 10.2.2 |

### Phase 11: Go-To-Market — **starts in the Phase 1 window**

| Step | Description | When |
|------|-------------|------|
| 🔧 | Build the tiered target list with named humans | 11.1.1 — START NOW |
| 🔧 | Verify which Hub bounties are currently open and relevant | 11.1.2 |
| 🔧 | Create Prime Intellect account; install Prime CLI | 11.1.2 |
| 🔧 | Apply to ≥4 expert marketplaces, leading with the Hub link | 11.1.3 |
| 🔧 | Decide and write down your contract-hours cap | 11.1.3 |
| 🔧 | Have an outside technical reader attack the transfer report | 11.2.2 |
| 🔧 | Agree acceptance criteria in writing before shipping | 11.2.3 |
| 🔧 | Ask every declining buyer what would have changed their mind | 11.2.3 |
| 🔧 | Follow the upstream CONTRIBUTING guide exactly | 11.2.4 |

### Phase 12: Arabic

| Step | Description | When |
|------|-------------|------|
| 🔧 | Build the Arabic golden corpus with a native speaker | 12.1.1 |
| 🔧 | Ask 2–3 buyers which Arabic they need before deciding | 12.1.2 |
| 🔧 | Commission an Arabic-market survey (≥60 stores) | 12.2.1 |
| 🔧 | Recruit authors via university and local technical networks | 12.2.2 |
| 🔧 | IP assignment signed **before** first commit, no exceptions | 12.2.2 |
| 🔧 | Lawyer confirms IP assignment validity under Israeli law | 12.2.2 |
| 🔧 | Review every `cheat_surface` personally, even after delegating | 12.2.3 |
| 🔧 | Notify existing buyers of the package rename before publishing | 12.3.2 |

---

## Appendix C: Development Order

Work sub-chunks in this order. Three items run **continuously in parallel** from the start and are marked ⟳ — do not serialise them behind the build.

```
PHASE 1: Foundation & Infrastructure
├── 1.1.1 Monorepo Structure (🔧 repo, toolchain)
├── 1.1.2 MobileGym Fork & NC Purge (🔧 licences, upstream test PR)
├── 1.1.3 Licence Firewall CI (🔧 brandlist)
├── 1.1.4 Determinism & Logging Foundations
├── 1.1.5 CI/CD Pipeline (🔧 Actions, GHCR)
├── 11.1.1 Buyer Pipeline Tracker ⟳ START HERE, NOT LATER (🔧 target list)
└── 10.2.1 Entity & Invoicing ⟳ (🔧 accountant — long lead time)

PHASE 2: Semantic Layer & Verification Engine
├── 2.1.1 Domain Interface Definition
├── 2.1.2 Commerce Domain Implementation
├── 2.1.3 Stub Second Domain
├── 2.2.1 State-Diff Judge Core
├── 2.2.2 Partial Credit & Reward Shaping
├── 2.2.3 Judge Meta-Test Harness (🔧 15 transcripts)
└── 2.2.4 Task Schema & Registry

PHASE 3: RTL Rendering Layer
├── 3.1.1 Bidirectional Text Engine (🔧 golden corpus)
├── 3.1.2 Numeral Systems & Money Formatting
├── 3.1.3 RTL Layout Primitives
├── 3.1.4 Hebrew Typography & Font Pipeline (🔧 OFL fonts)
├── 3.2.1 Pathology Injector Framework
├── 3.2.2 Pathology-Aware Judging
├── 3.3.1 Storefront App Shell
├── 3.3.2 State Control API Binding
└── 5.1.1 Survey Instrument & Schema ⟳ build now, use continuously

SURVEY (runs alongside Phases 3–4 — do not serialise)
└── 5.1.2 Execute the Survey ⟳ (🔧 100+ stores — THE MOAT)

PHASE 4: Content Pipeline & Provenance
├── 4.1.1 Provenance Manifest & Audit Tool
├── 4.1.2 Trademark & Brand Hygiene Check (🔧 logo refs)
├── 4.2.1 Synthetic Catalog Generator (🔧 lexicon)
├── 4.2.2 Hebrew Copy Generation (🔧 full review)
└── 4.2.3 Image Asset Pipeline (🔧 ComfyUI)

PHASE 5: Surface Generator
├── 5.2.1 Parameter Space Definition
└── 5.2.2 Surface Composition Engine

PHASE 6: Task Authoring System
├── 6.1.1 Task Authoring DSL & CLI
├── 6.1.2 Core Task Set (🔧 cheat surfaces)
├── 6.1.3 Pathology Task Set (🔧 from your screenshots)
├── 6.2.1 Reward-Hacking Red Team Harness (🔧 manual first pass)
├── 6.2.2 Difficulty Calibration Pipeline (🔧 $20–50/run)
└── 6.2.3 Author Onboarding & QA System

GATE 1
└── 6.3.1 Randomisation Validation Experiment ⚠ (🔧 $30–80) — formerly 5.2.3
        Success must drop materially from fixed to randomised surfaces.
        If it does not, return to 5.1.2 and survey harder. Do not proceed.

PHASE 7: Evaluation & Training Harness
├── 7.1.1 Agent Adapters (🔧 API keys)
├── 7.1.2 Parallel Rollout Runner (🔧 nginx, inotify)
├── 7.1.3 Metrics & Reporting
├── 7.2.1 Reference App Suite (🔧 choose archetypes by frequency)
├── 7.2.2 Training Pipeline (🔧 RunPod — smoke run first, every time)
└── 7.2.3 Transfer Experiment & Report ⚠ GATE 2 (🔧 $100–250, max 3 runs)
        Retention under ~70% means buyers discount everything. Fix before selling.

PHASE 8: Packaging & Distribution
├── 8.1.1 verifiers-Spec Environment Package (🔧 verify spec version)
├── 8.1.2 Container Image (🔧 clean VM test)
├── 8.1.3 Versioning & Deprecation Policy
└── 8.1.4 Public Documentation Site (🔧 outsider quickstart test)

CREDENTIAL & RUNWAY
├── 11.1.2 Hub Publication & Bounty Submission (🔧 verify open bounties)
├── 11.1.3 Marketplace Applications (🔧 apply to ≥4; set hours cap)
└── 11.2.4 Upstream Contribution (🔧 follow CONTRIBUTING)

PHASE 9: Security & Vendor Readiness
├── 9.1.1 Sandbox Isolation
├── 9.1.2 Supply Chain & Secrets (🔧 pre-commit)
└── 9.1.3 Vendor Readiness Pack (🔧 answer real questionnaires)

PHASE 10: Licensing & Commercial Infrastructure
├── 10.1.1 Buyer & Licence Tracker
├── 10.1.2 Release Gating on Licence State
└── 10.2.2 Contracts & IP (🔧 lawyer — only once a buyer is live)

SELLING
├── 11.2.1 Minimum Sellable Set
├── 11.2.2 Transfer Report as Sales Artifact (🔧 outside reader)
└── 11.2.3 Outreach Execution & First Delivery ⚠ GATE 3 — REVENUE
        Phase 12 does not begin until this closes. Fallback below if it slips.

PHASE 12: Arabic Expansion
├── 12.1.1 Arabic Script Engine (🔧 native-speaker corpus)
├── 12.1.2 Dialect & Register Decision (🔧 ask buyers)
├── 12.2.1 Arabic Content Pipeline (🔧 commission survey)
├── 12.2.2 Author Hiring & Onboarding (🔧 recruit; IP assignments)
├── 12.2.3 Arabic Task & Pathology Sets (🔧 review cheat surfaces)
├── 12.3.1 Arabic Transfer Validation (🔧 $100–250)
└── 12.3.2 Multilingual Packaging & Launch (🔧 notify buyers)
```

**Total sub-chunks:** 67
**Hard gates:** 3 — randomisation (6.3.1), transfer retention (7.2.3), revenue (11.2.3)
**Longest lead times:** the accountant (10.2.1) and the survey (5.1.2). Both start in the Phase 1 window.
**Most commonly skipped, most damaging:** 11.1.1, the target list. Every solo technical founder defers outreach until the product feels good enough, then discovers relationships take a quarter to form.

---

## Appendix D: Quick Reference

### Cost Summary (pre-revenue ceiling: $5,000)

| Item | Sub-chunks | Estimate |
|------|-----------|----------|
| Claude Code subscription | all build work | $1,000–2,000 |
| Model API — calibration & red team | 6.3.1, 6.2.1, 6.2.2 | $300–600 |
| Model API — copy generation | 4.2.2 | $50–150 |
| RunPod — transfer experiment | 7.2.2, 7.2.3 | $300–750 (3 runs max) |
| Lawyer — contract templates | 10.2.2 | $500–1,500 |
| Accountant + entity registration | 10.2.1 | $150–600 |
| Domain, CI, storage | 1.1.5 | $150–250 |
| Contingency | — | $500 |
| **Total** | | **$2,950–6,350** |

**This sits at or slightly over the ceiling.** Three levers, in order of preference:

1. **Cap transfer runs at three** and design the experiment on paper first. The smoke run is not one of the three.
2. **Defer the lawyer** until a buyer conversation is genuinely live. Do not buy templates speculatively.
3. **Marketplace contract work (11.1.3) is the real fix.** One month at expert rates covers the entire remaining budget. Cap the hours in writing — unbounded contract work is how this quietly becomes a job instead of a company.

Image generation is free (local GPU). Fonts are free (OFL). CI is free (GitHub free tier). No SaaS error tracking, no observability vendor, no hosting — all deliberate omissions, not oversights.

### Key Decisions to Validate Early

| Decision | Validate By |
|----------|-------------|
| Is the surface variation real or cosmetic? | 6.3.1 — everything downstream assumes it is real |
| Does sim-to-reference transfer hold? | 7.2.3 — under ~70% and buyers discount the whole pitch |
| Are Hub bounties currently open and relevant? | 11.1.2 — verify before relying on it for the credential |
| Does the upstream contribution process work? | 1.1.2 — test with a trivial PR, not with your RTL work |
| Is the `verifiers` spec stable at our target version? | 8.1.1 — check before packaging |
| Does the domain interface actually generalise? | 2.1.3 — the insurance stub passes, or the core has leaked |
| Will a vendor pay for a 40-task pilot? | 11.2.3 — the first "no" citing volume changes the MSS |
| Which Arabic do buyers actually want? | 12.1.2 — ask before building |

### Standing Disciplines (never "done")

| Discipline | Sub-chunk | Cadence |
|-----------|-----------|---------|
| Red team against own rubrics | 6.2.1 | Nightly in CI; manual pass per release |
| Difficulty calibration | 6.2.2 | After each task batch; before each release |
| Provenance audit | 4.1.1 | Every commit |
| Licence firewall | 1.1.3 | Every commit |
| Buyer pipeline review | 11.1.1 | Weekly — the leak report is the point |
| Survey expansion | 5.1.2 | Ongoing; every new defect is a candidate task |

### The Three Things That Matter Most

If the repo burned down and you could keep three artifacts:

1. **`content/distributions/he-commerce.json`** — the surveyed parameter distribution. Irreplaceable without redoing 100 store visits.
2. **`bench/tasks/he/pathology/**`** — the pathology set with its `observed_in` citations. This is the product.
3. **`bench/redteam/findings.md`** — every exploit ever found against your judges. Institutional memory that cannot be reconstructed.

Everything else is code, and code is the cheap part.

---

*End of RTL Environments Implementation Plan*
