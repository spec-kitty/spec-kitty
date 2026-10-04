---
work_package_id: WP04
title: Merge-site resolver (consolidate and dependency-lane merge)
dependencies:
- WP01
- WP03
requirement_refs:
- FR-007
- FR-012
- FR-013
- FR-009
- NFR-002
- C-003
- C-005
- SC-004
planning_base_branch: issue-5457-upgrade-project-global-state
merge_target_branch: issue-5457-upgrade-project-global-state
branch_strategy: Planning artifacts for this mission were generated on issue-5457-upgrade-project-global-state. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5457-upgrade-project-global-state unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-project-global-state-01M44538
base_commit: b33766f3b95528e03a4c0a1df73d9fcd159bcc60
created_at: '2026-10-04T21:01:22.475044+00:00'
subtasks:
- T013
- T014
- T015
- T016
- T017
phase: 'Phase 3 - Recovery: merge sites'
history:
- at: '2026-10-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/consolidation.py
create_intent:
- tests/lanes/test_primary_owned_merge_sites.py
- tests/lanes/test_worktree_allocator_primary_owned.py
- tests/integration/test_consolidate_upgraded_mission_recovery.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/lanes/worktree_allocator.py
- tests/lanes/test_primary_owned_merge_sites.py
- tests/lanes/test_worktree_allocator_primary_owned.py
- tests/integration/test_consolidate_upgraded_mission_recovery.py
- tests/architectural/test_destructive_op_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Merge-site resolver (consolidate and dependency-lane merge)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`):
`spec-kitty agent profile show python-pedro` and `spec-kitty charter context --action implement --json`.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Every feedback item is a TODO.

---

## Objectives & Success Criteria

A mission already in the **broken state** (a pre-fix upgrade committed a divergent `.kittify/metadata.yaml` and an identical `.gitattributes` line on every lane branch) must consolidate, and its dependent WPs must start, **with no manual edits**. Three git-merge sites gain one shared resolver that resolves a conflict on a primary-owned path (WP01's `is_primary_owned_path`) to that site's fixed side. Each of these merges runs in a worktree checked out on the receiving side, so the fixed side is always **stage 2 ("ours")**:

| Site | Code | "ours" is |
|------|------|-----------|
| Lane → mission merge (MERGE strategy) | `lanes/consolidation.py::_merge_branch_into`, the `else:` (MERGE) branch, ~:1261ff | the mission branch (the temporary worktree is detached at the target, which here is the mission branch) |
| Mission → target squash, plus `--strategy merge` | `_run_squash_merge` (~:973) and the same MERGE branch | the target branch |
| Dependency-lane merge | `lanes/worktree_allocator.py::_merge_dependency_lane_tips` (~:1590ff) | the dependent lane |

Every other conflict keeps today's behaviour byte-identically: `TARGET_BRANCH_CONTENT_CONFLICT` (`_SquashMergeConflict`), the `RuntimeError("Merge of … failed")` and `DependencyLaneMergeConflictError` (FR-009). `--strategy rebase` is out of scope and unchanged.

Spec refs: FR-007, FR-012, FR-013, FR-009, FR-010 (evidence), NFR-002, NFR-004, C-002, C-003, C-005; Story 2, Story 4 AS-1/2/3/5, Story 5 AS-2. Read `plan.md` (IC-03), `research.md` D3, `data-model.md`, and `research/squad-dispositions.md` #1, #2, #4 and #6.

## Context & Constraints

- **#4892 must hold**: no `-X theirs` / `-X ours`. The resolver may touch **only** unmerged paths for which `is_primary_owned_path` is True.
- **Squash ordering (disposition #6)**: `reconcile_derived_status_snapshot_conflicts` returns False when *any* unmerged path is not a `status.json`. So the order inside `_run_squash_merge` must be:
  1. `_resolve_planning_conflicts`;
  2. **`resolve_primary_owned_conflicts`**;
  3. `reconcile_derived_status_snapshot_conflicts`.
- **The MERGE branch today aborts on any non-zero merge.** Change it to:
  - resolve primary-owned conflicts;
  - **only if no unmerged path remains**, complete the merge with `git commit --no-edit`, and keep the existing pre/post HEAD no-op logic intact;
  - otherwise abort and raise exactly as today;
  - a non-zero merge with **no** unmerged paths (for example a failed driver) still raises as today.
- **Dependency merge**: call the resolver before `reconcile_derived_status_snapshot_conflicts`. If the index is then clean, commit `--no-edit` and `continue`. Otherwise fall through to the existing status reconcile, then to the existing atomic fail-closed path. Do **not** change the existing `reset --hard pre_loop_ref` behaviour (C-003 forbids adding destructive ops; this one is pre-existing and stays).
- **C-005**: do not modify `src/specify_cli/cli/commands/implement.py`. You reach the dependency merge through the CLI in tests only.
- No module-level filename list in `lanes/consolidation.py` or `worktree_allocator.py` (`test_exemption_registry_ratchet.py`).
- `test_merge_pipeline_ratchets.py`: every subprocess `env` must go through `_make_merge_env()` / the caller's `env`. Respect it.
- `test_destructive_op_routing.py`: if your resolver uses `git rm`, check that the gate accepts it. Use `git rm --cached` plus a path-scoped working-file removal only if the gate demands it.

## Branch Strategy

- **Strategy**: lanes · **Planning base branch**: `issue-5457-upgrade-project-global-state` · **Merge target branch**: `issue-5457-upgrade-project-global-state`.

## Subtasks & Detailed Guidance

### Subtask T013 – Red: real-CLI `consolidate` on broken-state fixtures

- **Purpose**: pin Story 4 AS-1, AS-2 and AS-3 and Story 2's recovery through the pre-existing entry point, `spec-kitty consolidate`.
- **Steps** (`tests/integration/test_consolidate_upgraded_mission_recovery.py`, real CLI via `run_cli`, fixtures from WP01):
  - **AS-1**:
    - A `lanes` mission with two approved lanes, in the broken state via `commit_broken_upgrade_state`, with the **lane worktrees present**.
    - Run `consolidate --mission <slug>`.
    - Expect exit 0, both lanes' files on the target, the target's `metadata.yaml` blob equal to its pre-consolidate blob, and the `.gitattributes` line present exactly once.
    - Today it fails (stale refusal, or after WP03, the uncoded lane → mission merge failure).
  - **AS-2**: the same, but with the **lane worktrees removed** (`git worktree remove`), so consolidate's auto-rebase cannot run.
  - **AS-3**:
    - One lane in the broken state, squash into a non-primary target `work`.
    - Also craft a both-sides `status.json` divergence in the same mission, so that the squash sees a mixed conflict set.
    - Expect exit 0 and no `TARGET_BRANCH_CONTENT_CONFLICT`.
  - Confirm all three are RED on the WP base (WP01 + WP03 merged), and commit them alone.

### Subtask T014 – `resolve_primary_owned_conflicts(worktree, env) -> list[str]`

- **Location**: `lanes/consolidation.py`, next to `reconcile_derived_status_snapshot_conflicts` (which `worktree_allocator` already imports).
- **Behaviour**:
  - For each `rel` in `_unmerged_paths(worktree, env)` where `is_primary_owned_path(rel)`:
    - **stage 2 present** (`git cat-file -e :2:<rel>`, or `git ls-files -u` parsing): `git checkout --ours -- <rel>`, then `git add -- <rel>`;
    - **stage 2 absent** (ours deleted it): `git rm -q -- <rel>`, path-scoped.
  - Return the resolved paths. Raise nothing on a non-primary path; leave it unmerged.
  - Make it idempotent and deterministic (NFR-004).
- **Unit tests** in `tests/lanes/test_primary_owned_merge_sites.py`, using real git in `tmp_path`:
  - a both-modified conflict resolves to ours;
  - a modify/delete conflict with ours deleted removes the path;
  - a delete/modify conflict with ours modified keeps ours;
  - a mixed set (primary-owned plus `src/x.py`) resolves only the primary-owned path and leaves `src/x.py` unmerged;
  - a non-conflicted tree is a no-op.
- Commit the helper together with its tests. They are the helper's own red→green: write the tests first.

### Subtask T015 – Wire it into the squash and the MERGE branch

- **`_run_squash_merge`**: insert the call between the planning resolution and the status reconcile, per the ordering above. If it resolved something and nothing is left, return `True` (a reconciliation was needed), which matches the planning-resolution semantics, so a resulting no-op is adjudicated by the existing zero-diff path.
- **MERGE branch of `_merge_branch_into`**: per the constraints above. Keep the pre/post HEAD no-op detection. A resolved commit is a real change.
- T013 AS-1, AS-2 and AS-3 go green. Commit: `fix(consolidate): resolve primary-owned bookkeeping at lane and target merges (#5457)`.

### Subtask T016 – Dependency-lane merge (red, then wire)

- **Red**: `tests/lanes/test_worktree_allocator_primary_owned.py`:
  - set up a mission where WP02 depends on WP01 in another lane;
  - give the WP01 lane branch (and the base) divergent `metadata.yaml` commits via the WP01 fixture;
  - run `spec-kitty implement WP02 --mission <slug>` (real CLI) or `spec-kitty agent action implement`, whichever the repo's tests use for dependency-lane allocation (see `tests/lanes/test_worktree_allocator*.py` for the established entry point);
  - today it raises `DependencyLaneMergeConflictError`. Commit the red test alone.
- **Wire**: in `_merge_dependency_lane_tips`, on a non-zero merge:
  1. `resolve_primary_owned_conflicts(worktree_path, env)`;
  2. if `_unmerged_paths` is empty, commit `--no-edit` and `continue`;
  3. otherwise run the existing `reconcile_derived_status_snapshot_conflicts`, then the existing fail-closed path.

  Import the helper through the existing import line for `reconcile_derived_status_snapshot_conflicts`. Green.

### Subtask T017 – Controls and the half-by-half proof

- **Story 5 AS-2**: in the same AS-3 fixture, also make a source file (`src/shared.py`) conflict between lane and target. `TARGET_BRANCH_CONTENT_CONFLICT` is still raised, and its rendered text and `conflicting_path` are byte-identical to the pre-change output. Capture the pre-change output from the WP base to compare.
- **Dependency control**: a source conflict in the dependency lane still raises `DependencyLaneMergeConflictError`.
- **MERGE-branch control**: a lane → mission source conflict still raises `RuntimeError("Merge of …")`.
- **Half-by-half proof** (tactic `acceptance-criteria-non-vacuity`):
  - revert the squash wiring → AS-3 goes red;
  - revert the MERGE wiring → AS-1 or AS-2 goes red;
  - revert the dependency wiring → T016 goes red.

  Record the results in the Activity Log.

## Post-tasks squad folds (binding)

- **Keep every destructive literal where it is.** `tests/architectural/test_destructive_op_routing.py` pins `merge --abort` / `reset --hard` by function and ordinal (`_merge_branch_into`, `_merge_dependency_lane_tips`). Extract only the *resolve-and-commit* step into a helper. Leave every abort and reset call literally in its current function and order. If a re-pin is genuinely unavoidable, edit only that pin (you now own the file) and justify it in the commit body.
- **No raw `ls-files` / `ls-tree`.** `_unmerged_paths` already uses `changed_paths(diff_filter="U")`. For stage presence use `kernel.git.listing.index_entries(..., tags/stages)` if it exposes stages; otherwise use `git cat-file -e :2:<path>`, which is not a path-listing argv. Run `tests/architectural/test_git_path_listing_owner.py`.
- **FR-007's `--strategy merge` mission → target leg**: add one targeted test of `_merge_branch_into(..., strategy=MergeStrategy.MERGE)` toward a target branch with a divergent `metadata.yaml`: red before, green after.
- **The dependency-lane conflict shape** (T016): a conflict needs the dependent side to have changed `metadata.yaml` too. That happens on the reuse path, or when the lane base carries an upgrade commit. Build it with a hand-written `lanes.json` (`depends_on_lanes`) via the WP01 knob. `finalize-tasks` may never produce cross-lane dependencies for tiny fixtures.
- **Production-path proof of WP03** (because AS-1 can be healed by WP05's auto-rebase): in T017, run **AS-2** (lane worktrees removed) through the CLI and show that reverting WP03's T010 turns it red, and reverting T011 turns it red. Also run the **Story 5 AS-1** control through the CLI: a different `.gitattributes` content stays a stale refusal, byte-identical.
- **Red tests assert the exact defect text** (`Merge of … failed` naming the lane, the stale refusal, or `TARGET_BRANCH_CONTENT_CONFLICT` with `conflicting_path: .kittify/metadata.yaml`), not just a non-zero exit.
- **Gate-file rights**: if a named architectural gate goes red because of a *legitimate* change, you may edit **only** that gate's own pin or allowlist entry. Name the file in the commit body with a one-line justification, and the reviewer re-checks it. Never touch `dead_symbol_allowlist.yaml` or `_git_path_listing_census.py`, and never add a new allowlist (C-007).

## Test Strategy

- `uv run --frozen pytest tests/lanes/test_primary_owned_merge_sites.py tests/lanes/test_worktree_allocator_primary_owned.py tests/integration/test_consolidate_upgraded_mission_recovery.py tests/lanes/test_merge.py tests/lanes/test_merge_policy.py tests/lanes/test_planning_merge_conflict_paths.py tests/lanes/test_worktree_allocator*.py -q`
- `uv run --frozen pytest tests/consolidation/ -q -x` (the owning subsystem directory: fast tier, recording the counts; classify any baseline red per the CLAUDE.md gotcha).
- Gates: `tests/architectural/test_exemption_registry_ratchet.py`, `test_merge_pipeline_ratchets.py`, `test_destructive_op_routing.py`, `test_merge_reconciliation_class_guard.py`, `test_no_dead_symbols.py`.
- Run `ruff check`, `ruff format --check --force-exclude` and `mypy` on the changed files. Complexity ≤ 15: the MERGE branch is inside a long function, so if needed extract `_complete_merge_after_primary_owned_resolution(...)` as a helper (with tests) rather than growing it.

## Risks & Mitigations

- **Masking a genuine conflict**: the resolver checks `is_primary_owned_path` per path, and the controls prove that genuine conflicts still refuse.
- **The reconciliation gate** (`consolidation/reconciliation.py::_is_bookkeeping` treats `.kittify/` as bookkeeping) must stay green on the presence and attribution axes. The AS-1 and AS-3 CLI tests reach the gate; check their output.
- **Dry-run preview** (`preview_mission_target_integration`) calls `_run_squash_merge`, so the forecast becomes consistent automatically. Add one assertion that `consolidate --dry-run` on the AS-3 fixture no longer forecasts the conflict.

## Review Guidance

- The red CLI tests are committed first and were red on WP01 + WP03.
- The resolver touches only primary-owned paths, and the controls are byte-identical.
- The squash ordering is correct, and the mixed `status.json` case is covered.
- `implement.py` is untouched; `--strategy rebase` is untouched.

## Activity Log

- 2026-10-04T19:40:00Z – system – Prompt generated via /spec-kitty.tasks
