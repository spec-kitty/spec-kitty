---
work_package_id: WP05
title: Auto-rebase managed-artifact rule
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-009
- SC-004
planning_base_branch: issue-5457-upgrade-project-global-state
merge_target_branch: issue-5457-upgrade-project-global-state
branch_strategy: Planning artifacts for this mission were generated on issue-5457-upgrade-project-global-state. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5457-upgrade-project-global-state unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-project-global-state-01M44538
base_commit: b33766f3b95528e03a4c0a1df73d9fcd159bcc60
created_at: '2026-10-04T20:31:25.092917+00:00'
subtasks:
- T018
- T019
- T020
- T021
phase: 'Phase 3 - Recovery: lane sync'
history:
- at: '2026-10-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/auto_rebase.py
create_intent:
- tests/lanes/test_auto_rebase_primary_owned.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/auto_rebase.py
- tests/lanes/test_auto_rebase_primary_owned.py
- tests/integration/test_lane_lifecycle_sync.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Auto-rebase managed-artifact rule

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`):
`spec-kitty agent profile show python-pedro` and `spec-kitty charter context --action implement --json`.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Every feedback item is a TODO.

---

## Objectives & Success Criteria

On a coordination mission already in the broken state, the lane sync that runs after every coordination lifecycle commit refuses today. The call chain is `agent action review` / implement-resume → `lanes/lifecycle_sync.py::sync_lane_after_coordination_commit` → `lanes/auto_rebase.py::attempt_auto_rebase`, which runs `git merge <coordination branch>` inside the lane worktree. Today that ends in `LANE_AUTO_REBASE_FAILED: no classifier rule matched …/.kittify/metadata.yaml`.

After this WP, a conflict on a primary-owned path (WP01's `is_primary_owned_path`) resolves to **stage 3 ("theirs")**: the incoming coordination or mission branch, which is closer to the primary branch. The resolution runs under a named rule, `R-PRIMARY-OWNED-BOOKKEEPING`, in auto-rebase's closed, whole-file **managed-artifact arm** (`_resolve_managed_artifact_conflicts`, ~:435-473), next to `R-COORDINATION-ARTIFACT-THEIRS`. The rule id appears in the auto-rebase audit commit message. Consolidate's own auto-rebase of a stale lane uses the same function, so it benefits too.

Spec refs: FR-008, FR-009, C-002; Story 3, Story 4 AS-4, Story 5 AS-3. Read `plan.md` (IC-04), `research.md` D4, and `research/squad-dispositions.md` #5.

## Context & Constraints

- **Not** a new entry in `consolidation/conflict_classifier.RULES`. That list is per-hunk and cannot express a whole-file or modify/delete conflict (ADR `2026-05-14-1`; WP06 amends it).
- Reuse `_resolve_take_theirs`. It already handles a stage-3 write through the sparse-aware `_stage_sparse` and a deletion through `_remove_sparse`. A coordination lane worktree has a sparse checkout, so use those helpers and never raw `git add`/`git rm`.
- No module-level filename list in `auto_rebase.py` (`test_exemption_registry_ratchet.py`). Call the WP01 predicate.
- `auto_rebase.py` deliberately does **not** seed `.git/info/attributes` (the #2709/#2711 note at ~:965). Do not change that.

## Branch Strategy

- **Strategy**: lanes · **Planning base branch**: `issue-5457-upgrade-project-global-state` · **Merge target branch**: `issue-5457-upgrade-project-global-state`.

## Subtasks & Detailed Guidance

### Subtask T018 – Tidy-first: parametrise the `_resolve_take_theirs` rule id

- Add a keyword-only `rule_id: str = RULE_ID_COORDINATION_ARTIFACT` parameter, and use it in the classification and every halt message. Existing callers stay unchanged.
- This is behaviour-preserving: run `tests/lanes/test_auto_rebase*.py` and expect it green and unchanged.
- Commit it alone, **before** the red test: `refactor(auto-rebase): parametrise take-theirs rule id (tidy-first, #5457)`.

### Subtask T019 – Red test (Story 4 AS-4 / Story 3)

- **Fixture**: a `lanes_with_coord` mission with a coordination worktree and a lane worktree (reuse `tests/integration/test_lane_lifecycle_sync.py::_init_repo` or the WP01 builders). Commit a divergent `.kittify/metadata.yaml` on the coordination branch and on the lane branch, with WP01's `commit_broken_upgrade_state`.
- **Entry point**: make a coordination lifecycle commit, then call `sync_lane_after_coordination_commit(...)`, the production function the `agent action review` / `implement` paths call (`workflow_executor`). Better still, if feasible with the fixture: run `spec-kitty agent action review <WP>` through `run_cli` (grounding Appendix A, Path C).
- Today it fails with `LANE_AUTO_REBASE_FAILED … no classifier rule matched …/.kittify/metadata.yaml`. Assert that after the fix:
  - the sync succeeds;
  - the lane's `metadata.yaml` equals the coordination branch's blob;
  - the auto-rebase commit message names `R-PRIMARY-OWNED-BOOKKEEPING`.
- Put it in `tests/integration/test_lane_lifecycle_sync.py` (the extended existing module) and/or `tests/lanes/test_auto_rebase_primary_owned.py`. Commit the red test alone.

### Subtask T020 – Implement the managed-arm branch

- Add the module constant `RULE_ID_PRIMARY_OWNED = "R-PRIMARY-OWNED-BOOKKEEPING"` next to the other rule ids.
- In `_resolve_managed_artifact_conflicts`, add `elif is_primary_owned_path(rel_path): classification, halt_reason = _resolve_take_theirs(file_path, worktree, rule_id=RULE_ID_PRIMARY_OWNED)`. Place it after the status-event and status-json branches, before `_is_coordination_owned_artifact` / `else`. Order does not matter for correctness, since the predicates are disjoint, but keep the status handling first.
- Check that a modify/delete conflict on `metadata.yaml` reaches this arm before the "no conflict markers" check in `_process_conflicted_file`. It should, because the managed arm runs first; verify it in a test.
- T019 goes green. Commit: `fix(auto-rebase): resolve primary-owned bookkeeping to the coordination side (#5457)`.

### Subtask T021 – Controls [P]

- **Same fixture, with a source file** (`src/shared.txt`, as in the existing lifecycle-sync conflict test) conflicting as well: the sync still refuses with `LANE_AUTO_REBASE_FAILED` and "no classifier rule matched src/shared.txt", byte-identical to today.
- **Modify/delete**: the coordination side deleted `metadata.yaml` and the lane modified it, so stage 3 is absent. The path is removed in the lane, under the rule id.
- Keep `tests/lanes/test_auto_rebase_managed_artifact_recognition.py` green. If that module enumerates the managed kinds, extend its expectations to the new rule (it is in the boy-scout scope only if it is in your owned files; otherwise note it and let the reviewer decide).

## Post-tasks squad folds (binding)

- **The coordination worktree must be the product-materialised sparse checkout** (WP01 fixture), so that `_stage_sparse` / `_remove_sparse` are really exercised.
- **No raw `ls-files` / `ls-tree`** (`tests/architectural/test_git_path_listing_owner.py`). Use the existing `_git_show_stage` helper for stage reads.
- If `tests/lanes/test_auto_rebase_managed_artifact_recognition.py` enumerates the managed kinds and must learn the new rule, you may edit it. It is a direct test of the arm you change. Name it in the commit body.
- **Gate-file rights**: if a named architectural gate goes red because of a *legitimate* change, you may edit **only** that gate's own pin or allowlist entry. Name the file in the commit body with a one-line justification, and the reviewer re-checks it. Never touch `dead_symbol_allowlist.yaml` or `_git_path_listing_census.py`, and never add a new allowlist (C-007).

## Test Strategy

- `uv run --frozen pytest tests/lanes/test_auto_rebase_additive.py tests/lanes/test_auto_rebase_managed_artifact_recognition.py tests/lanes/test_auto_rebase_primary_owned.py tests/integration/test_lane_lifecycle_sync.py tests/lanes/test_lane_consumers_divergent.py tests/consolidation/test_conflict_classifier.py -q`
- Gates: `tests/architectural/test_exemption_registry_ratchet.py`, `test_destructive_op_routing.py`, `test_no_dead_symbols.py`.
- Run `ruff check`, `ruff format --check --force-exclude` and `mypy` on the changed files; `make test-fast`.

## Risks & Mitigations

- **Sparse-checkout lanes**: always use `_stage_sparse` / `_remove_sparse`.
- **Rule-id drift**: the audit message is tested.

## Review Guidance

- The tidy-first commit is behaviour-preserving and comes before the red commit.
- The rule is in the managed arm, not in `RULES`.
- The control proves that genuine conflicts still refuse with the same text.

## Activity Log

- 2026-10-04T19:40:00Z – system – Prompt generated via /spec-kitty.tasks
