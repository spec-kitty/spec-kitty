---
work_package_id: WP01
title: Pin authority and finalize pin decisions
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- FR-009
planning_base_branch: issue-7793-single-branch-planning-pin
merge_target_branch: issue-7793-single-branch-planning-pin
branch_strategy: Planning artifacts for this mission were generated on issue-7793-single-branch-planning-pin. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7793-single-branch-planning-pin unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - Behaviour
history:
- at: '2026-11-22T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py
create_intent:
- tests/lanes/test_planning_base_pin_authority.py
- tests/integration/test_7793_single_branch_repin_patch_id.py
- tests/specify_cli/cli/commands/agent/test_finalize_pin_decisions_7297.py
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/planning_base.py
- tests/lanes/test_planning_base.py
- tests/lanes/test_planning_base_pin_authority.py
- src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py
- tests/integration/test_7793_single_branch_repin_patch_id.py
- tests/specify_cli/cli/commands/agent/test_finalize_pin_decisions_7297.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Pin authority and finalize pin decisions

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completion and record progress with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Objectives & Success Criteria

Primitives (`lanes/planning_base.py`):

- `planning_base.pin_branch_line(meta, target_branch) -> str`: `meta["mission_branch"]` when the STORED topology is `single_branch` and `mission_branch` is a non-empty string, else `target_branch` (research R1). Pure; no git.
- `planning_base.follow_pin_by_patch_id(repo_root, pin, tip) -> PatchIdFollow`: research R2. Exactly one non-empty patch-id match in `rev-list merge-base(pin, tip)..tip` gives `sha`; an empty-diff pin gives `miss="no_patch_id"`; zero matches give `"no_match"`; several give `"ambiguous"` with `candidates`. A git error raises `GitProbeError` (the caller refuses; NFR-002).
- Derivation (`resolve_finalize_planning_base`) anchors on `kitty-specs/<slug>/tasks/` (any file) and on the last absent→present transition of that directory on the first-parent line (research R5). The existing `resolve_planning_base_commit` contract (`--skip-lanes`, the Mission directory anchor) is unchanged.


Finalize behaviour:

- SC-001: the #7793 scenario exits 0 through the real CLI (commit → for_review → reject → `git rebase main` → re-pin → `move-task --to for_review`).
- SC-002: a no-match re-pin exits 1 with `PLANNING_PIN_NO_PATCH_ID_MATCH`, and `lanes.json` is byte-identical.
- SC-003: three plain finalizes keep a derived pin.
- SC-004: a minted-branch single_branch Mission rebased onto a newer `main` has no `main`-only commit in its window, and `--refresh-planning-commit` no longer refuses `PLANNING_REFRESH_FAIL_CLOSED`.
- The decision table in `contracts/pin-decisions.md` holds row by row.

## Context & Constraints

- Research R1-R4, R6; data-model invariants I-1..I-3.
- C-003: lane Missions keep the #4827 re-pin to the tip; only the derived freeze is topology-neutral.
- C-005: `mission_finalize.py` overlaps Slice 1a. Keep every edit inside `mission_finalize_planning_pin.py`. The callers pass `target_branch`; resolve the pin line inside the pin module from `meta.json`.
- Complexity ≤ 15 per function (Sonar S3776); extract helpers.

## Branch Strategy

- **Strategy**: single_branch (settled by finalize-tasks from the WP count/lane count)
- **Planning base branch**: `kitty/mission-single-branch-planning-pin-rebase-01M81KRS`
- **Merge target branch**: `issue-7793-single-branch-planning-pin`
- Execution workspaces come from `lanes.json`; on single_branch the WP runs in the repository root checkout.

## Subtasks

### T001 Red-first unit tests
New `tests/lanes/test_planning_base_pin_authority.py` over real temporary git repos: the rebased copy is found; an empty commit pin gives `no_patch_id`; a dropped commit gives `no_match`; a cherry-picked duplicate gives `ambiguous`; `pin_branch_line` for single_branch with and without `mission_branch`, and for `lanes`. In `tests/lanes/test_planning_base.py`: re-add anchors on the re-add; a rename `tasks/a.md -> tasks/WP01-a.md` anchors on the first task file. Run them red first.

### T002 `pin_branch_line`
Read topology with `specify_cli.migration.backfill_topology.stored_topology` and `mission_runtime.is_single_branch` (the same pair `single_branch_landing.is_single_branch_meta` uses).

