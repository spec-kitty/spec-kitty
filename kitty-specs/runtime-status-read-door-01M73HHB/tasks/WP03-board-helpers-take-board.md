---
work_package_id: WP03
title: Board helpers accept the board status
dependencies:
- WP01
requirement_refs:
- C-003
- FR-008
- NFR-001
- NFR-004
planning_base_branch: refactor/7310-status-read-door-s5
merge_target_branch: refactor/7310-status-read-door-s5
branch_strategy: Planning artifacts for this mission were generated on refactor/7310-status-read-door-s5. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into refactor/7310-status-read-door-s5 unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Tidy-first enablers
history:
- at: '2026-11-11T05:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/runtime/next/test_board_helpers_board_param.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/discovery.py
- src/runtime/next/decision.py
- tests/runtime/next/test_board_helpers_board_param.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Board helpers accept the board status

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Teach the board and progress helpers in `src/runtime/next/discovery.py` and `src/runtime/next/decision.py` to read a `BoardStatus` (WP01) passed as `board=`. Their current Path forms (`feature_dir` / `status_dir=`) stay, as thin adapters that build a board with `board_status_from_dir`. **No call site changes and no behaviour change** (tidy-first, Standing Order 2). WP04 switches the call sites to the door.

Done when:
- `preview_claimable_wp(feature_dir, *, status_dir=None, board=None)`: when `board` is given, lanes and provenance come from it; otherwise today's behaviour (built through the adapter, or kept as is if byte-identical).
- `_compute_wp_progress(feature_dir, *, status_dir=None, board=None)` and `_find_first_wp_by_lane(feature_dir, lane, *, status_dir=None, board=None)` likewise. `_get_wp_lanes` gains a board-aware sibling, or is folded in.
- With `board=`, weighted progress comes from `board.weighted_percentage` (no `materialize_snapshot` read).
- Equivalence tests prove the board and Path forms give identical results on the same fixtures, and every existing helper suite passes unchanged.

## Context & Constraints

- Spec FR-008, NFR-001, NFR-004; plan IC-01 (helpers half); research R-1, R-2.
- Inventory of the helpers and their callers: `research/code-grounding.md` §1. Definitions: `discovery.py:97` (`_load_wp_states`), `:196` (`preview_claimable_wp`); `decision.py:236` (`_get_wp_lanes`), `:251` (`_compute_wp_progress`), `:318` (`_find_first_wp_by_lane`).
- Behaviours to keep exactly:
  - `_load_wp_states` is best-effort: on any read or reduce failure it returns `{}`;
  - `_get_wp_lanes` swallows only `CanonicalStatusNotFoundError` (an absent log reads as `{}`), and a corrupt log raises;
  - `_compute_wp_progress` logs and omits the weighted figure on failure (`decision.py:310`), and returns `None` with no `tasks/` dir or no WP files;
  - genesis WPs are counted in `total_wps` but in no bucket (`NON_DISPLAY_LANES`).
- `tasks/` and the dependency graph stay planning reads on `feature_dir` (the PRIMARY partition). Only lane state moves to the board.
- Do **not** touch `decision._with_guard_failure_paths` (WP05) or the `Decision` dataclass (WP06).

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Run `spec-kitty agent action implement WP03 --agent <name> --mission runtime-status-read-door-01M73HHB` (it depends on WP01).

## Subtasks & Detailed Guidance

### Subtask T011 – `preview_claimable_wp` / `_load_wp_states` accept `board=`

- **Steps**:
  1. Add keyword-only `board: BoardStatus | None = None` to `preview_claimable_wp`.
  2. When `board` is given, use `board.wp_states` as the provenance map and derive lanes with `_wp_lanes_from_states(board.wp_states)`. That is the same derivation, so the result is identical.
  3. When `board` is `None`, keep today's `_load_wp_states(_status_dir)` path byte-identical. Do not route it through the adapter, because `_load_wp_states` swallows every exception and the adapter raises on a corrupt log. Keeping the old path avoids a behaviour change.
  4. Update the docstring: `board=` is the preferred form; `status_dir=` is kept for outside callers (`workflow.py:1261`) and tests.
- **Files**: `src/runtime/next/discovery.py`.

### Subtask T012 – `_compute_wp_progress` / `_find_first_wp_by_lane` accept `board=`

- **Steps**:
  1. Add keyword-only `board: BoardStatus | None = None` to both.
  2. Lane map: `board.lanes` when given, else `_get_wp_lanes(lane_read_dir)` as today.
  3. Keep the counting loops identical. Extract a tiny pure helper (e.g. `_bucket_counts(wp_files, wp_lanes)`) if it keeps complexity ≤ 15.
- **Files**: `src/runtime/next/decision.py`.

### Subtask T013 – Weighted progress from the board

- **Steps**: in `_compute_wp_progress`, when `board` is given, set `counts["weighted_percentage"] = board.weighted_percentage` when it is not `None`. Omit the key exactly when today's code would (on failure). With no board, keep the `materialize_snapshot` path.
- **Notes**: WP01's parity test is the proof that the two numbers agree; reference it in the docstring.

### Subtask T014 – Equivalence tests [P]

- **Steps**: new `tests/runtime/next/test_board_helpers_board_param.py`:
  - fixtures: a single_branch Mission with WPs in several lanes (planned, claimed, in_progress, for_review, approved, done, canceled, blocked) plus one genesis WP; reuse `tests/runtime/_next_mission_scaffold.py` helpers (`scaffold_software_dev`, `seed_wp_lane`);
  - for each helper, assert `helper(feature_dir, status_dir=d) == helper(feature_dir, board=board_status_from_dir(d))` (dicts and ids);
  - weighted progress equal to 1 dp;
  - absent log: same results both ways (empty board vs `CanonicalStatusNotFoundError` swallowed);
  - corrupt log: the Path forms keep today's behaviour (pin it), and building the board raises `StoreError`.
- **Files**: `tests/runtime/next/test_board_helpers_board_param.py` (new).

### Subtask T015 – Run the helper suites

- **Steps**: run the commands below and record counts in `add-history`. Every existing file must pass **unchanged**. If one needs editing, this WP changed behaviour: stop and fix the code.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -n 4 --dist loadfile tests/runtime/next/test_board_helpers_board_param.py tests/runtime/next/test_board_status.py tests/next/test_decision_unit.py tests/next/test_next_claimable_payload.py tests/next/test_finalized_task_routing.py tests/next/test_next_dependency_wedge_5669.py tests/integration/test_next_preview_primary_routing.py tests/specify_cli/status/test_progress_integration.py tests/runtime/test_run_state_hardening.py`
- `ruff check`, `ruff format --check --force-exclude` on changed files; `mypy src/runtime/next/discovery.py src/runtime/next/decision.py`
- `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_status_read_single_door.py tests/architectural/test_layer_rules.py`

## Risks & Mitigations

- **Accidental behaviour change on the Path form** (the exception policy differs between `_load_wp_states` and the adapter). Keep the old Path code path; T014 pins it.
- **Cyclic import** `decision.py` ↔ `board_status.py`: WP01's module imports nothing from `decision.py`. Import `BoardStatus` under `TYPE_CHECKING` where only types are needed.

## Review Guidance

- No caller changed; existing suites unchanged and green.
- `board=` and Path forms are proven equal on the same fixture, a same-fixture positive control.
- Complexity of `_compute_wp_progress` stays ≤ 15.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
