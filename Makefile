SHELL := /bin/bash
.PHONY: setup verify verify-tree gates test test-js test-py lint provenance licence purge-audit sbom smoke release

## setup: install JS and Python workspaces from committed lockfiles
setup:
	pnpm install --frozen-lockfile
	uv sync --frozen

## verify: full local gate (provenance and licence join this target when implemented)
verify: verify-tree gates lint licence test

## verify-tree: directory tree must match tools/expected-tree.txt
verify-tree:
	@tools/verify_tree.sh

## gates: negative tests proving each gate actually rejects what it should
gates:
	@tools/test_depcruise_gate.sh
	@tools/test_verify_tree_gate.sh
	@tools/test_licence_gate.sh
	@tools/test_rng_gate.sh
	@tools/test_vocab_gate.sh

test: test-js test-py

## test-js: build first so workspace packages resolve to fresh dist (tests exercise the shipped shape)
test-js:
	pnpm -r build
	pnpm -r test

test-py:
	uv run pytest

## lint: build first (workspace packages resolve through dist), then boundaries, eslint, python lint
lint:
	pnpm -r build
	@tools/check_dist_importable.sh
	pnpm exec depcruise --config .dependency-cruiser.cjs packages
	pnpm exec eslint .
	uv run ruff check .

## sbom: CycloneDX 1.5 for both ecosystems, validated; CI uploads dist/sbom.cdx.json
sbom:
	uv run python tools/sbom/generate.py --output dist/sbom.cdx.json --validate

## smoke: the built simulator serves its page and the content root (needs pnpm -r build)
smoke:
	@tools/smoke.sh

provenance:
	@echo "make provenance: not implemented until sub-chunk 4.1.1 (minimal manifest check arrives in 1.1.3)"; exit 2

## licence: NC guard + dependency licences + brand guard. CI runs this exact command.
licence:
	uv run python tools/licence/scan.py --mode all

## purge-audit: local only (needs refs/upstream/mobilegym); manifest == upstream minus sim/
purge-audit:
	uv run python tools/licence/scan.py --mode purge-audit

## release: local dry run of release.yml (no push, no tag): wheel, SBOM, container image.
## The real release is tag-triggered: git tag vX.Y.Z && git push --tags
release:
	pnpm -r build
	uv build --package rtl-commerce --out-dir dist/wheels
	uv run python tools/sbom/generate.py --output dist/sbom.cdx.json --validate
	docker build --build-arg VERSION=0.0.0-local -t rtl-environments:local .
	@echo "release dry run OK: dist/wheels, dist/sbom.cdx.json, image rtl-environments:local"