### T003 `follow_pin_by_patch_id`
Frozen dataclass `PatchIdFollow(sha, miss, candidates)`. `git merge-base pin tip` through `run_git`; no merge-base → `no_match`.

### T004 Derivation anchor
Walk `git log --first-parent --reverse --format=%x00%H --name-status -- kitty-specs/<slug>/tasks/`, tracking the set of present paths. The anchor is the commit that made the set non-empty after it was last empty. The base is that commit's first parent (a root is its own base). Keep the lane-containment check.


### T005 Red-first real-CLI tests
New `tests/integration/test_7793_single_branch_repin_patch_id.py` on the #5939 harness pattern (`python -m specify_cli` subprocesses, isolated HOME). Shape A: commit-to-target single_branch on an unprotected `topic`. Rows: the #7793 positive (red today); no-match (rewrite the planning commit's content during the rebase); window guard (re-pin target that drops the work); derived freeze across three plain finalizes; shape B (minted branch): the pin is on the mission branch, the window excludes `main`-only commits after the rebase, and refresh succeeds. Unit-level decision rows go in `test_finalize_pin_decisions_7297.py` (reasons and texts).

### T006 Pin branch line
A helper `_pin_line(repo_root, mission_slug, target_branch, owned)` reads stored meta (`single_branch_landing.stored_mission_meta` or the placement seam) and returns `planning_base.pin_branch_line`. Use it for `capture_branch_tip` in `_preserve_or_capture_planning_commit_sha`, for derivation, for the classifier tip, and in `_prepare_primary_pin_refresh_commit` (the destination check and the compare-and-swap tip).

### T007 Patch-id re-pin
In `_resolve_refresh_planning_commit_decision` for an ORPHANED pin with `--allow-orphaned` on single_branch: `follow_pin_by_patch_id`. A match gives `action="repinned"`, `sha=match`, `matched_by="patch_id"` (a new optional field; the JSON `planning_commit.matched_by` appears only when set). A miss refuses with `error_code` `PLANNING_PIN_NO_PATCH_ID_MATCH` or `PLANNING_PIN_PATCH_ID_AMBIGUOUS`, saying the evidence window would lose committed work and naming the manual route (set `planning_commit_sha` to the commit before the first implementation commit). A `GitProbeError` refuses `PLANNING_REFRESH_FAIL_CLOSED`.

### T008 Window guard
`_window_keeps_owned_work(repo, slug, old, candidate, tip)`: union of every WP's `owned_files` (reuse the ownership reader finalize already uses), `wp_evidence.evidence_paths` and `has_owned_change`. The explicit single_branch refresh/re-pin refuses `PLANNING_PIN_WOULD_EMPTY_WINDOW`. The automatic refresh returns `kept_with_warning`, `refusal_reason="window_would_empty"`. A probe error refuses (explicit) or keeps the pin (automatic).

### T009 Freeze and reasons
Automatic path: when the recorded pin equals `resolve_finalize_planning_base` on the pin line now, return `preserved` (extract it so `_resolve_preserve_planning_commit_decision` stays ≤ 15). INDETERMINATE with `recorded is None`, a resolved tip and nothing derivable gives `no_pin_underivable`. Update `_report_planning_sha_decision`: the `indeterminate_tip_uncapturable` text only for a `None` tip; a new text for `no_pin_underivable` naming `finalize-tasks --refresh-planning-commit`; a `window_would_empty` text; the re-pin text names the patch-id match.

## Test Strategy

`tests/lanes/test_planning_base.py`, `tests/lanes/test_planning_base_pin_authority.py`, the new files, plus `tests/lanes/test_issue_4827_allocator_orphan_pin.py`, `tests/consolidation/test_single_branch_evidence_axis.py`, `tests/consolidation/test_wp_evidence.py`; out-of-matrix (disclose): `tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py`, `test_finalize_tasks_orchestration.py`, `test_move_task_evidence_gate.py`; and `make test-fast`.

## Definition of Done

All rows of the contract are covered by a test; the red-first tests were seen red on the base.

## Risks

Golden JSON contract tests (`test_mission_cli_golden_contract.py`): `matched_by` must be absent unless set.

## Reviewer Guidance

Verify the lane re-pin path is byte-identical; verify the shape B fixture really mints a branch.
