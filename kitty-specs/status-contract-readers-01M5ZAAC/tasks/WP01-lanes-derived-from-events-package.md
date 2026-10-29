---
work_package_id: WP01
title: Lanes derived from the events package
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- SC-004
planning_base_branch: issue-6400-structured-status-actor
merge_target_branch: issue-6400-structured-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6400-structured-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6400-structured-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-contract-readers-01M5ZAAC
base_commit: 1ab6dbf9338a18e12cb33f154b1c39f6745c8f3d
created_at: '2026-10-27T18:47:40.481743+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundations
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status_lanes.py
create_intent:
- tests/status/test_status_lanes_derivation.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status_lanes.py
- tests/status/test_status_lanes_derivation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Lanes derived from the events package

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item before your work is complete and record each change with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Resolves issue #6448.

- `src/specify_cli/status_lanes.py` contains no hand-typed list of lane names (SC-004).
- `PACKAGE_LANES` = every `spec_kitty_events.status.Lane` value, in package order.
- `NON_AUTHORABLE_LANES = frozenset({"genesis"})`, explicit and documented.
- `CANONICAL_LANES` = `PACKAGE_LANES` minus `NON_AUTHORABLE_LANES`, order kept. Its value is byte-identical to today: `("planned","claimed","in_progress","for_review","in_review","approved","done","blocked","canceled")`.
- A test fails if the CLI's own `status.models.Lane` enum and the package enum differ by anything but the read sentinel `uninitialized` (FR-003).
- Every consumer of `CANONICAL_LANES` behaves exactly as before (FR-002).

## Context & Constraints

