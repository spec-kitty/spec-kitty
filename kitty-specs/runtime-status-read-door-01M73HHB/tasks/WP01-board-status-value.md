---
work_package_id: WP01
title: Board status value and parity
dependencies: []
requirement_refs:
- C-001
- C-003
- FR-008
- NFR-001
- NFR-002
planning_base_branch: refactor/7310-status-read-door-s5
merge_target_branch: refactor/7310-status-read-door-s5
branch_strategy: Planning artifacts for this mission were generated on refactor/7310-status-read-door-s5. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into refactor/7310-status-read-door-s5 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-runtime-status-read-door-01M73HHB
base_commit: eac7338080680082d07285af65c04b95e6a2d64d
created_at: '2026-11-11T05:19:26.637949+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Tidy-first enablers
history:
- at: '2026-11-11T05:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/board_status.py
create_intent:
- src/runtime/next/board_status.py
- tests/runtime/next/test_board_status.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/board_status.py
- tests/runtime/next/test_board_status.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Board status value and parity

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

Add one immutable **board status** value: a single reduced reading of a Mission's status for one `next` decision or query. It is built once from a status read door surface. This WP adds the value, its builders and its proofs. It changes **no** call site. WP03 and WP04 adopt it.

Done when:
- `src/runtime/next/board_status.py` exists with a frozen `BoardStatus` and two builders: `board_status_from_surface(surface)` and the Path adapter `board_status_from_dir(feature_dir)`.
- A parity test proves that, for every `kitty-specs/*/status.events.jsonl` in this repository, the board's per-WP lanes equal `get_all_wp_lanes(dir)` and its weighted progress equals `round(compute_weighted_progress(materialize_snapshot(dir)).percentage, 1)` (NFR-001).
- Edge tests cover no log, empty log, corrupt line and a ref-sourced surface.
- `ruff check`, `ruff format --check --force-exclude` and `mypy` are clean on both files; complexity ≤ 15 (NFR-004).

## Context & Constraints

