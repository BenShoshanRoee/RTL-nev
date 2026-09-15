# Upstream: MobileGym

`sim/` is a hard fork of [MobileGym](https://github.com/Purewhiter/mobilegym)
(Purewhiter/mobilegym), Apache-2.0. This file is the auditable record of the fork point,
what was removed, what we changed, and how to sync.

## Fork point

| | |
|---|---|
| Upstream repository | https://github.com/Purewhiter/mobilegym |
| Fork-point commit | `57bc275accdb06eea3aee13880afdebbe80583d3` (2026-08-28) |
| Local reference clone | `refs/upstream/mobilegym` (gitignored, full history, never shipped) |
| Purge tool | `tools/licence/purge_fork.py` (deterministic; re-runnable) |
| Purge record | `tools/licence/nc_purge_manifest.json` (every removed path, SHA-256, size, reason) |
| Audit command | `uv run python tools/licence/scan.py --mode purge-audit` |

Upstream tracked 6,676 files at the fork point. We kept 463 and removed 6,213 (plus 5 files
we replaced with our own content at the same path: README.md and four data stubs).
The raw upstream tree was **never committed** to this repository: only the purged tree entered
`sim/`, so no CC BY-NC content or brand asset exists anywhere in our git history. The
upstream commit SHA above plus the per-file hashes in the manifest are the audit reference.

## Upstream licences (read in full by the operator before the purge, 2026-09-15)

| File (upstream) | Licence | Our handling |
|---|---|---|
| `LICENSE` | Apache-2.0 | Kept as `sim/LICENSE` |
| `NOTICE` | attribution | Kept and extended as `sim/NOTICE` |
| `LICENSE-DATA` | CC BY-NC 4.0 with a scope preamble covering `apps/*/data`, `apps/*/assets`, `public/*.json` dataset snapshots, icons, and synthetic content | All covered content removed. File removed from `sim/` so no NC licence text ships; hash recorded in the purge manifest |
| `DISCLAIMER.md` | data provenance and takedown procedure for upstream's dataset | Removed with the data; hash in manifest |
| `mobilegym-rl/LICENSE` | Apache-2.0 | Directory removed (vendored training stack); hash in manifest |
| `mobilegym-rl/verl/LICENSE` | Apache-2.0 | Removed with the directory |
| `mobilegym-rl/verl/Notice.txt` | empty file | Removed with the directory |
| `mobilegym-rl/rllm/` | no licence file in tree; parent `pyproject.toml` declares an MIT classifier but points its licence field at the Apache-2.0 file | Removed with the directory. Inconsistency noted; nothing of it ships |
| `public/vendor/cytoscape*.js`, `dagre.min.js` | MIT (header in `cytoscape.min.js`; dagre and cytoscape-dagre are MIT upstream projects) | Kept; used by the navigation graph viewer |

The separate downloadable MobileGym dataset (CC BY-NC 4.0) was **never fetched** and must never be.

## What was removed, by reason

| Reason | Files | What |
|---|---|---|
| `unused-upstream-app` | 3,444 | 11 of 13 apps, code included. Brand-named, dead without their data |
| `unused-upstream-system-app` | 272 | 10 of 14 system apps: Browser, Calculator, Calculator2, Calendar, Compass, FileManager, Gallery, Notes, Settings, ThemeStore. Phone-vendor UI replicas the OS shell does not need |
| `vendored-training-stack` | 1,520 | `mobilegym-rl/` (rLLM + verl). Phase 7 uses our own `training/` |
| `nc-data` | 539 | `apps/*/data/`, `apps/*/assets/` for all 13 apps |
| `upstream-benchmark` | 239 | `bench_env/task/`, `bench_env/tests/` (MobileGym-Bench tasks for deleted apps) |
| `nc-public-asset` | 114 | `public/sdcard/`, `public/ime/`, `public/icons/` |
| `system-app-data` | 21 | content files under the kept system apps' `data/` and `assets/`; the Apache-2.0 `data/index.ts` loaders stay and read our empty stubs |
| `project-surface` | 26 | website, README images, agent config, upstream CI, READMEs, CONTRIBUTING |
| `dead-test` | 28 | tests importing a deleted app or the removed website |
| `brand-asset` | 4 | `public/logos/` (real bank and telecom logos) |
| `nc-licence-text` | 2 | `LICENSE-DATA`, `DISCLAIMER.md` |
| `unused-upstream-tooling` | 2 | IME and theme tooling for purged data |
| `replaced-by-workspace` | 1 | `package-lock.json` |
| `generated-artifact` | 1 | `public/tailwind.css` |

## Retained upstream apps (until sub-chunk 3.3.1)

`sim/apps/Ebay` and `sim/apps/TencentMeeting` are kept as **code-only structural reference**
for the app contract: manifest shape, navigation declaration, page wiring. Their `data/` and
`assets/` are gone; they will not run. **Sub-chunk 3.3.1 deletes both** once the Storefront
exists. Until then the 1.1.3 brand guard carries a dated waiver for these two paths.

## Kept system apps

`AnswerSheet` (bench protocol), `Clock` (launcher widget), `Contacts` and `Sms` (OS providers; SMS
flows are needed for checkout OTP tasks later). Their `data/` directories hold upstream's loader
code plus our empty stubs (`defaults.json`, `cities.json`, `phoneSettingsPages.generated.ts`).

## Our delta from upstream (commit B of 1.1.2 onward)

- `sim/package.json`: renamed `@rtl/sim`, joined the pnpm workspace, Map/Google Maps/puppeteer/eslint
  dependencies dropped. `package-lock.json` replaced by the workspace `pnpm-lock.yaml`.
- Every `mobilegym-data` reference removed. The dev CDN plugin in `vite.config.ts` now serves
  our provenance-tracked `content/` directory.
- `index.tsx` no longer preloads deleted apps. The four app-discovery globs (`os/data/appRegistry.tsx`,
  `os/PackageManagerService.ts`, `os/OSContext.tsx`, `os/providers/appProvidersBootstrap.ts`) exclude
  the two reference apps; `tsconfig.json` excludes them from typecheck.
- `system/Clock/navigation.types.ts` re-exports from `Sms` instead of the removed `Calendar` (identical file upstream).
- `sim/README.md` written by us; upstream READMEs removed.
- Later sub-chunks record their changes to `sim/os` and `sim/system` here.

## Sync procedure

1. `git -C refs/upstream/mobilegym fetch && git -C refs/upstream/mobilegym log --oneline 57bc275..origin/main`
2. Review upstream changes under `os/`, `system/`, `bench_env/env`, `scripts/`, `vite.config.ts`.
   Ignore everything the purge rules delete.
3. Apply relevant hunks to `sim/` by hand; upstream and `sim/` diverge too much for a merge.
4. Re-run `tools/licence/purge_fork.py --dry-run` against the new upstream commit to see whether
   the rules still classify every new path; extend `RULES` if not.
5. Update the fork-point line above only if the purge is re-run from a newer commit.
6. `make verify` and `uv run python tools/licence/scan.py --mode nc` must pass.
