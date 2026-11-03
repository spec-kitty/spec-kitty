---
work_package_id: WP01
title: The shared absence probe and the never-created cause
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-007
- FR-008
- NFR-001
- NFR-002
- SC-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - The shared seam
history:
- at: '2026-11-03T13:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/wp_evidence.py
- tests/consolidation/test_wp_evidence.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7120'
---

# Work Package Prompt: WP01 – The shared absence probe and the never-created cause

## Objectives & Success Criteria

`consolidation/wp_evidence.py` is the single authority for the implementation-evidence axis, and
both refusing surfaces already call it (`move-task` through `lane_evidence_window` /
`evidence_paths` / `widened_lane_paths`, `accept` and `consolidate` through `evaluate_evidence`).
This work package puts the absent-branch knowledge there once:

- a public, fail-closed `branch_ref_absent` (today's private `_branch_ref_absent`, used by the
  #6780 landed-window path) so a caller outside this module can apply the same rule;
- a read-only classifier for the shape the issue recorded — a `lanes`/`coord` Mission in which no
  code lane has a branch — and the cause sentence that names it, with the honest next step;
- the `IMPLEMENTATION_UNREADABLE` recovery row gains the same next step (a step that exists), so
  the shared table and the per-work-package line agree.

Success: `evaluate_evidence` on the #7120 shape produces an `IMPLEMENTATION_UNREADABLE` refusal
whose cause line names the absent lane branch, states the Mission's work is on the target branch
instead, says creating the branch would fabricate the evidence, and names the open ruling; a
pruned-branch case keeps the restore remedy; a present-but-unreadable ref keeps
"could not be diffed"; and no verdict changes.

## Context & Constraints

- Read the issue: <https://github.com/spec-kitty/spec-kitty/issues/7120>. The quoted refusal and the
  three candidate fixes are there; this Mission implements option 1 only.
- `_landed_window`'s rules must not move: `git show-ref --verify` exit **1** is absence, exit 128
  is not; a ref that exists but cannot be read never falls back (#6780).
- Do **not** widen the window (#7120 option 2, C-001). Do not touch `single_branch` wording.
- `tests/consolidation/test_wp_evidence_recovery_wording.py` (landing with PR #7124) pins facts
  about the `IMPLEMENTATION_MISSING` and `REVIEW_NOT_INDEPENDENT` rows only; leave those rows alone.
- Existing assertions you must keep true: `tests/consolidation/test_wp_evidence.py`'s
  `test_a_lane_ref_that_exists_but_cannot_be_read_refuses_instead_of_falling_back` ("could not be
  diffed", never "no longer exists") and the pruned-tip test's two "pull request merge commit (not a
  squash)" mentions.

## Subtasks & Detailed Guidance

### Subtask T001 – Public `branch_ref_absent` and the lane-branch classifier
- **Steps**:
  1. Rename `_branch_ref_absent` to `branch_ref_absent`, add it to `__all__`, update the two
     in-module callers and the two test references in `tests/consolidation/test_wp_evidence.py`.
     Keep the body byte-for-byte: only `git show-ref --verify` exit 1 means absent; every other
     outcome (128, `OSError`) means present.
  2. Add a small read-only classifier, e.g.
     `lane_branches_absent(repo_root, lanes_manifest) -> bool`: True only when the manifest has at
     least one code lane and every code lane's created branch is absent. Use
     `lane_created_branch`/`is_planning_lane` so a planning lane (whose tip is the target branch)
     never counts as a lane branch. Never raises: an unreadable probe reads as "not absent".
  3. Docstrings must state the fail-closed direction and why the probe is only ever called after a
     diff has already failed.
- **Files**: `src/specify_cli/consolidation/wp_evidence.py`
- **Notes**: NFR-001 — no added git call on the passing path.

### Subtask T002 – The never-created cause
- **Steps**:
  1. Add the cause text for an absent lane-window tip: state that the lane branch does not exist;
     state, when `lane_branches_absent` holds, that the Mission never created its lane branches and
     committed its work on the target branch; state that there is no lane window to restore and that
     creating the branch now would fabricate the evidence the gate checks; state that the evidence
     policy for that shape is unruled (#7120) and that the honest next step is to report it.
  2. For the pruned case (another lane branch exists, or a lane-tip ref was recorded) keep the
     restore remedy in the module's established phrasing: `refs/spec-kitty/lane-tip/<branch>` or the
     pull request's head.
  3. Wire it into `_unreadable_line`'s `absent_ref` branch, keeping the existing
     "pull request merge commit (not a squash)" scoping sentence and the `--merge-commit` remedy.
- **Files**: `src/specify_cli/consolidation/wp_evidence.py`
- **Notes**: no new code is emitted; the code stays `IMPLEMENTATION_UNREADABLE`.

### Subtask T003 – Tests for the classifier and the cause
- **Steps**:
  1. In `tests/consolidation/test_wp_evidence.py`, add: (a) `branch_ref_absent` is True for a
     never-created branch and False for a present one (existing test may cover part of this);
     (b) `lane_branches_absent` is True when no code lane has a branch, False when one does, and
     False for a `single_branch`/planning-lane-only manifest; (c) `evaluate_evidence` on the
     never-created fixture refuses `IMPLEMENTATION_UNREADABLE` with the never-created cause;
     (d) the pruned-tip fixture keeps the restore remedy and does not claim the Mission never
     created its lanes.
  2. Prove red: run the new cases against the pre-fix module (keep the tests, `git stash` the
     source) and record the failure.
- **Files**: `tests/consolidation/test_wp_evidence.py`
- **Notes**: use the file's existing helpers (`_repo`, `_manifest`, `_lane`, `_evaluate`) rather
  than a new fixture style.

## Definition of Done

- `uv run pytest tests/consolidation/test_wp_evidence.py -q -p no:randomly` green, new cases
  demonstrably red against the pre-fix source.
- `uv run mypy src/specify_cli/consolidation/wp_evidence.py` and
  `uv run ruff check src/specify_cli/consolidation/wp_evidence.py tests/consolidation/test_wp_evidence.py` clean.
- No verdict, code, exit status or passing-path git call changed.
