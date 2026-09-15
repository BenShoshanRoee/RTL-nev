SHELL := /bin/bash
.PHONY: setup verify verify-tree gates test test-js test-py lint provenance licence purge-audit release

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

test: test-js test-py

test-js:
	pnpm -r test

test-py:
	uv run pytest

## lint: architecture boundaries, typecheck, python lint
lint:
	pnpm exec depcruise --config .dependency-cruiser.cjs packages
	pnpm exec eslint .
	pnpm -r typecheck
	uv run ruff check .

provenance:
	@echo "make provenance: not implemented until sub-chunk 4.1.1 (minimal manifest check arrives in 1.1.3)"; exit 2

## licence: NC guard + dependency licences + brand guard. CI runs this exact command.
licence:
	uv run python tools/licence/scan.py --mode all

## purge-audit: local only (needs refs/upstream/mobilegym); manifest == upstream minus sim/
purge-audit:
	uv run python tools/licence/scan.py --mode purge-audit

release:
	@echo "make release: not implemented until sub-chunk 1.1.5"; exit 2
