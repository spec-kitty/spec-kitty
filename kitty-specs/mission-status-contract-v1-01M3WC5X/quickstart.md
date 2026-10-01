# Quickstart: running the checks locally

For implementers and reviewers of Mission `mission-status-contract-v1-01M3WC5X`. Use the checkout's own virtual environment (`.venv/bin/python`, `.venv/bin/ruff`, `.venv/bin/pytest`), never a bare `uv run`, which re-syncs and destroys a hand-built environment. Commands below assume the repository root as the working directory.

## What runs locally and what runs only in CI

| Step | Locally | CI only |
|---|---|---|
| Every `contracts/tools/*.py` Python check | yes | also in the contracts workflow |
| Reality check and every unit-test module in `tests/contract/` | yes | also in `tests-corpus` |
| Workflow guard tests in `tests/ci/` | yes | also in the `ci` module shard |
| Validate, bundle, lint, breaking-change diff, resolver parity, release dry run | only with a JDK, Gradle, vacuum and oasdiff installed through `install_tools.py` | the contracts workflow (the planning workstation has none of these tools) |

## Python checks over the contract

```bash
.venv/bin/python contracts/tools/layout_check.py --root contracts
.venv/bin/python contracts/tools/citation_check.py --root contracts
.venv/bin/python contracts/tools/provisional_check.py --root contracts
.venv/bin/python contracts/tools/example_check.py --root contracts
.venv/bin/python contracts/tools/event_mapping_check.py --root contracts
.venv/bin/python contracts/tools/enum_pin_check.py --root contracts
.venv/bin/python contracts/tools/leak_scan.py --root contracts
.venv/bin/python contracts/tools/structure_check.py --root contracts
.venv/bin/python contracts/tools/codeowners_check.py
.venv/bin/python contracts/tools/no_pytest_scan.py
```

Each prints a final `counts:` line; exit 0 is pass, 1 is a violation, 2 means the check could not do its job (read the code in the message). To see a check fail on purpose, point it at its planted fixtures with `--root contracts/tools/fixtures/<script>/<case>`.

## Reality check and unit tests (targeted files only)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_status_reality.py
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_contract_resolver.py tests/contract/test_leak_patterns.py tests/contract/test_layout_check.py
.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py
```

The last command proves the reality check is selected by the `corpus` marker expression the router's `tests-corpus` job uses. The reality check is read-only: it never calls `materialize` and hashes every tracked file under `kitty-specs/` before and after. Do not run the full architectural directory, an end-to-end suite or `make test-full` in mission work; run the named files only.

## Named gate files (run after every rebase and before hand-off)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_ci_corpus_trigger_completeness.py \
  tests/architectural/test_no_duplicate_suite_execution.py \
  tests/architectural/test_workflow_coherence.py \
  tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_ci_router_transcription_guards.py \
  tests/architectural/test_no_legacy_terminology.py \
  tests/ci/test_fork_guard.py tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py \
  tests/ci/test_prose_only.py tests/ci/test_ci_module_wiring.py \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py \
  tests/release
```

`tests/release` is the whole directory (15 test modules), not only the inventory freshness test: the regenerated inventory selects the `release` module shard, which runs all of it. A pull request that edits only `scripts/ci/` and `tests/ci/` would never run the freshness test, so regeneration is the author's job, not CI's.

Baseline at planning: only eight of those files were measured (265 passed, 1 skipped, 0 failed): the four architectural gates, the three `tests/ci/` fleet and fork files, and `tests/release/test_pinning_inventory_fresh.py`. The rest (the two router-derivation guards, terminology, prose-only, module wiring, the other `tests/release` modules, the docs files and the commands below) are measured at implement start, before the first change, so a red can be classed pre-existing or introduced. After editing `scripts/ci/fleet_verdict.py` or the two fleet test files, regenerate the derived inventory with `python3 scripts/ci/derive_pinning_inventory.py` (never by hand) and re-run the freshness test.

## Which jobs a path set selects (read-only)

```bash
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, ".")
from scripts.ci import gate_selection as g
print(g.select_gates(["contracts/mission-status/openapi.yaml"]))
print(g.select_modules(["tests/ci/test_fleet_verdict.py"]))
PY
```

This is the same single authority the router uses; with the `contracts/**` glob present a contracts-only path set selects `tests-corpus` and no module shard.

## Docs gates and the cutover guard (read-only)

This Mission edits a docs page and the changelog, so the always-on `docs-lint` and the routed `tests-docs` run in CI. The changelog entry goes to `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink; edit the target in place), in American spelling and the house entry shape.

```bash
.venv/bin/python -m scripts.docs.check_spelling
.venv/bin/python -m scripts.docs.check_changelog_style
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/docs/test_docs_index_freshness.py tests/docs/test_docs_index.py \
  tests/docs/test_docs_freshness_invariant.py tests/docs/test_changelog_style.py \
  tests/docs/test_check_spelling.py
.venv/bin/spec-kitty cutover-guard --base-ref origin/main
```

If a new `##` heading is added to `docs/development/reference/ci-gate-mechanics.md`, regenerate the committed index with `python -m scripts.docs.docs_index --write` (never by hand). Record the `cutover-guard` verdict at implement start and at PR prep.

## Lint and format (whole repository, as CI runs them)

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Checksum code needs a one-line `# noqa: TID251` with a file-integrity justification; the repository bans `hashlib.sha256` otherwise.

## Optional local coverage of the helper (non-gating, NFR-007)

```bash
.venv/bin/python -m pytest -q tests/contract/test_mission_status_payloads.py \
  --cov=tests.contract._mission_status_payloads --cov-branch --cov-fail-under=90
```

Paste the output in the PR body. No CI job measures this; it is local discipline.

## Reader authors: the reality check is not selected by a reader edit

A pull request that edits a status reader, or only `tests/contract/**`, selects no job that runs the reality check; the push-to-`main` run of `built-in-corpus-suite` is the net. Run it locally before pushing such a change: `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_status_reality.py`. The same one-line command goes in `contracts/README.md` beside the reader-author warning.
