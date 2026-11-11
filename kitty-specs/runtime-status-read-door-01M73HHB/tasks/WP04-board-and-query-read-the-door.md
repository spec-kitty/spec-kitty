---
work_package_id: WP04
title: 'Board and query read the door; fixes #7507'
dependencies:
- WP02
- WP03
requirement_refs:
- C-002
- FR-001
- FR-002
- FR-005
- FR-006
- FR-008
- FR-011
- NFR-003
- SC-001
- SC-004
planning_base_branch: refactor/7310-status-read-door-s5
merge_target_branch: refactor/7310-status-read-door-s5
branch_strategy: Planning artifacts for this mission were generated on refactor/7310-status-read-door-s5. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into refactor/7310-status-read-door-s5 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-runtime-status-read-door-01M73HHB
base_commit: db26b1c8fbcd81e375d1a72f2bf4c9032f4d2155
created_at: '2026-11-11T06:05:11.709992+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
- T022
phase: Phase 2 - Reads move onto the door
history:
- at: '2026-11-11T05:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/runtime/next/test_board_query_read_door_7507.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_decision_mapping.py
- src/runtime/next/runtime_bridge_query.py
- tests/runtime/next/test_board_query_read_door_7507.py
- tests/runtime/test_runtime_bridge_read_path_branches.py
- tests/next/test_runtime_bridge_unit.py
- tests/next/test_query_mode_unit.py
- tests/architectural/test_status_read_single_door.py
- tests/architectural/_baselines.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Board and query read the door; fixes #7507

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

This WP removes the cause of #7507 (`fixes #7507` in the PR). `next` in query mode, and the board selector, read the status read door **once per decision** and pass one `BoardStatus` to every helper.

Done when:
- #7507 cells (red-first): for a non-owned coordination Mission with WP01 planned and WP02 for_review committed on the coordination branch, `query_current_state` on an **empty** and on an **unmaterialized** coordination worktree reports `mission_state` `implement`, `wp_id` WP01, 1 planned / 1 for review, weighted 30.0, the same as the materialized control (FR-001, SC-001).
- Board selector `_resolve_wp_board_action`:
  - **empty** worktree: dispatches WP01 (today it returns `blocked:no_actionable_wp`);
  - **unmaterialized** worktree: still returns today's named "Coordination surface … is not readable … materialize it" block, byte for byte (FR-002, for direct callers);
  - **deleted** branch: unchanged flatten guidance.
- Owned (DM-1): owned coordination query on an empty or unmaterialized worktree reads the committed branch (FR-005, red-first: today the empty cell raises `MissionNotFoundError` and the unmaterialized cell shows an empty board). The owned board on those cells keeps today's outcome, a decline (dispatch never runs from a missing owned workspace; the typed `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` decision comes from bootstrap, WP05) (FR-006).
- Exactly one door read per board decision and per query (FR-008), proven with a counting spy.
- Gate: 4 entries removed (`_resolve_wp_board_action` ×2, `query_current_state`, `_build_finalized_override_query_decision`); `_LIVE_HIT_FLOOR` 42 → 38; `_baselines.yaml` `legacy_read_allowlist` 41 → 37 (FR-011).

## Context & Constraints

- Spec FR-001, FR-002, FR-005, FR-006, FR-008, FR-011; data-model state table; Decision Moments DM-1 (`01M73HKG7WSR4VDRFXG9JWTGM8`) and corrected DM-2 (`01M73J4X57HKNF5RK7WVN8QHC5`).
- Evidence: `research/code-grounding.md`:
  - §0 for the sites and line numbers;
  - §4 for the test inventory (B = behaviour pin, keep; M = mechanism pin, may go stale; X = the two block pins, which **must stay green**);
  - §5 for the observed cells.
  Repro: `research/repro/repro_cells.py MATERIALIZED EMPTY UNMATERIALIZED` (run from the repo root with `PYTHONPATH=.`).
