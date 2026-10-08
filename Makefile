.DEFAULT_GOAL := help

.PHONY: help dev-setup lint format-check format-check-files docs-lint typecheck test-fast test-full convergence-census ci-parity test-quality-scan

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev-setup: ## Sync deps and install all slash commands for configured agents
	uv sync --frozen --all-extras
	uv run --frozen spec-kitty doctor skills --fix

lint: ## Run ruff linter
	uv run --frozen ruff check src/

# Convenience only -- the enforced copy of this check lives in
# tests/architectural/test_ruff_format_enforcement.py (part of `make
# test-full`), so a red gate is never silent regardless of whether anyone
# runs this target locally (#558).
format-check: ## Run ruff formatter check on the whole repo (issue #473's gate)
	uv run --frozen ruff format --check .

# Per-file check that honors the [tool.ruff.format].exclude ratchet (#5301):
# an explicitly-passed path is checked even when excluded, unless
# --force-exclude is given. Usage: make format-check-files FILES="a.py b.py"
format-check-files: ## Run ruff formatter check on explicit paths, honoring the format-exclude ratchet
	uv run --frozen ruff format --check --force-exclude $(FILES)

docs-lint: ## Spell-check docs (typos + scoped US spelling) and check the changelog [Unreleased] style
	uv run --frozen python -m scripts.docs.check_spelling
	uv run --frozen python -m scripts.docs.check_changelog_style

convergence-census: ## Fetch upstream and report convergence dispositions
	git fetch old
	uv run --frozen python scripts/convergence/census_status.py

typecheck: ## Run targeted mypy strict type checking
	uv run --frozen mypy --strict \
	  src/specify_cli/runtime/agent_commands.py \
	  src/specify_cli/git/commit_helpers.py

ci-parity: ## Preview locally which CI gates/shards your diff selects (#2476 parity)
	uv run --frozen python scripts/ci/local_gate_parity.py

# Static first pass of the internal `test-suite-quality-assessment` procedure:
# ranks every test file for squad review and runs no tests. The scanner is the
# internal-pack asset `test-quality-scan` (same file `spec-kitty charter pack
# asset path test-quality-scan` resolves). Extra flags via SCAN_ARGS, e.g.
# SCAN_ARGS="--paths tests/status" or SCAN_ARGS="--since <rev>".
TEST_QUALITY_OUT ?= work/test-quality/$(shell date +%F)
test-quality-scan: ## Rank test files for a quality review (static; runs no tests)
	uv run --frozen python packs/internal/assets/test-quality-scan.py --out $(TEST_QUALITY_OUT) $(SCAN_ARGS)

# The subsystem directories an implementer's blast radius typically covers
# (see AGENTS.md "Test policy"). `make test-fast` is a baseline, not a
# substitute for running the tests of the modules your diff actually touches.
FAST_TIER_DIRS := tests/unit tests/status tests/cli tests/specify_cli/runtime tests/architectural/test_no_retired_subsystems.py

# Fast tier = pure-logic tests only; every slow tier is deselected by marker.
FAST_TIER_MARKERS = (fast or unit) and not slow and not e2e and not integration and not regression and not distribution and not live_adapter and not stress and not windows_ci and not platform_darwin

# Parallel-unsafe marker families (pytest.ini): `stress` spawns real
# multi-process/subprocess concurrency and `timing` measures wall-clock — both
# are corrupted by co-scheduled xdist workers, so they are deselected from the
# parallel pass below and get their own dedicated -n0 passes in the
# `test-full` target below.
PARALLEL_UNSAFE_MARKERS = not stress and not timing

test-fast: ## Run fast tier of the typical blast-radius dirs (target <2 min)
	env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest $(FAST_TIER_DIRS) \
	  -m "$(FAST_TIER_MARKERS)" -n auto --dist loadfile -p no:cacheprovider -q

# Keep make test-full green in under 30 minutes on main. Re-measure if a
# future change materially bloats the suite.
#
# Each test-full pass writes its failure, if any, to this marker instead of
# stopping the target: a red parallel pass must not skip the stress/timing
# passes, or a CI round-trip diagnosing red main gets signal on only one of
# the three families. The final recipe line aggregates.
TEST_FULL_STATUS := .test-full-status

test-full: ## Run everything: one parallel pass + serial marker passes
	@rm -f $(TEST_FULL_STATUS)
	env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/ \
	  -m "$(PARALLEL_UNSAFE_MARKERS)" -n auto --dist loadfile -p no:cacheprovider -q || echo parallel >> $(TEST_FULL_STATUS)
	# Serial passes: the two parallel-unsafe marker families run serially under
	# -n0. The per-test timeout that guards a hung fork/process from stalling a
	# lane indefinitely is no longer passed here: since #3143 it is set once, in
	# pytest.ini (`timeout = 240`, `timeout_method` unset -> signal on this POSIX
	# runner). The previously explicit `--timeout=240 --timeout-method=signal`
	# was byte-for-byte redundant with that default on Linux/macOS and actively
	# Windows-hostile (forcing the SIGALRM-only signal method where no SIGALRM
	# exists), so it was dropped in favour of the single authority. These passes
	# stay serial (-n0) for the stress/timing reasons above, not for the timeout.
	env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/ \
	  -m "stress and not windows_ci" -n0 -q || echo stress >> $(TEST_FULL_STATUS)
	env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/ \
	  -m timing -n0 -q || echo timing >> $(TEST_FULL_STATUS)
	@if [ -s $(TEST_FULL_STATUS) ]; then \
	  echo "test-full: FAILED passes: $$(tr '\n' ' ' < $(TEST_FULL_STATUS))"; \
	  rm -f $(TEST_FULL_STATUS); exit 1; fi