- Spec: `kitty-specs/status-contract-readers-01M5ZAAC/spec.md` (FR-001..FR-003, SC-004); plan D-1; research §1 (#6448).
- Charter: single canonical authority (the events package owns the lane vocabulary); ATDD-first.
- Keep the name `CANONICAL_LANES` (8 importers, exported from `specify_cli.status`). Do NOT add an alias such as `AUTHORABLE_LANES` pointing at the same tuple (duplicate authority, plan D-1).
- Do NOT add `genesis` to `CANONICAL_LANES`. Consumers that rely on it being absent (triage on #6448):
  - `src/specify_cli/task_metadata_validation.py:269-278` — frontmatter `lane` validation.
  - `src/specify_cli/status/validate.py:116-126` — genesis allowed only as `from_lane`.
  - `src/specify_cli/status/event_log_merge.py:18-33` — forward rank from the declared order minus `blocked`/`canceled`.
  - `src/specify_cli/task_utils/support.py:28` (`LANES`), `src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py:230,354` (must not change: shipped migration, DIRECTIVE_044 drift hash covers only its own module, but its behaviour depends on this tuple, which stays byte-identical).
- Performance: every CLI invocation already loads `spec_kitty_events` (verified: even `spec-kitty --version`), so the import adds no user-facing cost. Library cold imports do pay it; `tests/architectural/test_cold_import_status_boundary.py` forbids only `specify_cli.status*`, `specify_cli.workspace*`, `specify_cli.agent_utils.status*`.
- Do not touch `status/models.py`'s `Lane` enum itself (hundreds of call sites); only pin it with a parity test.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6400-structured-status-actor`
- **Merge target branch**: `issue-6400-structured-status-actor`

Execution worktrees are allocated per computed lane from `lanes.json`. Run:

```bash
spec-kitty agent action implement WP01 --agent claude --mission status-contract-readers-01M5ZAAC
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first derivation and parity tests

- **Purpose**: pin the contract before the change; RED on the base because the new names do not exist.
- **File**: `tests/status/test_status_lanes_derivation.py` (new).
- **Tests** (mark `pytest.mark.fast` like sibling unit tests in `tests/status/`; check `pytest.ini` for the marker set):
  1. `test_package_lanes_mirror_the_events_enum`: `PACKAGE_LANES == tuple(l.value for l in spec_kitty_events.status.Lane)`.
  2. `test_canonical_lanes_are_package_lanes_minus_non_authorable_in_order`: equality with the filtered tuple AND with the literal 9-tuple above (the literal in the test is the ratchet that proves no behaviour change).
  3. `test_genesis_is_the_only_non_authorable_lane`: `NON_AUTHORABLE_LANES == frozenset({"genesis"})` and `"genesis" not in CANONICAL_LANES`.
  4. `test_cli_lane_enum_matches_package_plus_read_sentinel`: `{l.value for l in specify_cli.status.models.Lane} == set(PACKAGE_LANES) | {"uninitialized"}`.
  5. `test_status_lanes_holds_no_hand_typed_lane_list`: AST-parse `status_lanes.py`; assert no `Tuple`/`List`/`Set` literal whose elements are all string constants drawn from the lane values with length ≥ 3. Self-mutation check: the test must fail against the base file (verify by running it before T002; record the red output in the commit message or history note).
- Commit this test alone first: `test(status): pin lane derivation from spec_kitty_events (#6448)`.

### Subtask T002 – Derive the constants

- **File**: `src/specify_cli/status_lanes.py`.
- **Steps**:
  1. `from spec_kitty_events.status import Lane as _PackageLane`.
  2. `PACKAGE_LANES: tuple[str, ...] = tuple(lane.value for lane in _PackageLane)`.
  3. `NON_AUTHORABLE_LANES: frozenset[str] = frozenset({_PackageLane.GENESIS.value})`.
  4. `CANONICAL_LANES: tuple[str, ...] = tuple(lane for lane in PACKAGE_LANES if lane not in NON_AUTHORABLE_LANES)`.
  5. Keep `LANE_ALIASES`, `TERMINAL_LANES` and the rest untouched.
  6. Add the new names to the module's exports if it declares `__all__` (it does not today; do not add one only for this).
- **Validation**: T001 goes green; `python -c "from specify_cli.status_lanes import CANONICAL_LANES; print(CANONICAL_LANES)"` prints the same tuple as before.

### Subtask T003 – Pin the authorable-lane consumers [P]

- **Purpose**: FR-002 ratchet; prove the derivation changed nothing downstream.
- **Steps**: run and record (no edits expected):
  - `tests/specify_cli/status/test_wp_metadata.py` (genesis rejection pins at ~218-231)
  - `tests/status/test_event_log_merge.py`
  - `tests/status/test_models.py`, `tests/status/test_lane_expansion.py`
  - `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py`
  - `tests/specify_cli/core/test_claim_preconditions.py`
- If a consumer has no test pinning genesis exclusion, add one assertion to `tests/status/test_status_lanes_derivation.py` (owned) that calls the consumer, e.g. `event_log_merge`'s rank map has no `genesis` key and ranks `planned < claimed < ... < done`.

### Subtask T004 – Docstrings [P]

- Module docstring of `status_lanes.py`: one paragraph saying the package is the lane authority, `CANONICAL_LANES` is the authorable subset, and why `genesis` is excluded (pre-finalize producer state, never authored).
- Update the comment in `status/event_log_merge.py:23` only if it states the tuple is hand-declared (that file is not owned; a one-line comment edit there is an acceptable out-of-map edit with a rationale in the history note, or leave it if still accurate).

## Test Strategy

```bash
uv run --frozen pytest tests/status/test_status_lanes_derivation.py -q
uv run --frozen pytest tests/specify_cli/status/test_wp_metadata.py tests/status/test_event_log_merge.py tests/status/test_models.py tests/status/test_lane_expansion.py tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py tests/specify_cli/core/test_claim_preconditions.py -q
uv run --frozen pytest tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_shared_package_boundary.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check src/specify_cli/status_lanes.py tests/status/test_status_lanes_derivation.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/status_lanes.py tests/status/test_status_lanes_derivation.py
uv run --frozen mypy src/specify_cli/status_lanes.py
```

## Risks & Mitigations

- A future package release reorders or adds a lane: the parity and literal tests fail loudly, which is the intent; the fix is a deliberate update, not a silent drift.
- Import cycle: `spec_kitty_events` never imports `specify_cli`; safe.

## Review Guidance

- Confirm the T001 commit precedes T002 and was red on the base (history note or commit message shows it).
- Confirm `CANONICAL_LANES` value is byte-identical and no consumer changed.
- Confirm no second name aliases the same tuple.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP01 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T001 --status done`.