- Uses WP01 (`board_status_from_surface`), WP02 (owned door entry) and WP03 (helpers accept `board=`).
- **Block decision from the surface source, not a seam raise.** Today the selector probes `placement_seam(...).read_dir(STATUS_STATE)` only to catch `CoordinationWorktreeUnmaterialized` (`decision_mapping.py:476`). Through the door an unmaterialized worktree reads as `COORD_BRANCH_REF`, the same as an empty one. To keep the block for **unmaterialized only**, distinguish the two with a door-level fact, not a seam probe. Options, in order of preference:
  1. a small public door helper in `read_surface.py` (for example `coordination_worktree_materialized(surface) -> bool | None`). That file is owned by WP02, so it is an out-of-map edit: record it with one line in `add-history`;
  2. `probe_coord_state` from `specify_cli.missions._read_path_resolver`, which the door itself uses, called with the surface's facts.
  Either way the block's text must stay exactly today's (it comes from the exception's own `next_step`; build the same exception and use its message so the remedy keeps one composer).
- `_build_finalized_override_query_decision` builds a second `mission_context_for`. Pass it the board (or the surface) from `query_current_state` instead, so the query reads once.
- Query's PRIMARY reads (`tasks/`, mission type) stay on the placement seam / mission context, and only `STATUS_STATE` moves. For an owned coordination Mission, the mission context build raises `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` today because it resolves the status kind too. Resolve the PRIMARY kinds without the status kind (e.g. `placement_seam(repo_root, slug, owned=owned).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)`, which resolves only the requested kind; verify against `resolution.py:_owned_read_dir_for_kind`) so the query no longer trips that refusal.
- Charter: red-first (C-002); judge each test (stale mechanism pin → re-pin keeping its domain assertion; never delete a behaviour pin); no `make test-full`.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Run `spec-kitty agent action implement WP04 --agent <name> --mission runtime-status-read-door-01M73HHB` (it depends on WP02, WP03).

## Subtasks & Detailed Guidance

### Subtask T016 – Red test: #7507 cells

- **Steps**:
  1. New `tests/runtime/next/test_board_query_read_door_7507.py` (marker per file convention; these build git repos, so mark `git_repo` + `integration`).
  2. Fixture: `scaffold_coord_software_dev(repo, slug, MissionTopology.COORD, wps={"WP01": "planned", "WP02": "for_review"})`, commit the coordination worktree, then make the cell (empty: `shutil.rmtree` the coordination Mission dir; unmaterialized: `git worktree remove --force` the coordination worktree). Parametrize `COORD` and `LANES_WITH_COORD`.
  3. Assert for `query_current_state`: state `implement`, wp WP01, progress planned 1 / for_review 1 / total 2, weighted 30.0, in all three cells.
  4. Assert for `_resolve_wp_board_action`: materialized and empty dispatch `implement` WP01; unmaterialized returns the named block (reuse the expectations of `tests/runtime/test_next_board_authority.py:601`).
  5. Commit **alone** and confirm red: the empty and unmaterialized query cells and the empty board cell. Record the failure output with `add-history`.

### Subtask T017 – Red test: owned coordination query and board

- **Steps**:
  1. Same new file. Build an owned coordination Mission (reuse fixtures from `tests/integration/test_owned_next_runtime.py`).
  2. Owned query on empty and on unmaterialized: real lanes (red today: `MissionNotFoundError` / empty board).
  3. Owned board on empty and unmaterialized: `_WP_BOARD_DECLINE`, unchanged (green today; this is the ratchet for FR-006).
  4. Commit together with T016's red commit, or right after it, before any fix.

### Subtask T018 – Board selector reads the door

- **Steps** in `runtime_bridge_decision_mapping.py`:
  1. In `_resolve_wp_board_action`: `surface = resolve_status_read(repo_root, mission_slug, owned=owned)`. Map `CoordinationBranchDeleted` to today's blocked text (unchanged). `StatusSurfaceRefUnreadable` / `WorktreeRegistryUnavailable` must not escape as a traceback: return a named blocked reason using the exception's message.
  2. Unmaterialized (non-owned): return today's block (see Context). Owned + ref source: return `_WP_BOARD_DECLINE` (today's outcome).
  3. `board = board_status_from_surface(surface)`. PRIMARY `task_board_dir` comes from the placement seam / mission context, as today.
  4. Pass `board=board` to `_wp_task_surface_error`, `_compute_wp_progress`, `_finalized_task_board_override_step`, `_resolve_wp_board_implement_action`, `_resolve_wp_board_review_action`. The helpers defined in this file (`_wp_task_surface_error`, `_count_wp_endings`, `_has_claimable_planned_wp`, `_finalized_task_board_override_step`, the two resolvers) gain `board=`, with their Path forms kept as adapters for outside callers (`runtime_bridge_guards.py:102` passes `ctx.feature_dir`; leave it working).
  5. Remove the `placement_seam(...).read_dir(STATUS_STATE)` probe and the `artifact(STATUS_STATE)` read from this function.

### Subtask T019 – Query reads the door once

