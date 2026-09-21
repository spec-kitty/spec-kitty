---
work_package_id: WP03
title: Consumer detection
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
- NFR-003
- NFR-004
planning_base_branch: fix/finalize-repin-orphaned-planning-commit
merge_target_branch: fix/finalize-repin-orphaned-planning-commit
branch_strategy: Planning artifacts for this mission were generated on fix/finalize-repin-orphaned-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/finalize-repin-orphaned-planning-commit unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
- T017
phase: Phase 1 - Implementation
history:
- timestamp: '2026-09-21T00:00:00Z'
  agent: system
  action: Prompt generated via tasks phase authoring
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_issue_4827_allocator_orphan_pin.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/lanes/test_issue_4827_allocator_orphan_pin.py
- tests/lanes/test_lane_base_common_ancestor.py
- tests/lanes/test_worktree_allocator_atomicity.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match.

---

## Objective

Make every recorded-pin CONSUMER recognise an orphaned `planning_commit_sha` and name the finalize re-pin recovery — instead of a generic merge-conflict dead-end, a silently-wrong review diff against a dead base, or a bare claim refusal. Detection is centralized in the shared `_merge_recorded_planning_commit` helper so no call site is missed. finalize stays the sole WRITER (C-001); this WP only DETECTS. Issue #4827; research.md D5/D6; invariant-lens Findings 1 & 2.

## Context

