---
work_package_id: WP02
title: Test reader and golden repoint
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-008
- SC-002
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 2 - Consumers
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/pinned_service_assets.py
create_intent:
- tests/pinned_service_assets.py
- tests/contract/test_pinned_service_assets.py
execution_mode: code_change
model: ''
owned_files:
- tests/pinned_service_assets.py
- tests/contract/test_pinned_service_assets.py
- tests/contract/_mission_status_conformance.py
- tests/contract/test_mission_status_conformance.py
- tests/contract/_mission_status_artifact_goldens.py
- tests/contract/test_mission_status_artifact_goldens.py
- tests/glossary/test_torn_tail_repair_goldens.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`), then load `spec-kitty charter context --action implement`. Read `research/code-grounding.md` for the facts this WP relies on.

## Branch Strategy

- Planning/base branch: `issue-6915-events-service-cutover`; final merge target: `issue-6915-events-service-cutover`.
- Topology `single_branch`: no lane worktree. `lanes.json` holds one repo-root lane; work in the repository root checkout.
- Start with: `spec-kitty agent action implement WP02 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

One test-side reader of the pinned extras, failing closed; the mission-status conformance tests, the artifact goldens and the glossary torn-tail goldens read the pinned `conformance-fixtures` instead of `services/`. Requirements: FR-006, FR-008. Do this while `services/` still exists: the release fixtures are byte-identical to core's copies (grounding §0), so a green run proves the repoint.

## Subtasks

### T007 — `tests/pinned_service_assets.py`

- Load `scripts/sync_services.py` by path (as `tests/ci/test_sync_services.py` does; cache the module) and expose:
  - `REPO_ROOT`;
  - `pinned_extra(extra: str, *, service: str = "read-service") -> Path` → `extras_root(REPO_ROOT, service, extra)`; on `SyncServicesError` raise `pytest.fail(...)`-compatible error: call `pytest.fail(f"{exc}", pytrace=False)` so the failure names the code and the remedy. Never `pytest.skip`.
  - Convenience: `conformance_fixtures_root()`, `contract_bundle_dir(module)` (`<root>/bundle/<module>`), `contract_tools_dir()` (`<root>/contracts/tools`).
- Honour `XDG_CACHE_HOME` exactly as `default_cache_root()` does (the per-worker HOME isolation in `tests/conftest.py` may redirect HOME/XDG: check it!). If the root fixture isolates `XDG_CACHE_HOME`, the reader must resolve the cache from the real environment captured before isolation, or from `SPEC_KITTY_SERVICE_ASSET_DIR`. Find out first (`grep -n XDG_CACHE_HOME tests/conftest.py`), and pick the approach that keeps tests hermetic while reading the CI-fetched cache. Document the choice in `traces/design-decisions.md`.
- `tests/contract/test_pinned_service_assets.py`: (1) against an empty tmp cache the reader fails with `SERVICE_BINARY_MISSING` and `make sync-services` in the message (positive control: (2) with the real cache it returns a directory containing `conformance/manifest.json`).
- Red first: write the test, commit, then the module.

### T008 — Conformance

- `tests/contract/_mission_status_conformance.py:51-52`: `CONFORMANCE_DIR`, `LEAK_PATTERNS_FILE` are repo-relative paths; `test_mission_status_conformance.py:38, :117-119` copies both into a scratch dir at the same relative layout. Change the constants to resolve from `conformance_fixtures_root()` (`conformance/`, `leak-patterns.json`) and keep the scratch layout working (adjust the copy to use explicit source and destination paths). Read each use site before editing.
- The leak-pattern cross-check (`:606-629`) compares with `contracts/tools/leak_patterns.py`: load that tool from `contract_tools_dir()` (the loader is `tests/contract/_loader.py`). Update the `"source"` string accordingly.
- Docstrings: say the goldens come from the pinned `conformance-fixtures` asset of spec-kitty-events.

### T009 — Artifact goldens

- `_mission_status_artifact_goldens.py:40-42` → `conformance_fixtures_root() / "artifact-conformance"`.
- Remove the `--write` regeneration mode (the release is read-only; regeneration happens in spec-kitty-events against a pinned core SHA, ADR consequences). Keep the comparison.

### T010 — Torn-tail goldens

- `tests/glossary/test_torn_tail_repair_goldens.py:26` → `conformance_fixtures_root() / "event-log" / "torn-tail" / "repair-cases.json"`.
- Remove the `python -m …` rewrite path and its docstring paragraph; keep `CASES` and the live-Python comparison. The docstring states the file is spec-kitty-events' and is regenerated there.

## Validation

```bash
uv run --frozen pytest tests/contract/test_pinned_service_assets.py tests/contract/test_mission_status_conformance.py tests/contract/test_mission_status_artifact_goldens.py tests/glossary/test_torn_tail_repair_goldens.py -q
```
Plus ruff/format/mypy on the changed files. Then prove independence from `services/`: `git stash`-free check — temporarily `mv services /tmp/services.bak`, rerun, move it back (record the run).

## Definition of Done
- No changed file references `services/`.
- Removing the cached extras makes these tests fail with the remedy (proved by T007's test).

## Reviewer guidance
- The scratch layout of the conformance test still mirrors what the Python oracle expects.
- No skip path anywhere.