- **Steps** in `runtime_bridge_query.py`:
  1. `query_current_state`: after the merged-mission short-circuit, resolve PRIMARY via the context or seam (see Context: avoid the owned status-kind refusal), then `surface = resolve_status_read(..., owned=owned)` and `board = board_status_from_surface(surface)`. Feed `_wp_task_surface_error`, `_compute_wp_progress` and `_finalized_task_board_override_step` with `board=`.
  2. `_build_finalized_override_query_decision`: accept `board` (or reuse the one built), call `preview_claimable_wp(task_dir, board=board)`, and drop its second `mission_context_for`.
  3. Map the door's exceptions to today's typed errors: `CoordinationBranchDeleted` passes through as the read-path error (`COORDINATION_BRANCH_DELETED` is in `_READ_PATH_ERROR_CODES`); a missing Mission stays `MissionNotFoundError`.
  4. Counting spy test: exactly one `resolve_status_read` and one `read_status_stream` call per `query_current_state`.

### Subtask T020 – Re-pin stale mechanism pins

- **Steps**: run the suites. For each red **mechanism** pin (M in grounding §4), re-pin it to the new mechanism while keeping its domain assertion, and list it in `add-history` with one line each:
  - `tests/runtime/test_runtime_bridge_read_path_branches.py:131` (`len(probes) == 1` on a fake seam) → one door read;
  - `:169` (fake seam + `contexts == [...]`);
  - `tests/next/test_runtime_bridge_unit.py:1068` (patches `decision_mapping.get_all_wp_snapshots`) → patch the board;
  - `:1806` / `:1825` (query `mission_context_for` pass-through);
  - `tests/next/test_query_mode_unit.py` patches of `runtime_bridge_query._compute_wp_progress`: they keep working if the name stays; re-pin only if red.
  Behaviour pins (B) and the X block pins (`test_next_board_authority.py:601`, `test_coordination_remedy_5113.py` `runtime_bridge` case) must pass **unchanged**. If one goes red, the code is wrong, not the test.
- **Files**: the three test files in `owned_files`. For a stale pin elsewhere, edit it out-of-map with a one-line rationale.

### Subtask T021 – Gate

- **Steps**: in `tests/architectural/test_status_read_single_door.py`, delete the 4 keys:
  - `src/runtime/next/runtime_bridge_decision_mapping.py::_resolve_wp_board_action::artifact(STATUS_STATE)`
  - `src/runtime/next/runtime_bridge_decision_mapping.py::_resolve_wp_board_action::read_dir(STATUS_STATE)`
  - `src/runtime/next/runtime_bridge_query.py::_build_finalized_override_query_decision::artifact(STATUS_STATE)`
  - `src/runtime/next/runtime_bridge_query.py::query_current_state::artifact(STATUS_STATE)`

  Then set `_LIVE_HIT_FLOOR = 38` (42 live hits today, minus 4). In `tests/architectural/_baselines.yaml`, change `legacy_read_allowlist` from 41 to 37 and append `Shrunk 41 -> 37 by runtime-status-read-door WP04` to its justification. Commit the gate change in the same commit as the move.

### Subtask T022 – Run suites

- Commands below; record counts.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -n 4 --dist loadfile tests/runtime/next/test_board_query_read_door_7507.py tests/runtime/test_next_board_authority.py tests/runtime/test_runtime_bridge_read_path_branches.py tests/next/test_runtime_bridge_unit.py tests/next/test_query_mode_unit.py tests/next/test_finalized_task_routing.py tests/next/test_next_claimable_payload.py tests/integration/test_next_preview_primary_routing.py tests/integration/test_owned_next_runtime.py tests/integration/test_owned_lifecycle_acceptance_next.py tests/specify_cli/cli/commands/test_coordination_remedy_5113.py tests/specify_cli/cli/commands/test_next_fail_closed.py tests/runtime/next/test_merged_mission_terminal.py tests/runtime/next/test_board_status.py tests/runtime/next/test_board_helpers_board_param.py`
- Gates: `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_status_read_single_door.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py`
- `ruff check`, `ruff format --check --force-exclude` per changed file; `mypy` on both source files.
- `tests/specify_cli/cli/commands` is out-of-matrix in CI (nightly only), so run those files locally.

## Risks & Mitigations

- **The X block pins go red** if unmaterialized is treated like empty. Keep the distinction (Context).
- **Owned query now hits the door before the PRIMARY reads.** Order the reads so a missing Mission still maps to `MissionNotFoundError`.
- **Second read sneaks back in** through `_build_finalized_override_query_decision`. The counting spy guards it.

## Review Guidance

- Red commits precede the fix; the empty and unmaterialized query cells were red on the base.
- Block text for unmaterialized is byte-identical (diff the X pins' expectations; they are unchanged).
- Gate: 4 keys removed, floor 38, baseline 37 in the same commit as the move.
- The PR body will say `Closes #7507`; check the cells match the issue.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP04 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