Consumers of `LanesManifest.planning_commit_sha` (all READ-only here):
- `worktree_allocator.py::_merge_recorded_planning_commit` (~L579, called at :419/:482/:562) — no-ops when the pin is an ancestor of the **lane HEAD**, else merges; an orphaned pin falls through to `git merge <orphan>` → generic `PlanningCommitMergeConflictError` (~L680). **C-006: the existing lane-HEAD no-op gate is a different question and must be preserved** (a fresh coord lane legitimately has no common ancestor with the pin, #2993). Layer the orphan check (keyed off TARGET-TIP reachability via WP01) BEFORE/around the merge, not in place of the lane-HEAD gate.
- `implement_support.py:352` — a SECOND call of `_merge_recorded_planning_commit` (reconcile path); covered automatically if detection lives in the shared helper.
- `implement_support.py:497` `check_claim_ancestry` — `_is_git_ancestor(workspace, pin, head)`; an orphan lands `"recorded planning commit <sha>"` in `missing_refs` with no recovery hint.
- `tasks_move_task.py:697` `_mt_resolve_owned_review_base` — `git rev-parse --verify <sha>^{commit}` SUCCEEDS on an orphan (object present) → review diff silently computed against a DEAD base (correctness bug).

**Brownfield note:** `_merge_recorded_planning_commit` takes no target-branch argument today — it must gain one (C-006) so it can classify. Confirm the target-branch/ref threading from the allocator's callers before implementing.

### Brownfield seam notes (folded from the pre-implement scout — read before coding)

1. **Tip capture stays IN the lanes layer.** WP01's `classify_recorded_pin` takes an already-captured `target_tip`, so each caller must capture it. Do **NOT** import `_capture_target_branch_tip` from `cli.commands.agent.mission_finalize` (an upward cli-god-module coupling from a lanes-layer helper), and do **NOT** add a third inline `rev-parse`. Reuse the EXISTING lanes-layer primitive — `lanes/merge.py::_rev_parse(repo_root, ref) -> str | None` (returns `None` on failure, matching the degrade contract) or `implement_support.py::_rev_parse` (~L251) / `lanes/_git.py`. Capture `target_tip = _rev_parse(repo_root, manifest.target_branch)` at the caller and pass it to both `_merge_recorded_planning_commit` and `classify_recorded_pin`. (Linked worktrees share the object store, so `cat-file`/`is-ancestor` resolve identically regardless of `cwd=repo_root` vs `worktree_path`.)
2. **Do NOT retire `implement_support.py::_is_git_ancestor` (~L385).** It is used TWICE: the pin at :497 (convert this use to `classify_recorded_pin`, keyed off the target tip) AND the **dependency-lane tips at :500** (leave on `_is_git_ancestor`). Deleting it breaks the dep-lane ancestry check. Only the :497 pin use converts.
3. **Narrow the fresh-path try/except.** `worktree_allocator.py` :561-569 wraps the FRESH-path merge in `except PlanningCommitMergeConflictError` (worktree removal + retry). The new `OrphanedPlanningCommitError` (T013) MUST NOT be caught there, or a fresh-path orphan gets the remove-and-retry-forever treatment. Keep that except narrow to the generic conflict.
4. **`_mt_resolve_owned_review_base` captures the tip from the RIGHT repo.** Its current `resolve_commit`/`rev-parse --verify` runs with `cwd=owned.root` (the owned checkout). The orphan classification needs the TARGET TIP, captured from the repo that holds `target_branch` — `st.main_repo_root` / `owned.primary`, NOT `owned.root`.
5. **5th reader — decide and document.** `resolve_lane_base_or_refuse`'s `detached_base` route (`worktree_allocator.py` :240-244, fed at :497/:529; FR-010 `UnhonorableBaseError`) is an unreconciled read of the pin, but it only fires on an explicit `--base` and is a common-ancestor query (not tip-reachability), so an orphan does not obviously mislead it. It is already in a WP03-owned file — consciously decide whether it needs orphan-awareness and record the decision in the tracer; do not leave it silently unconsidered.
6. **Recovery-string constant (LOW).** The `--refresh-planning-commit --allow-orphaned` recovery text authored as a Typer flag in WP02 is referenced as literal text in `OrphanedPlanningCommitError.next_step` here — prefer a shared module constant to avoid drift if convenient, acceptable as literal otherwise.

## Subtasks

### T011 — Red-first repro (@pytest.mark.regression, pinned to #4827)
`tests/lanes/test_issue_4827_allocator_orphan_pin.py`: allocate/merge a lane whose `lanes.json` records an ORPHANED pin (present, unreachable from the target tip). Assert the desired post-fix behavior (orphan-specific error naming the finalize re-pin recovery) → RED today (currently the generic `PlanningCommitMergeConflictError` or a silent fall-through). Reference #4827 in the docstring.

### T012 — Centralized orphan detection in the merge helper
Give `_merge_recorded_planning_commit` a `target_branch`/`target_tip` argument (thread from callers at :419/:482/:562). Before the existing lane-HEAD ancestry logic, classify the pin via WP01 `classify_recorded_pin(repo_root, pin, target_tip)`; on `orphaned` (or `foreign`) raise the new orphan-specific error (T013). Leave the lane-HEAD no-op gate and the genuine-content-conflict path (`advanced`) unchanged.

### T013 — Orphan-specific error class
Add an error class (sibling to `PlanningCommitMergeConflictError`) — e.g. `OrphanedPlanningCommitError` — whose message/`next_step` names the recorded SHA and the `spec-kitty agent mission finalize-tasks --refresh-planning-commit --allow-orphaned` recovery, and whose `to_dict`/payload distinguishes it from the generic conflict. Do NOT reuse the generic conflict's "resolve manually" text.

### T014 — Reconcile implement_support
- `:352` reconcile merge is covered by T012 (shared helper) — verify the target ref is threaded there too.
- `check_claim_ancestry` (:497): when the pin classifies `orphaned`, surface an orphan diagnostic naming the re-pin recovery instead of the bare `"recorded planning commit <sha>"` `missing_refs` entry.

### T015 — Reconcile the owned-review base
`_mt_resolve_owned_review_base` (`tasks_move_task.py:697`): classify the pin; on `orphaned` fail closed / name the re-pin recovery rather than diffing against the dead base (do not trust `rev-parse --verify` alone — object presence ≠ reachability).

### T016 — Corrected expectations
- `tests/lanes/test_lane_base_common_ancestor.py` (~L284 `test_conflicting_merge_fails_closed_...`) and `tests/lanes/test_worktree_allocator_atomicity.py` (~L302): these set a real side-branch commit (present-unreachable) and assert the GENERIC conflict. Update them to the corrected expectation: if the fixture pin is now classified `orphaned` (unreachable from the target tip), assert the orphan error; if the intent is a genuine reachable content conflict, adjust the fixture so the pin is reachable from the target tip and keep the generic error. Preserve each test's original INTENT; do not green-wash. **GREEN-WASH GATE (reviewer-enforced):** after this edit, at least ONE test in `tests/lanes/` MUST still exercise the generic `PlanningCommitMergeConflictError` with a pin that is **reachable from the target tip** (a genuine content conflict). Flipping BOTH tests to expect the orphan error would leave the genuine-conflict path with zero coverage — that is the lazy failure this subtask exists to prevent.

### T017 — Un-mark and verify
Demote the T011 repro from `@pytest.mark.regression` to a focused permanent test post-fix. Run and record the full `tests/lanes/` directory.

## Branch Strategy

Planning branch and merge target: `fix/finalize-repin-orphaned-planning-commit`. Per computed lane from `lanes.json`. **Depends on WP01** (the classifier).

## Definition of Done

- All four consumers (merge fresh+reuse, reconcile, claim gate, owned-review base) surface an orphan-specific, recovery-naming outcome for an orphaned pin.
- Healthy/reachable pins keep their existing behavior (genuine conflicts stay generic; lane-HEAD no-op gate intact — C-006).
- NFR-003 catch-up-merge behavior documented in the tracer (an already-allocated lane catches up after a re-pin; genuine conflicts there are real).
- Corrected-expectation suites pass with intent preserved; the #4827 allocator repro green post-fix.
- `ruff` / `ruff format --check` / `mypy` clean; complexity ≤ 15; no new suppressions.

## Risks / reviewer guidance

- **C-006 is the whole game**: reviewers must verify orphan detection keys off the TARGET-BRANCH TIP, not the lane HEAD — else it misfires on every healthy fresh coord lane (#2993). This is the #1 review focus.
- `tests/lanes/` is OUTSIDE `make test-fast` — name it explicitly in the PR *Tests run*.
- Keep detection in the ONE shared helper; do not scatter per-call-site orphan checks (single authority).