- Spec: `kitty-specs/runtime-status-read-door-01M73HHB/spec.md` (FR-008, NFR-001, NFR-002).
- Plan: `plan.md` IC-01. Research: `research.md` R-1, R-2. Data model: `data-model.md` § BoardStatus.
- Evidence: `research/code-grounding.md` §1 (the Path-typed consumers this value replaces) and §2 (reducer experiment: lanes and weighted % identical on all 816 logs; only `implementer_of_record` differs, and runtime/next does not read it). Script: `research/repro/reducer_exp.py`.
- The door: `src/specify_cli/status/read_surface.py`. Use `read_status_stream(surface)` (transitions + annotations) and `specify_cli.status.reduce`. Never re-derive a source (C-001).
- Charter: tidy-first (Standing Order 2, DIRECTIVE_025): behaviour-preserving, no call-site change in this WP.
- Precedent: `src/specify_cli/cli/commands/agent/tasks_status_cmd.py` (`_st_reduce_surface`, #7335) reduces a door surface once.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; run `spec-kitty agent action implement WP01 --agent <name> --mission runtime-status-read-door-01M73HHB`.

## Subtasks & Detailed Guidance

### Subtask T001 – Define the frozen BoardStatus value

- **Purpose**: one value every board and progress helper reads, so they can no longer disagree (FR-008).
- **Steps**:
  1. Create `src/runtime/next/board_status.py` with a module docstring that cites ADR `2026-11-06-2` and #7310.
  2. Define `@dataclass(frozen=True) class BoardStatus` with:
     - `lanes: Mapping[str, Lane]`: WP id → canonical lane. Keep genesis WPs (as `Lane.GENESIS`) so callers can skip unseeded WPs. Mirror `runtime.next.discovery._wp_lanes_from_states` (`Lane(state.get("lane", Lane.GENESIS))`).
     - `wp_states: Mapping[str, Mapping[str, Any]]`: the reduced per-WP states (lane plus provenance, e.g. `reason_source`), as `_load_wp_states` returns today.
     - `has_log: bool`: whether the declared source holds a status log. It replaces the `has_event_log` / `CanonicalStatusNotFoundError` probes.
     - `weighted_percentage: float | None`: weighted progress to 1 dp, or `None` when it could not be computed.
     - `source: str`: the door's declared source (`StatusReadSource` value), or `"path"` for the adapter.
  3. Wrap the mappings in `types.MappingProxyType` so the value is truly read-only.
  4. Export `__all__ = ["BoardStatus", "board_status_from_surface", "board_status_from_dir"]`.
- **Files**: `src/runtime/next/board_status.py` (new, ~120 lines).
- **Notes**: keep it free of git and filesystem logic beyond the two builders. Layering: `runtime` may import `specify_cli.status` (it already does); do not import from `runtime.next.decision` (avoid a cycle).

### Subtask T002 – Build from a door surface in one read and one reduction

- **Purpose**: `board_status_from_surface(surface: StatusReadSurface) -> BoardStatus` reads the log exactly once (NFR-002).
- **Steps**:
  1. `stream = read_status_stream(surface)` (one read; for a ref surface it reuses the door's prefetched read).
  2. `has_log`:
     - path source: `(surface.path / "status.events.jsonl").is_file()`;
     - ref source: whether the ref read found the file. Use `read_status_text(surface) is not None` only if it does not cost a second subprocess. The prefetched read is reused, but verify by reading `read_surface._ref_text`. If it would re-read, derive `has_log` from the stream plus the prefetched result.
  3. `snapshot = reduce(stream.transitions, stream.annotations)`. For each WP derive `lanes` and `wp_states` from `snapshot.work_packages`.
  4. Weighted progress: `round(compute_weighted_progress(snapshot).percentage, 1)` inside `try/except Exception`. On failure, log a warning (same wording as `decision.py:_compute_wp_progress`) and set `None`.
  5. Corrupt line: today `get_all_wp_lanes` raises `StoreError` (lanes step) while the weighted step logs and omits it (`decision.py:310`). The builder must **raise** on a corrupt log (reading the stream raises), so callers keep their current raise. Document this in the docstring.
- **Files**: `src/runtime/next/board_status.py`.
- **Validation**: a counter test (T005) shows one `read_status_stream` call per build.

### Subtask T003 – Path adapter for outside callers and tests

- **Purpose**: `board_status_from_dir(feature_dir: Path) -> BoardStatus` lets the `status_dir=` keyword of the helpers (WP03) keep working, unchanged, for `workflow.py:1261`, `runtime_bridge_guards.py:102` and existing tests.
- **Steps**:
  1. Read with `specify_cli.status.read_event_stream(feature_dir)`. That is the same parser the door uses for a path source (`read_surface.read_status_stream` path arm).
  2. Then share the reduction code with T002 through one private helper. Do not duplicate the reduction.
  3. `has_log = (feature_dir / "status.events.jsonl").exists()`, matching `has_event_log`.
  4. `source = "path"`.
- **Files**: `src/runtime/next/board_status.py`.
- **Notes**: this adapter is a *path read*. The single-door gate does not scan `read_event_stream`, and this module is not in `DOOR_ONLY_MODULES`. Say so in the docstring: it exists for callers outside the runtime decision path, and its removal is a follow-up.

### Subtask T004 – Parity test over every repo status log [P]

- **Purpose**: prove NFR-001 on real data; this is the guard for every later WP.
- **Steps**:
  1. `tests/runtime/next/test_board_status.py`: parametrize over `sorted(Path("kitty-specs").glob("*/status.events.jsonl"))` (resolve from the repo root via `Path(__file__).parents[3]`). Skip with a clear reason when none are found, which happens in a sparse checkout.
  2. For each log dir `d`:
     - `board_status_from_dir(d).lanes` must equal `get_all_wp_lanes(d)` as a dict;
     - `weighted_percentage` must equal `round(compute_weighted_progress(materialize_snapshot(d)).percentage, 1)`;
     - wrap each in the same exception handling: a corrupt log must raise in both.
  3. Keep it fast. Many logs are small; if the run takes over ~10 s, mark the module `pytest.mark.slow` as well as the fast-tier marker the file convention requires (check `tests/architectural/test_pytest_marker_convention.py`).
- **Files**: `tests/runtime/next/test_board_status.py` (new).

### Subtask T005 – Edge tests [P]

- **Purpose**: pin the board's behaviour where today's readers diverge or fail.
- **Steps** (same test file):
  - no `status.events.jsonl`: `has_log is False`, `lanes == {}`, `weighted_percentage` equals today's value for an empty snapshot;
  - empty file: `has_log is True`, `lanes == {}`;
  - corrupt line: the builder raises `StoreError`, just as `get_all_wp_lanes` does on the same fixture;
  - genesis WP (seeded with no lane): kept as `Lane.GENESIS`;
  - ref surface: build a coordination Mission whose log is committed on the coordination branch with an EMPTY coordination worktree (`tests/runtime/_next_mission_scaffold.scaffold_coord_software_dev`, as in `research/repro/repro_cells.py`). `board_status_from_surface(resolve_status_read(repo, slug))` gives WP01 planned, WP02 for_review and 30.0, with `source == "coord_branch_ref"`;
  - one read: patch `read_status_stream` with a counting pass-through and assert exactly 1 call per build.
- **Files**: `tests/runtime/next/test_board_status.py`.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/runtime/next/test_board_status.py`
- `.venv/bin/ruff check src/runtime/next/board_status.py tests/runtime/next/test_board_status.py`
- `.venv/bin/ruff format --check --force-exclude src/runtime/next/board_status.py tests/runtime/next/test_board_status.py`
- `.venv/bin/mypy src/runtime/next/board_status.py`
- `.venv/bin/python -m pytest -q tests/architectural/test_status_read_single_door.py tests/architectural/test_layer_rules.py` (the new module must not add a bypass or a layer violation)

Record exact commands and counts with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Risks & Mitigations

- **Parity gap on an exotic log.** The test enumerates every real log. If one differs, stop and report it with the log path; do not special-case it.
- **Hidden second read for ref surfaces.** Verify T002 step 2 against `read_surface._ref_text`.

## Review Guidance

- No call site outside the new module changed.
- The parity test really iterates the repo's logs (not a fixture subset), and it fails if the builder is swapped for a different reducer. Mutation-check by temporarily changing the lane default.
- Typed sources: confirm mypy was run, not only pytest.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`), never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
