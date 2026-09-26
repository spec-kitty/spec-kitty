---
work_package_id: WP01
title: reconciliation.py attribution — squash deletions (#5022) + commit-level exclusion (#5018)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
planning_base_branch: fix/terminus-reconciliation-attribution-integrity
merge_target_branch: fix/terminus-reconciliation-attribution-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-reconciliation-attribution-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-reconciliation-attribution-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-reconciliation-attribution-integrity-01M3D4RW
base_commit: bcb9725f57bd5edadd93599b3fbc34019baed510
created_at: '2026-09-25T21:10:50.283916+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - reconciliation attribution axes
history:
- at: '2026-09-25T21:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/terminus/test_repro_5022.py
- tests/terminus/test_repro_5018.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/reconciliation.py
- tests/terminus/test_repro_5022.py
- tests/terminus/test_repro_5018.py
- tests/merge/test_reconciliation.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5022'
- '#5018'
---

# Work Package Prompt: WP01 — reconciliation.py attribution (#5022 + #5018)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter before parsing the
rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

State which initialization/boundaries/directives you applied, then continue.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objective & Success Criteria

Fix two attribution defects in the `spec-kitty merge` pre-teardown reconciliation gate, both in `src/specify_cli/merge/reconciliation.py`:

1. **#5022 (P2, HIGHEST — data loss)**: the default-`squash` content axis skips deletions, so a canceled WP's deletion of a pre-existing file that no approved lane re-authors rides a carrier lane onto the target and lands at exit 0.
2. **#5018 (P2 — availability, fail-closed)**: a mixed approved+canceled write-scope lane is wrongly blocked under `--strategy merge`/`rebase` because exclusion is computed at LANE granularity.

**Success**: `test_repro_5022.py` and `test_repro_5018.py` are RED before the fixes and GREEN after (driven through the REAL `spec-kitty merge` CLI, no `_run_git`/subprocess mocking). Adversarial siblings hold. The 3-way `xfail(strict)` at `tests/merge/test_reconciliation.py` STILL xfails. `ruff`, `ruff format --check`, `mypy --strict` clean; complexity ≤ 15.

## Context (grounded — file:line at HEAD 1409dc827f)

- `_unattributable_content_squash` (`reconciliation.py:553-574`): `if status.startswith("D"): continue` at L567 — the deletion skip. `_window_has_non_bookkeeping_change` (L537-551) skips D at L546.
- `_final_authored_blobs` (`reconciliation.py:898-936`): walks an approved lane's first-parent spine newest→oldest, keeps the FINAL blob per path. At L932-935 a path whose newest touching commit deletes it makes `blob_id_at` raise → path marked seen, no blob → **this is exactly the authored-deletion signal**.
- `_collect_authored` (`reconciliation.py:939-972`): returns `(authored_shas, authored_patch_ids, authored_blobs)`.
- `_collect_excluded` (`reconciliation.py:849-873`): at L865 `if not any(wp in excluded_canceled_wp_ids for wp in lane.wp_ids): continue`; L868-872 adds ALL of a mixed lane's tip commits (+ patch-ids) to the excluded set — no approved-lane / commit-level narrowing.
- `_collect_approved_shas` (`reconciliation.py:829-846`) adds the same lane tips for the approved survivor; `_reachable_excluded` (L412-427) flags them reachable → FAIL.
- `build_approved_wp_set` calls `_collect_excluded` BEFORE `_collect_authored` — WP2 must THREAD the authored sets into `_collect_excluded` (params), not reorder into shared mutable state.
- `ApprovedWpCommitSet` fields: L230-302 (add `authored_deletions` beside `authored_blobs`, L281).
- Real-CLI harness: `tests/terminus/conftest.py` — `build_coord_mission`, `run_terminus`, `output_names_content_fail`, `blob_present_at`, `sha_reachable`. Study `tests/terminus/test_repro_4977.py` (excluded axis) and `test_repro_4981.py` for the mixed/canceled patterns.

Read `../data-model.md` and `../contracts/reconciliation-gate-contract.md` (scenarios S1-S4, M1-M4) before coding.

## Subtasks

### T001 — Red-first repro for #5022 (squash deletion data-loss)

**Purpose**: Prove, through the real CLI, that a canceled WP's deletion of a pre-existing product file ships under default squash today.

**Steps**:
1. Create `tests/terminus/test_repro_5022.py`, `@pytest.mark.regression` + issue-pin `#5022`, `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.
2. Using `build_coord_mission` (coord topology), build a mission where a **pre-existing** product file (e.g. `src/product/keep_me.py`) exists at the coord base. One lane carries an approved survivor WP and a canceled-with-provenance sibling WP; the canceled sibling's commit **deletes** `keep_me.py`; no approved lane re-authors it. Integrate the lane (carrier), so the squashed tree has the deletion.
3. Drive `spec-kitty merge` (default squash) through `run_terminus`.
4. Assert the DESIRED post-fix behavior: the gate FAILs (`output_names_content_fail` / non-zero exit) AND `keep_me.py` is still present on the target (`blob_present_at(repo, target, "src/product/keep_me.py")`). Today this is RED (the file is gone, exit 0) → mark `xfail(strict=True)` with reason referencing #5022 until T003, then remove the marker.

**Validation**: RED before T003 (assert it fails through the pre-existing entry point). Commit as the lane's FIRST commit.

### T002 — authored_deletions field + collector

**Purpose**: Give the squash axis an authority for legitimate approved deletions.

**Steps**:
1. Add `authored_deletions: frozenset[str] = frozenset()` to `ApprovedWpCommitSet` (near `authored_blobs`, L281); update the docstring.
2. Add `_final_authored_deletions(repo_root, first_parent_shas) -> set[str]` — walk the spine newest→oldest, record a path when its newest touching commit deletes it (i.e. `blob_id_at` raises for that path at that commit). Do NOT record a path that has a later (newer) present blob (delete-then-re-add ⇒ final state present). Reuse the seen-path walk shape of `_final_authored_blobs`; consider computing both in one pass to avoid a second spine walk.
3. Thread it: `_collect_authored` returns the deletions too; `build_approved_wp_set` sets `authored_deletions` on the claim.

**Validation**: `mypy --strict` clean; a focused unit test in `tests/merge/test_reconciliation.py` for `_final_authored_deletions` (add-then-delete ⇒ recorded; delete-then-re-add ⇒ not recorded).

### T003 — Attribute deletions in the squash content axis

**Purpose**: Close the #5022 data-loss escape.

**Steps**:
1. In `_unattributable_content_squash`, replace the blanket `if status.startswith("D"): continue` (L567) with: for a `D` path, it is attributable iff `path in claim.authored_deletions` OR `self._is_bookkeeping_path(path, claim)`; otherwise append it to the unattributable list (add an `unattributable_deletions` tuple to `Divergence`, or fold into the existing `unattributable_blobs` with a sentinel blob — prefer a dedicated `unattributable_deletions` field for honest rendering).
2. Decide `_window_has_non_bookkeeping_change` (L546): a `D` path with no authored-deletion authority is a real change for the vacuous-authorship REFUSE path — narrow the skip consistently (a bookkeeping/authored deletion is not content; an unattributable one is). Keep the vacuous path fail-closed.
3. Remove the `xfail` from T001 → it goes GREEN.
4. **Adversarial**: add sibling cases — a rename under `--no-renames` (delete+add) attributes both halves; a path deleted in the canceled sibling but re-authored/modified by another approved lane is attributable; a bookkeeping-path deletion PASSes.

**Validation**: T001 GREEN; adversarial siblings green; existing squash tests (S4 add/modify) unchanged.

### T004 — Red-first repro for #5018 (mixed lane false-FAIL)

**Purpose**: Prove a mixed approved+canceled write-scope lane false-FAILs under `merge`.

**Steps**:
1. Create `tests/terminus/test_repro_5018.py`, `@pytest.mark.regression` + `#5018`.
2. Build a coord mission with ONE write-scope lane holding an approved/done WP and a canceled-with-provenance sibling; the survivor's first-parent commits legitimately land. Drive `spec-kitty merge --strategy merge`.
3. Assert the DESIRED behavior: exit 0 / gate PASS (the survivor's commits are approved authorship). Today RED (FAIL + revert) → `xfail(strict=True)` referencing #5018 until T005.

**Validation**: RED before T005. Commit before T005's fix.

### T005 — Commit-level exclusion

**Purpose**: Attribute exclusion at commit granularity (C-001: granularity, not strictness).

**Steps**:
1. Thread `authored_shas` / `authored_patch_ids` into `_collect_excluded` (compute `_collect_authored` first in `build_approved_wp_set`, or pass the sets as params — keep collectors pure).
2. In `_collect_excluded`, for a mixed lane subtract the approved first-parent authored SHAs/patch-ids: `excluded_shas ← lane_tips − authored_shas`; `excluded_patch_ids ← lane_patch_ids − authored_patch_ids`. A fully-canceled lane (no approved WP) is unchanged (all tips excluded).
3. Remove T004's `xfail` → GREEN.
4. **Adversarial** (the #4977 safety net): a canceled commit smuggled via a carrier merge's SECOND parent (not on the survivor's first-parent spine) must STILL be excluded and FAIL when reachable; a cherry-picked canceled copy must still be patch-id caught; a fully-canceled lane fully excluded.

**Validation**: T004 GREEN; `test_repro_4977.py` and the excluded-axis tests still GREEN.

### T006 — Full axis test run + honest-red check

**Steps**:
1. `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/ tests/merge/test_reconciliation.py -q`.
2. Confirm the 3-way `test_squash_three_way_merge_resolution_is_unattributable` STILL reports `xfailed` (NOT xpassed/un-stricted). If it xpasses, you changed the disjoint-scope model — STOP and revert; that case is out of scope (C-003).
3. Record pass/fail counts for the PR *Tests run* section.

## Branch Strategy

Planning branch: `fix/terminus-reconciliation-attribution-integrity`. Final merge target: `fix/terminus-reconciliation-attribution-integrity` (the mission later opens a PR to `main`). Execution worktrees are allocated per computed lane from `lanes.json` — enter the resolved workspace, do not reconstruct it.

## Test Strategy (ATDD / red-first — mandatory)

Each defect lands its issue-pinned `@pytest.mark.regression` real-CLI repro RED through `spec-kitty merge` (committed FIRST), then the fix makes it GREEN. After the fix, a transitional `regression` repro that has become a stable unit test may be re-homed, but the two `test_repro_50XX.py` files stay as real-CLI functional repros. Targeted surface: `tests/terminus/`, `tests/merge/test_reconciliation.py`.

## Definition of Done

- FR-001..FR-005 satisfied; scenarios S1-S3, M1-M4 (contract) pass; S4 unchanged.
- `test_repro_5022.py`, `test_repro_5018.py` GREEN (were RED first); adversarial siblings GREEN.
- 3-way `xfail(strict)` still xfailing.
- `ruff check`, `ruff format --check`, `mypy --strict` clean, no new suppressions; complexity ≤ 15; new branches/helpers carry focused tests.

## Reviewer Guidance

- Verify red→green: each repro was RED on the base commit and GREEN on the final commit.
- Adversarial data-loss lens: confirm the exclusion narrowing does NOT let second-parent-smuggled canceled code ride an approved sibling (C-001 / #4977).
- Confirm no gate was weakened toward a false-PASS; the fixes are attribution-granularity only.
- Confirm the 3-way xfail is untouched and still strict.

## Risks

- **R1 (C-001)**: over-narrowing exclusion reopens #4977. Mitigation: subtract only first-parent-authored commits; adversarial 2nd-parent test.
- **R2 (C-003)**: deletion attribution accidentally un-stricts the 3-way xfail. Mitigation: T006 explicit check.
- **R3**: `_window_has_non_bookkeeping_change` skip left inconsistent with the axis. Mitigation: narrow both together, keep vacuous path fail-closed.
