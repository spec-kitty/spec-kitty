---
work_package_id: WP11
title: S8 - stamp the write-branch head; approval-time warnings
dependencies:
- WP02
requirement_refs:
- FR-070
- FR-075
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T061
- T062
- T063
- T064
- T065
- T066
phase: Phase 4 - S8 approval windows for single_branch
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_lane_head_single_branch.py
- tests/consolidation/test_single_branch_stamp_warnings.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/lane_head.py
- src/specify_cli/lanes/single_branch_landing.py
- src/specify_cli/consolidation/approved_bound.py
- tests/status/test_lane_head_single_branch.py
- tests/consolidation/test_single_branch_stamp_warnings.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 - S8: stamp the write-branch head; approval-time warnings

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP11 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP11 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S8 (#7283), stamp half:

- FR-070: every lifecycle transition of a WP in a Mission whose STORED topology is `single_branch` carries the Mission write branch's head as `policy_metadata.lane_head`, gated on the stored topology, never on `is_planning_lane` / `execution_mode: direct_repo`. Positive control: a `lanes` Mission's planning-lane WP returns no stamp on the same run.
- FR-075: `move-task` and `agent status emit` print the existing unstamped-approval and forced-approval warnings (`approved_bound.unstamped_approval_warning`, `forced_approval_warning`) for `single_branch` Missions.
- Behaviour-preserving tidies that WP12 and WP14 build on.

## Context & Constraints

- Read: spec User Story 4, FR-070 to FR-078, A-4, A-8; `research.md` R-7, R-8; `data-model.md` §5; WP02's ADR `2026-10-04-5` amendment; CLAUDE.md "Approved claim is bounded by the approval stamp" (the lanes rule you mirror).
- Stamp probe: `status/lane_head.py` is injected by the two status shells; the status pipeline stays git-free. Keep imports function-local (`tests/architectural/test_cold_import_status_boundary.py`).
- Five overlapping predicates today (`is_planning_lane`, `is_repo_root_lane`, `lands_mission_branch`, `minted_mission_branch`, `is_single_branch_mission`); `lane_created_branch("lane-planning")` resolves to the target (trap). `write_branch_for(manifest, meta)` becomes the one answer (charter single canonical authority).
- **#7248 (NOT merged, `issue-7224-flat-fixture-single-branch`)**: its fixture comment says `single_branch` is never stamped. When it lands, rebase onto it and deliberately reverse that comment/assertion in a separate commit; note it. Until then, do not depend on its fixture.
- `mission_runtime/resolution.py::single_branch_write_ref` is the pure write-branch rule; `write_branch_for` should delegate to it, not duplicate it.
- C-011 red-first; complexity <= 15 (the `check_lane` split exists for that).
- **Later recorded out-of-map hunk by WP20** (analysis G3/G5): WP20 (after you, via WP12 -> WP14) adds a separate default-Mission predicate (for example `lands_topic_branch`) to `lanes/single_branch_landing.py`. `lands_mission_branch` keeps its `single_branch` meaning and its six callers; do not widen it here either.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T061 - Red-first tests

- `tests/status/test_lane_head_single_branch.py`: `test_single_branch_probe_stamps_mission_branch_head` (minted `single_branch` Mission; probe returns the Mission branch head SHA); `test_lanes_planning_lane_wp_stays_unstamped` (positive control, same run); `test_move_task_approved_records_lane_head_single_branch` (through the real `move-task` CLI; the persisted `approved` event carries `policy_metadata.lane_head`).
- `tests/consolidation/test_single_branch_stamp_warnings.py`: `test_unstamped_single_branch_approval_warns` (stderr one-line warning on `move-task` and `agent status emit`); `test_forced_single_branch_approval_warns`.

### Subtask T062 - `write_branch_for`

- In `lanes/single_branch_landing.py`: `write_branch_for(manifest, meta) -> str` delegating to `single_branch_write_ref`; collapse `minted_mission_branch` (`:75`), `single_branch_evidence_window`'s branch and `expected_consolidate_checkout` onto it. Add an owned-aware stored-topology helper callable without a manifest (reads `meta.json`). Behaviour-preserving commit.

### Subtask T063 - `approved_bound` tidies

- Rename `_maps_to_code_lane` (`:325`) -> `_approval_is_bounded` (it will answer "is this approval bounded", true for minted `single_branch` too after T064/WP12).
- Split `check_lane` (`:465`) stamp resolution into a public `stamp_refusal(...)` returning the existing `BoundRefusal` codes (`APPROVAL_STAMP_MISSING`, `APPROVAL_STAMP_NOT_ON_LANE`). Pure refactor; existing approved-bound tests green.

### Subtask T064 - `lane_head` `single_branch` arm

- `status/lane_head.py`: when the stored topology is `single_branch` and `write_branch_for` names a branch, stamp its head (`git rev-parse refs/heads/<b>`), for every lifecycle transition. A `lanes` planning lane stays unstamped. A probe failure keeps today's best-effort behaviour (no stamp, no crash) - the bound treats a missing stamp per FR-074.

### Subtask T065 - Warnings

- `approved_bound.unstamped_approval_warning` / `forced_approval_warning`: extend their predicate via `_approval_is_bounded` so `single_branch` Missions with a minted branch warn. Commit-to-target Missions (write branch == target) do not warn (unbounded residual, FR-078).

### Subtask T066 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/status/test_lane_head_single_branch.py tests/consolidation/test_single_branch_stamp_warnings.py -q
uv run --frozen pytest tests/status tests/consolidation tests/specify_cli/lanes tests/lanes -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile -k "move_task or status"   # out-of-matrix dir
uv run --frozen pytest tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_layer_rules.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict src/specify_cli/status/lane_head.py src/specify_cli/lanes/single_branch_landing.py src/specify_cli/consolidation/approved_bound.py
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP11] ...**`, naming the trace file); the orchestrator appends them.

## Risks & Mitigations

- Stamping changes event bytes for `single_branch`: `policy_metadata.lane_head` is an existing optional key (contracts/README); no schema change.
- Cold-import regression: function-local imports.

## Review Guidance

- Gated on the STORED topology; `lanes` planning lane unstamped; predicates collapsed onto one answer; warnings on both surfaces; refactors behaviour-preserving.

## Definition of Done

- T061-T066 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T061 T062 T063 T064 T065 T066 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP11 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
