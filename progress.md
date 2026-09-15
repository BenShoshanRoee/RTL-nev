# Progress

**Current sub-chunk:** 1.1.3 — Licence Firewall CI (not started)
**Last updated:** 2026-09-15 (1.1.2 complete)
**Phase:** 1 of 12

Rules for this file: update at the END of every sub-chunk, never at the start.
"Verified by" is the exact command the operator ran. Append to Decisions for every call
the operator did not explicitly approve. Append to Known debt for every cut corner, with a
payback trigger. Keep under 400 lines; archive completed phases to `docs/progress-archive/`.

## Completed
| Sub-chunk | Title | Date | Verified by | Notes |
|---|---|---|---|---|
| scaffold | CLAUDE.md, progress.md, skills, settings, tree | 2026-09-15 | `find . -name .gitkeep \| wc -l` = 76 | Pre-1.1.1. No implementation code. |
| 1.1.1-manual | Toolchain + GitHub repo (plan's 🔧 steps) | 2026-09-15 | `docker run --rm hello-world`; `gh auth status`; `git ls-remote --heads origin` | Node 25, pnpm 10, uv + Python 3.11.14, Docker 29.8, origin = github.com/BenShoshanRoee/RTL-nev |
| 1.1.1 | Monorepo Structure | 2026-09-15 | `git clone . <tmp> && make setup && make verify` (both exit 0); `make gates` | 6 TS packages + 2 Python packages, all stubs. Commit 557a125 on main, pushed. |
| 1.1.2 | MobileGym Fork & NC Purge | 2026-09-15 | `make verify` (incl. `make licence`); `make purge-audit`; `grep -ri mobilegym-data sim/ \| wc -l` = 0; `pnpm --filter @rtl/sim --fail-if-no-match build`; `curl -s -o /dev/null -w '%{http_code}' localhost:3000/` = 200 | Two commits: A = purged fork + audit records (f2ac336), B = workspace adaptation. Upstream 6,676 files: 463 kept, 6,213 removed, 5 replaced. sim/ is 7.7 MB. |
| plan-rev-1 | Nine plan corrections applied to `rtl-implementation-plan.md` | 2026-09-15 | see Decisions rows dated 2026-09-15 (plan-rev-1) | 34 edits, 67 sub-chunks unchanged in count |

## In progress
None. 1.1.3 has not begun.

## Blocked / awaiting manual step
| Sub-chunk | Blocking step | What I need from the operator |
|---|---|---|
| 1.1.2 | Push | Commit B is local only. Say "push" to publish both 1.1.2 commits. |
| 1.1.3 | 🔧 Brandlist | `tools/licence/brandlist.txt`: ~150 Israeli retail, bank and payment brands, Hebrew and English. The brand guard cannot be tested without it. |

## Operator queue (not blocking code, time-sensitive)
| Item | Sub-chunk | Why it can't wait | Status |
|---|---|---|---|
| Buyer pipeline tracker + target list | 11.1.1 | Relationships take a quarter to form; plan says start in the Phase 1 window | Not started |
| Entity, invoicing, accountant | 10.2.1 | Long lead time; buyers pay net 30–60 | Not started |
| Populate `brandlist.txt` (~150 Israeli retail/bank/payment brands, he+en) | 1.1.3 | Brand guard is a build gate from 1.1.3 onward | Not started |
| Read MobileGym licences in full before purge | 1.1.2 | Purge is a single auditable commit; must be right first time | Done 2026-09-15 |
| Open one trivial upstream PR to MobileGym (typo or doc fix) | 1.1.2 | Proves the contribution process before 11.2.4 relies on it | Not started |

## Decisions made
| Date | Decision | Reasoning | Sub-chunk |
|---|---|---|---|
| 2026-09-15 | `sim/os` and `sim/system` not pre-created in skeleton | They arrive with the MobileGym fork in 1.1.2; placeholders would collide with upstream content. | scaffold |
| 2026-09-15 | `refs/` created locally but fully gitignored (no tracked `.gitkeep`) | Plan says never shipped; a tracked placeholder inside an ignored tree is contradictory. | scaffold |
| 2026-09-15 | `git init` run locally, nothing committed | `.gitignore` and settings assume a repo. No remote, no commit, reversible. | scaffold |
| 2026-09-15 | Skills use `.claude/skills/<name>/SKILL.md` layout | Claude Code's skill discovery format. | scaffold |
| 2026-09-15 | (plan-rev-1 #1) Provenance bootstrap: 1.1.2 ships empty-but-valid `content/MANIFEST.json`; 1.1.3 defines minimal v1 schema (`schema_version`, `path`, `sha256`, `licence`) and enforces "unlisted file under content/ fails"; 4.1.1 ADDS fields, never redefines | 1.1.3's NC guard depended on a manifest that did not exist until Phase 4. Forward-compat rule keeps a v1 manifest valid forever. Operator-approved. | 1.1.2, 1.1.3, 4.1.1 |
| 2026-09-15 | (plan-rev-1 #2) 1.1.2 retains exactly two upstream apps as code-only structural reference; 3.3.1 deletes them, with an explicit acceptance criterion and `UPSTREAM.md` record | 1.1.2 cross-referenced 1.1.3 (the licence firewall) by mistake. Operator-approved. | 1.1.2, 3.3.1 |
| 2026-09-15 | (plan-rev-1 #3) Replace `tree -L 2` criterion with `make verify-tree`: sorted `find -type d` diffed against checked-in `tools/expected-tree.txt` | `tree -L 2` cannot verify a 4-deep tree and `tree` is not installed. No external dependency. Operator-approved. | 1.1.1 |
| 2026-09-15 | (plan-rev-1 #4) `Money = { minor: integer, currency: ISO-4217 }` with a per-currency exponent table; cross-currency arithmetic throws; KWD (3-decimal) test in 2.1.2. Type placed in `packages/core-semantic/src/money.ts` (2.1.1 Files) | Gulf currencies have 3 minor-unit decimals; "integer agorot" would force a core change in Phase 12. Placement in core-semantic is my call: rtl-primitives (3.1.2) needs the exponent table and must not import from domains/commerce. | 2.1.1, 2.1.2, 3.1.2 |
| 2026-09-15 | (plan-rev-1 #5) 2.2.1 defines the minimal task contract (`id`, `setup`, `goal_matchers`, `unchanged_subtrees`) in `bench/rtlenv/task/schema.py`; 2.2.4 extends with authoring fields, never redefines | Judge consumed fields the schema did not yet define. Option B chosen by operator. | 2.2.1, 2.2.4 |
| 2026-09-15 | (plan-rev-1 #6) Business docs live in a separate private repo; `docs/business/` in this repo is gitignored scratch only; plan paths `docs/business/…` kept for readability with a note in Appendix A | Operator decision. Operator moved the files. | Appendix A, Phases 10–12 |
| 2026-09-15 | (plan-rev-1 #7) Non-code operator items moved from "Blocked" to a new "Operator queue" section in this file | They do not block code; they are time-sensitive and were being lost in the Blocked table. Operator-specified format. | progress.md |
| 2026-09-15 | (plan-rev-1 #8) `observed_in` on pathology injectors is nullable at registration (3.2.1); 6.1.3 adds `tools/provenance/check_observed_in.py` in CI failing on any task-referenced injector with `observed_in: null` | 3.2.1 mandated a survey reference that 5.1.2 produces later. Same class as #1. Operator-specified. | 3.2.1, 6.1.3 |
| 2026-09-15 | Dependency batch approved by operator: typescript (Apache-2.0), vitest, eslint, dependency-cruiser, pytest, ruff (all MIT) | Needed by 1.1.1; asked once as a batch per ground rule 5. Anything beyond these six needs a fresh ask. | 1.1.1 |
| 2026-09-15 | Authoritative plan moved to tracked `docs/plan/rtl-implementation-plan.md` | Operator decision. Business docs stay in gitignored `docs/business/` scratch; canonical copies in the separate private repo. | scaffold |
| 2026-09-15 | Node runtime pinned to 24.21.0 LTS via `.npmrc` `use-node-version` and `.node-version`; `engines` set to `^22 \|\| ^24` | dependency-cruiser refuses to run on odd-numbered Node (25). pnpm downloads and uses the pinned version project-locally; operator's global Node is untouched. LTS pin is what CI (1.1.5) will use anyway. | 1.1.1 |
| 2026-09-15 | TypeScript pinned to the 5.x line (5.9.3), not 7.x | pnpm resolved `typescript` to 7.0.2, the native-compiler preview. dependency-cruiser cannot use its API and silently analysed nothing; the gate test only exposed this once it required a clean pass first. 5.x is the stable JS API every tool supports. | 1.1.1 |
| 2026-09-15 | Python build backend is `uv_build` (bench and rtl_commerce) | A backend is unavoidable for `uv sync` to install workspace members. `uv_build` ships from the uv project already approved; Apache-2.0/MIT. No new third party. | 1.1.1 |
| 2026-09-15 | eslint deferred to 1.1.4 despite being in the approved batch | Its only job is hosting the no-Math.random and no-physical-CSS rules written in 1.1.4 and 3.1.3. Installing it unused adds nothing. It needs a TS parser plugin; I will ask then. | 1.1.1 |
| 2026-09-15 | Every gate has a negative test that first requires a clean pass (`make gates`) | The first version of the depcruise gate test reported "caught" while depcruise was refusing to run at all. A negative test without a positive bracket is vacuous. Rule applies to every future gate. | 1.1.1 |
| 2026-09-15 | pytest runs with `--import-mode=importlib` | Two test files with the same basename in different packages collided under the default import mode. | 1.1.1 |
| 2026-09-15 | 1.1.2 commit structure: A = purged tree + audit records, B = workspace adaptation; the raw upstream tree was never committed | Plan wanted raw fork then purge; that leaves CC BY-NC bytes and real logos in history forever. Manifest hashes + upstream SHA are the audit reference instead. Operator-approved. | 1.1.2 |
| 2026-09-15 | Minimal system apps: kept AnswerSheet, Clock, Contacts, Sms; removed the other 10 | Confirmed plan said "keep all 14, stub loaders". Evidence after purge: 98 type errors, and the data was phone-vendor UI replicas (a 623-page Settings clone, MIUI phone settings). OS needs only Clock's preload and Contacts/Sms types; Sms is useful for OTP tasks. Reversible: every file is in the manifest and the local clone. Operator offered "minimal system" as an option. | 1.1.2 |
| 2026-09-15 | Retained reference apps (Ebay, TencentMeeting) are excluded from all four discovery globs and from typecheck | They have no data and must not be bundled; they exist only to be read. Deleted in 3.3.1. | 1.1.2 |
| 2026-09-15 | `purge_fork.py` never overwrites a file already in `sim/` and only removes a file at a purged path if its bytes are upstream's | First version overwrote 12 edited files and restored upstream `package.json`, which made `pnpm --filter @rtl/sim` match nothing and every check exit 0 vacuously. | 1.1.2 |
| 2026-09-15 | Every filtered pnpm call uses `--fail-if-no-match` | A filter that matches no project exits 0 having run nothing. Same class as the depcruise-on-Node-25 vacuity. | 1.1.2 |
| 2026-09-15 | `make licence` runs the minimal NC scan now and is part of `make verify`; `make purge-audit` is local-only | A real gate today beats a stub that exits 2. 1.1.3 extends the scan add-only. | 1.1.2 |
| 2026-09-15 | `scan.py` treats a file of ours at a purged path as "replaced" (fine) and only flags upstream bytes | Our `sim/README.md` and four data stubs live at paths upstream also had. | 1.1.2 |
| 2026-09-15 | Sim dependencies dropped: leaflet, both Google Maps packages, puppeteer, eslint, typescript-eslint, eslint-plugin-react-hooks | Map app deleted; puppeteer unused; eslint arrives with its rules in 1.1.4. Nine runtime + eight dev deps kept, all MIT/ISC/Apache-2.0. | 1.1.2 |
| 2026-09-15 | `verify-tree` enumerates directories from `git ls-files -co --exclude-standard`, not `find` | The operator's first run failed on an empty `sim/public/sdcard` the dev server creates at boot. Anything gitignored or empty is not part of the tree we ship, so git's view is the right source. Negative gate now plants a file, not just a directory. | 1.1.2 |
| 2026-09-15 | (plan-rev-1 #9) 5.2.3 renumbered 6.3.1 under new "Chunk 6.3: Gate 1 — Randomisation Validation", moved to the end of Phase 6; dependency set to 5.2.2 + 6.2.3; Phase 5/6 Outcome text, Appendix B/C/D updated; two "formerly 5.2.3" notes left as breadcrumbs | It depended on Chunk 6 and executed after it per Appendix C. Dependency on 6.2.3 (not 6.1.3) is my call: Appendix C places GATE 1 after 6.2.3 and the experiment needs calibrated tasks. | 6.3.1 |

## Reference material (gitignored, local only)
| What | Where | Pinned at | Notes |
|---|---|---|---|
| MobileGym upstream clone | `refs/upstream/mobilegym` | commit `57bc275accdb06eea3aee13880afdebbe80583d3` (2026-08-28) | Full history kept for future syncs. 636 MB incl. `.git`. `apps/` is 353 MB of mostly CC BY-NC data. 13 apps in repo; the separate dataset was NOT downloaded and never will be. `mobilegym-rl/rllm` ships no LICENSE file: record in `UPSTREAM.md` during 1.1.2. |

## Deviations from plan
| Sub-chunk | Planned | Actual | Why |
|---|---|---|---|
| 1.1.2 | Commit the raw fork, then purge in a second commit | Only the purged tree was committed | NC content must never enter history (see Decisions) |
| 1.1.2 | Keep `os/`, `bench_env/`, `scripts/`, `docs/` and the code of `apps/` and `system/` | Kept 4 of 14 system apps; removed `bench_env/task` and `bench_env/tests`, `mobilegym-rl/`, `web/` | Lean fork; everything removed is hashed in the manifest and retrievable from `refs/upstream` |

## Known debt
| Item | Sub-chunk | Why deferred | When we pay it back |
|---|---|---|---|
| Money type placement (core-semantic vs domain) not yet validated by the insurance stub | 2.1.1 | Stub does not exist yet | 2.1.3: if the stub cannot use `Money` without commerce vocabulary leaking, revisit |
| `make verify` does not include `provenance`; that target exits 2 with a message | 1.1.1 | Not implemented until 4.1.1 | 4.1.1 adds `provenance` to `verify` |
| Transitive build-time deps with licences off the allowlist: `lightningcss` (MPL-2.0), `caniuse-lite` (CC-BY-4.0) | 1.1.2 | Pulled in by vite/tailwind; not distributed in the artifact | 1.1.3: `policy.yaml` waivers with reason "build-time only", or replace |
| Brand names inside `sim/apps/Ebay`, `sim/apps/TencentMeeting`, and upstream docs under `sim/docs` | 1.1.2 | Reference apps are needed until 3.3.1; docs describe the platform | 1.1.3 waiver for the two apps; 3.3.1 deletes them; docs get a brand sweep in 1.1.3 |
| Kept system apps run on empty stubs (no alarms, cities, contacts, SMS settings) | 1.1.2 | Content arrives with Hebrew resources in Phase 3 | 3.3.1 or first task that needs SMS/Contacts content |
| `sim/eslint.config.js` references eslint packages that are not installed | 1.1.2 | Lint rules are written in 1.1.4 | 1.1.4 rewrites it |
| Launcher home-screen widgets render an error box: their theme XML lived in the purged dataset (`/cdn/themes/...`) | 1.1.2 | Boot criterion is "serves a page"; the launcher theme is replaced by our surface generator | 3.3.1 (storefront shell) at the latest; 5.2.2 owns the launcher theme |
| OS default locale is Chinese (`zh`) and system UI strings are Chinese | 1.1.2 | Locale plumbing is 3.1.x work | 3.1.3 sets `he` default with RTL layout |
| `tools/expected-tree.txt` was generated from the tree, then cross-checked against Appendix A by script | 1.1.1 | Chicken-and-egg on the first run | Any future directory change must edit `expected-tree.txt` deliberately; that is the point |
