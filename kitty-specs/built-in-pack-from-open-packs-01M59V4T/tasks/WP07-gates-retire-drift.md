---
work_package_id: WP07
title: Tracked-tree absence gate, retire drift gate, update parity and internal identity tests
dependencies:
- WP01
- WP06
requirement_refs:
- FR-001
- FR-012
- FR-013
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: 5e2384d769b00f757fd3c66232ae88ef3baaa9d3
created_at: '2026-10-19T12:51:36.723038+00:00'
subtasks:
- T030
- T031
- T032
- T033
- T049
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_pack_trees_untracked.py
create_intent:
- tests/architectural/test_pack_trees_untracked.py
- tests/architectural/test_no_pack_presence_skipif.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/architectural/test_pack_trees_untracked.py
- tests/architectural/test_built_in_drift_gate.py
- tests/cross_cutting/packaging/test_built_in_release_parity.py
- tests/charter_offering/test_internal_pack_identity.py
- tests/architectural/test_no_pack_presence_skipif.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP07 – Tracked-tree absence gate, retire drift gate, update parity and internal identity tests

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

Add the gate that fails if `packs/built-in` or `packs/internal` is tracked, retire the drift gate (#6421 and the drift-gate part of #6364), and align the parity and internal identity tests with the fetched trees.

Requirements: FR-001, FR-012, FR-013 (closes #6421; drift-gate part of #6364).

## Context

- `tests/architectural/test_built_in_drift_gate.py:48,57` copies the committed tree and drives `vendor --check`; delete the file.
- `tests/cross_cutting/packaging/test_built_in_release_parity.py:49,55` compares the wheel digest with the pin; switch to `load_pack_pin`/`verify_pack_pin` and keep it (it is the release-parity ratchet).
- `tests/charter_offering/test_internal_pack_identity.py:74 test_internal_pack_declares_no_pack_version` asserts `pack_version is None`; relax it to accept the canonical `1.0.0` from open-packs (DM 01M59YNJWKKHG6KJVBGF56K0PQ). L56 still asserts it loads as an org pack — that depends on the open-packs PR restoring `pack_level: org` (prerequisite noted in WP01).
- New gate (B4): checks `git ls-files`, authored red-first with `xfail(strict=True, reason='trees untracked in WP09')`; WP09 removes the marker in the same commit as `git rm --cached` (recorded as an allowed single out-of-map edit in WP09). `git ls-files packs/built-in packs/internal` must be empty. Original note: `git ls-files packs/built-in packs/internal` must be empty. It will be red until WP09; mark it `xfail(strict=True, reason=...)` here and WP09 removes the marker. Also assert both paths are matched by `git check-ignore`.

Dependencies: Depends on WP01, WP06.

## Subtasks

### T030: Tracked-tree absence gate

- **Purpose**: Tracked-tree absence gate.
- **Steps**: Write `test_pack_trees_untracked.py` (strict xfail until WP09) plus a passing gitignore assertion.
- **Edge cases / notes**: Run git with `cwd=repo root`; skip cleanly when not in a git checkout (sdist).
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T031: Retire the drift gate

- **Purpose**: Retire the drift gate.
- **Steps**: `git rm` nothing; just delete `tests/architectural/test_built_in_drift_gate.py` in the lane and note #6421/#6364 in the commit message.
- **Edge cases / notes**: Check no other test imports from it.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T032: Update release parity

- **Purpose**: Update release parity.
- **Steps**: Use the new pin API; keep both tests.
- **Edge cases / notes**: Run with the packaging marker, file-scoped.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T033: Relax internal identity

- **Purpose**: Relax internal identity.
- **Steps**: Assert `pack_version` equals the value in the open-packs PINNED tree (not None-tolerant); rename the test. Never relax `pack_level`.
- **Edge cases / notes**: Do not weaken the ULID and org-level assertions.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T049: No skipif keyed on pack presence

- **Purpose**: Missing packs must fail loudly, never skip (B4).
- **Steps**: Add `tests/architectural/test_no_pack_presence_skipif.py`: grep gate forbidding `skipif`/`skip` conditions keyed on pack presence (e.g. `packs/built-in` existence) in `tests/`. No `skipif` on missing `packs/built-in` anywhere in this WP's files (also in the T030 gate's non-git case: fail, do not skip, in a checkout).
- **Edge cases / notes**: Name the gate in the failure message.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `tests/architectural/test_pack_trees_untracked.py`
- `tests/architectural/test_built_in_drift_gate.py`
- `tests/cross_cutting/packaging/test_built_in_release_parity.py`
- `tests/charter_offering/test_internal_pack_identity.py`
- `tests/architectural/test_no_pack_presence_skipif.py`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/architectural/test_pack_trees_untracked.py -q
uv run --no-sync pytest tests/cross_cutting/packaging/test_built_in_release_parity.py -q
uv run --no-sync pytest tests/charter_offering/test_internal_pack_identity.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- The tracked-tree gate checks `git ls-files` and is authored red-first with `xfail(strict=True, reason='trees untracked in WP09')`; WP09 removes the marker in the same commit as `git rm --cached`.
- The pin gate `scripts/sync_packs.py --check` (run after a real fetch, WP04) is named as the replacement for EACH drift-gate assertion: list each retired assertion in the WP notes against it (digest match, commit resolvable, subtree present, tree not stale).
- No `skipif` keyed on missing `packs/built-in`; `test_no_pack_presence_skipif.py` is a grep gate enforcing this.
- Internal identity test asserts `pack_version` equals the value from the open-packs pinned tree (not None-tolerant) and never relaxes `pack_level`.
- The pack-manifest regen and DRG gates run against fetched trees (WP04).
- Requirements FR-001, FR-012, FR-013 demonstrably covered by a test or gate.

## Risks

Retiring a gate without the replacement pin gate (WP04) live would leave a window; WP04 lands the pin gate.

## Reviewer guidance

Confirm the xfail is strict and that the replacement gates cover every assertion the drift gate made. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP07 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
