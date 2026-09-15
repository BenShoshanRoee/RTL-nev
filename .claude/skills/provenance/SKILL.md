---
name: provenance
description: Use when adding, changing or generating ANY file under content/ (catalogs, copy, images, fonts, distributions), or adding ANY new dependency (pnpm, uv, GitHub Action, Docker base image). Manifest entry, SHA-256, origin fields, brand check, licence allowlist.
---

# provenance — nothing ships untraced

## Any file under `content/`
1. **Manifest entry required** in `content/MANIFEST.json` before the file is committed.
   The build fails on an unlisted file. Never add a waiver to get past the audit.
2. Fields, all mandatory:
   - `path` (relative to `content/`), `sha256` of the file bytes
   - `origin`: one of `generated-image`, `generated-text`, `synthetic-data`, `font`, `survey-derived-distribution`, `hand-authored`
   - `generator`: tool + version/hash (ComfyUI model hash, Claude model id, script path + git SHA)
   - `prompt` or `prompt_sha256` (full prompt for text; hash acceptable for images if prompt file is stored)
   - `seed` (integer; the exact seed that reproduces it)
   - `licence`: ours (`proprietary`) or the asset's (`OFL-1.1` for fonts, must be on allowlist)
   - `created` (ISO date), `author` (operator, or script)
   - `brand_check`: result id from `tools/provenance/brand_check.py`
3. **Regenerate, don't edit.** If an asset is wrong, fix the generator or seed and regenerate,
   so the manifest still reproduces it. Hand edits break provenance.
4. **Brand check** every text asset against `tools/licence/brandlist.txt` and every image
   against `refs/brand-logos/` perceptual hashes. A hit is a build failure, not a warning.
5. **Fonts:** SIL OFL only, each in its own directory with its LICENSE file, listed in the
   manifest with the upstream URL and version.
6. Nothing derived from `refs/` (survey captures, screenshots, logos) is ever copied into
   `content/`. Distributions are aggregated statistics, never raw captures.
7. Run `make provenance` (or `python tools/provenance/audit.py`) and show the operator the
   command and the zero-finding output.

## Any new dependency
1. **Ask first.** State: what it does, why the existing stack cannot, size, licence.
2. Licence must be on the allowlist: MIT, Apache-2.0, BSD-2/3-Clause, ISC, SIL OFL-1.1,
   CC0-1.0, Unlicense. Anything else is a hard no unless the operator writes a waiver in
   `tools/licence/policy.yaml` with a reason.
3. Check transitive licences too: `pnpm licenses list` / `pip-licenses`. One GPL transitive
   dep fails the gate.
4. Pin: exact version in lockfile; GitHub Actions to commit SHA; Docker base image to digest.
5. Run `make licence` after adding. Show the command and clean output.

## Never
- Fetch the MobileGym data tarball or any `mobilegym-data/` path.
- Commit anything CC BY-NC, anything with a real retailer/bank/payment brand, or any
  asset without a manifest entry.
