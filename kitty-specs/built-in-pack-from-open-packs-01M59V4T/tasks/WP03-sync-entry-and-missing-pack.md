---
work_package_id: WP03
title: sync_packs script, make sync-packs, BuiltInPackMissing, gitignore
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-005
- FR-006
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: cef8a4216592dffbda69eb008fe0de908c094be5
created_at: '2026-10-19T12:39:38.469552+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
- T045
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/sync_packs.py
create_intent:
- scripts/sync_packs.py
- tests/scripts/test_sync_packs.py
- tests/charter_offering/test_built_in_pack_missing.py
- tests/charter_offering/conftest.py
execution_mode: code_change
model: sonnet
owned_files:
- scripts/sync_packs.py
- Makefile
- .gitignore
- src/charter/offering/pack_paths.py
- tests/scripts/test_sync_packs.py
- tests/charter_offering/test_built_in_pack_missing.py
- tests/charter_offering/conftest.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – sync_packs script, make sync-packs, BuiltInPackMissing, gitignore

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

Give developers and CI one entry point that syncs both packs, make `dev-setup` run it, and make a missing built-in tree fail with an error that names the fix.

Requirements: FR-001, FR-003, FR-005, FR-006.

## Context

- Contract `contracts/sync-cli.md`: `python scripts/sync_packs.py [--pack built-in|internal|all] [--offline] [--check]`.
- `Makefile:9-11` `dev-setup` runs `uv sync --frozen --all-extras` and `doctor skills --fix`; add `sync-packs` and call it from `dev-setup` (also add to `.PHONY` on L3).
- `src/charter/offering/pack_paths.py:153 built_in_root()` → `:219 _resolve_built_in()` → `kernel.paths.get_built_in_pack_root` (`src/kernel/paths.py:232`), translating `SiblingPathNotFound` to `PackRootNotFound`. Add `BuiltInPackMissing(PackRootNotFound)` so existing `except PackRootNotFound` callers (e.g. `pack_validator.py`) keep working (C-001).
- Only raise `BuiltInPackMissing` when the resolution reached the source checkout (a `packs/built-in.source.yaml` sibling exists) but the tree is absent; an installed wheel keeps today's behaviour.
- `built_in_root` keeps delegating to the kernel resolver and only translates the kernel miss into `BuiltInPackMissing`, with a `make sync-packs` hint (A4).
- `.gitignore`: add `/packs/built-in/` and `/packs/internal/`. Do NOT `git rm` the trees here (WP09). Note: gitignore does not untrack files, so the trees stay tracked until WP09.

Dependencies: Depends on WP02.

## Subtasks

### T011: Red tests for the script

- **Purpose**: Red tests for the script.
- **Steps**: `tests/scripts/test_sync_packs.py`: invoke `main([...])` with a fake pin pointing at a local bare repo (reuse the WP02 fixture module); assert exit codes and codes in stderr per the contract table, including `--check` → `PACK_TREE_STALE`.
- **Edge cases / notes**: Pass the repo root as a parameter so tests never touch the real `packs/`.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T012: Write `scripts/sync_packs.py`

- **Purpose**: Write `scripts/sync_packs.py`.
- **Steps**: Thin argparse wrapper: find `packs/*.source.yaml`, call `fetch_to_cache` + `place_pack` (or `check_pack` with `--check`), print one line per pack, exit 0/1.
- **Edge cases / notes**: No business logic here; it calls `charter.offering.packs.pack_fetch`. Must run with plain `python` after `uv sync`.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T013: Make targets

- **Purpose**: Make targets.
- **Steps**: Add `sync-packs: ## Fetch and verify packs/built-in and packs/internal` running `uv run --frozen python scripts/sync_packs.py --pack all`; make `dev-setup` call it after `uv sync`.
- **Edge cases / notes**: `make test-fast` itself does not sync; document that in the target help.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T014: `BuiltInPackMissing`

- **Purpose**: `BuiltInPackMissing`.
- **Steps**: Red test first in `test_built_in_pack_missing.py`: point `SPEC_KITTY_PACKS_ROOT`/a tmp repo layout at a root with a pin and no tree, assert the raised type and that the message contains `make sync-packs`. Then implement in `_resolve_built_in`.
- **Edge cases / notes**: Keep `PackRootNotFound` as the base type; check `test_built_in_location_authority.py` still passes.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T015: gitignore entries

- **Purpose**: gitignore entries.
- **Steps**: Add the two entries with a comment pointing at the pins and `make sync-packs`.
- **Edge cases / notes**: Verify `git check-ignore packs/built-in/x` reports the rule.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T045: Session-start guard in `tests/charter_offering/conftest.py`

- **Purpose**: A missing built-in pack must be loud, never a skip (A4).
- **Steps**: Add a session-scoped autouse fixture: at session start, if the built-in pack is missing, raise `BuiltInPackMissing` (message names `make sync-packs`). Red test: run with the tree absent and assert the error, not a skip.
- **Edge cases / notes**: Document that `make sync-packs` must run once per worktree (implement/review); WP08 carries this in the how-to.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `scripts/sync_packs.py`
- `Makefile`
- `.gitignore`
- `src/charter/offering/pack_paths.py`
- `tests/scripts/test_sync_packs.py`
- `tests/charter_offering/test_built_in_pack_missing.py`
- `tests/charter_offering/conftest.py`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/scripts/test_sync_packs.py -q
uv run --no-sync pytest tests/charter_offering/test_built_in_pack_missing.py -q
uv run --no-sync pytest tests/architectural/test_built_in_location_authority.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- `built_in_root` delegates to the kernel resolver and translates the kernel miss into `BuiltInPackMissing` with a `make sync-packs` hint.
- `tests/charter_offering/conftest.py` raises `BuiltInPackMissing` at session start when the pack is missing (never skip); a test proves it.
- Requirements FR-003, FR-005, FR-006, FR-001 demonstrably covered by a test or gate.

## Risks

Raising a new subtype in the wheel path would change consumer behaviour; restrict it to the source checkout.

## Reviewer guidance

Confirm the script holds no logic beyond argument handling and that the error message text matches the contract. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP03 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
