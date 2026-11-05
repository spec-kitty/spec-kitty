# Work Packages: Account for every late-window change before the coordination branch goes

**Inputs**: Design documents from `kitty-specs/fix-7198-late-window-accounting-01M6P3DS/`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Tests**: Red-first is the point of this Mission: each of the two defect shapes gets a failing test
through `_teardown_coordination_triple` before the assertion is widened.

**Organization**: Two work packages. WP01 widens what the assertion proves (the disposition table,
two containment helpers, two refusal kinds) with its red-first cases on both run kinds. WP02 is the
operator surface (per-kind remedies, the re-pinned gate-CAS fixture, docs, changelog) and the
regression sweep that proves the established proofs were not weakened.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: The disposition table (Priority: P0) 🎯 MVP

**Goal**: `assert_late_window_landed` judges every path the late window changed — landed,
landed-by-union, excluded-as-derived, carried-by-target-copy, or refused — on both run kinds.
**Independent Test**: `uv run --frozen pytest tests/coordination/test_projection_teardown.py -q` —
the new status-event and `meta.json` cases teardown cleanly (defect) at the base commit and refuse /
pass correctly after the change; `tests/consolidation/test_late_teardown_projection.py` keeps its
`RECORD_NOT_LANDED` and deletion cases green.
**Prompt**: `/tasks/WP01-disposition-table.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, NFR-001, NFR-002

### Included Subtasks

T001 Write the failing first-run case in `tests/coordination/test_projection_teardown.py`: append an
event to the coordination branch's `status.events.jsonl` from a checkout other than the coordination
worktree, run `_teardown_coordination_triple`, and assert teardown refuses, the branch survives, the
marker is intact and `coord_tip_after_projection` did not advance (RED at base: the branch is
deleted at exit 0 and the event is nowhere on the target).
T002 Write the same shape through a `--resume` state (RED at base, same reason) and the positive
control: with the event also committed on the target branch, both run kinds tear down cleanly.
T003 Write the `meta.json` pair: a coordination-side document the target does not carry refuses;
a coordination-side document the target's copy contains (bake/stamp/flatten) tears down (RED at
base: both tear down, so the first assertion fails).
T004 Replace the two exemptions in
`src/specify_cli/consolidation/bookkeeping_projection.py#assert_late_window_landed` with one
disposition per path: byte-landed, status event containment, derived-snapshot exclusion, document
containment, else refused. Aggregate per class so one refusal names every offending path (bounded to
20); keep the existing deletion refusal first.
T005 Add the module-private helpers `_status_events_missing_from_target` (canonical
`read_event_log_text` on both blobs, ids present in the coordination log but not the target's) and
`_json_document_carried_by` (recursive JSON object containment), both failing closed on unparseable
input, and the two `LateProjectionRefusalKind` members `STATUS_EVENTS_NOT_LANDED` and
`NON_COORDINATION_RECORD_NOT_LANDED`.
T006 Rewrite the assertion's docstring and the two exemption comments as stated rules with their
reason (they are cited by `_post_checkpoint_mission_paths`, which keeps its own projection
exclusion — the assertion is not a projection).

### Implementation Notes

- One owner per rule: `_classify_status_bookkeeping_filename` for "is this a status file",
  `is_coordination_kind_file` for "is this a coordination record", `read_event_log_text` for event
  identity. No new filename list.
- No new git call: the two blobs the loop already reads are the inputs to both helpers.
- The assertion's signature and call site do not change.

### Parallel Opportunities

- T001/T002/T003 (tests) all precede T004–T006 (implementation) and are independent of each other.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Refusing a legitimate resume window: the resume base reaches back to the merge start, so
  merge-authored commits appear in it. They are byte-identical on the target except `meta.json`,
  which document containment covers. The focused suites are the check.

---

## Work Package WP02: Operator surface and regression sweep (Priority: P1)

**Goal**: Each new refusal names the repair that clears it, the docs describe the widened guarantee,
the changelog fragment exists, and the existing suites pass with no weakened assertion.
**Independent Test**: `uv run --frozen pytest tests/consolidation/test_late_teardown_projection.py
tests/consolidation/test_teardown_refusal_resume.py tests/terminus/test_coord_teardown_cas_branch_delete.py -q`
plus `_late_projection_remedy`'s bijection test.
**Prompt**: `/tasks/WP02-operator-surface.md`
**Requirement Refs**: FR-007, FR-009, NFR-003, SC-004

### Included Subtasks

T001 Add the two remedy branches to
`src/specify_cli/consolidation/phase_teardown.py#_late_projection_remedy` (status events: make the
coordination worktree's copy — the union's source — hold the events, or land them on the target;
non-coordination record: land it on the target from the branch, or revert it there), each ending in
`spec-kitty consolidate --resume`.
T002 Extend `_REMEDY_PHRASES` in `tests/consolidation/test_late_teardown_projection.py` for both new
kinds and keep `test_no_two_refusal_kinds_share_a_remedy` green.
T003 Re-pin `test_first_run_does_not_approve_a_tip_that_moved_during_the_projection`: it injects a
`meta.json` commit as an "exempt" path to isolate the gate's compare-and-swap. `meta.json` is judged
now, so inject `status.json` instead (still excluded, by the derived-snapshot rule) and say so in the
docstring. No assertion is weakened.
T004 Update `docs/guides/how-to/recovery/recover-from-interrupted-merge.md`: the late-window section
states what is proved (every change in the window) and what the two new refusals mean.
T005 Add `docs/changelog/unreleased/<pr>.fixed.md` (renamed to the PR number once it exists).
T006 Run the sweep and record the results in the PR body: the five focused suites, ruff, format,
mypy on the two changed modules, `test_no_legacy_terminology.py`, changelog style, docs freshness.

### Implementation Notes

- No new CLI flag, exit code or error code: both kinds ride `COORD_LATE_PROJECTION_REFUSED` and the
  existing exit-1 teardown error.
- The remedy must never repeat the refusal: do not tell an operator to copy `status.events.jsonl`
  onto the target when the union stage will overwrite it on the next run without saying so.

### Parallel Opportunities

- T001/T002 are one seam; T003–T005 are independent of them and of each other.

### Dependencies

- Depends on WP01 (the kinds must exist before a remedy can be written for them).

### Risks & Mitigations

- Doc drift: the recovery guide currently says "coordination record" where the guarantee is now
  "every change in the window"; update the sentence, not the whole page.
