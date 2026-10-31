# Work Packages: Model-built payloads for the three post-mission lifecycle events

**Inputs**: Design documents from `kitty-specs/issue-6438-build-lifecycle-payloads-from-models-01M68ZPD/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. This is an ATDD/red-first change: the rejected-payload tests are written and proven red before the emitters change.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`

---

## Work Package WP01: Red-first contract tests for the three emitters (Priority: P0)

**Goal**: A new test module that pins, per emitter, both directions of the contract — the persisted payload is the model dump, and a model-rejected field raises before anything is appended. It must fail on the pre-change code.
**Independent Test**: `uv run pytest tests/specify_cli/status/test_model_built_payloads_6438.py -q` fails on `origin/main` and passes on this branch.
**Prompt**: `/tasks/WP01-red-first-contract-tests.md`
**Requirement Refs**: FR-004, FR-005

### Included Subtasks

T001 Create the module with the shared completed-mission fixture and the WP-dir fixture (both used by the positive and the negative assertion of every emitter)
T002 [P] `MissionReopened`: persisted payload equals `MissionReopenedPayload(...).model_dump(mode="json", exclude_none=False)`; `reason=""` raises `ValidationError` with the log line count unchanged
T003 [P] `FollowUpRecorded`: the same pair for the `commit` and the `pr` discriminator; `recorded_by=""` raises with the log unchanged
T004 [P] `ReviewerSelfApproval`: the same pair; `failure_reason=""` raises with the log unchanged
T005 Prove the module is red against the pre-change emitters and record the failure in `tasks.md`

### Implementation Notes

- Use `pytestmark = pytest.mark.fast`, matching `tests/specify_cli/status/test_post_mission_lifecycle_events.py`.
- Reuse the existing fixture shape: a feature directory with a `meta.json` whose `merged_at` makes `is_mission_completed` true (see `test_post_mission_lifecycle_events.py::_write_meta`).
- Assert on the file, not only the return value: read `mission_event_log_path(feature_dir)` before and after the rejected call and compare line counts. That is the positive control for "nothing was written".
- Do not import a private helper; call the three public emitters.

### Parallel Opportunities

- T002, T003 and T004 touch disjoint test functions in one new file; they may be written together.

### Dependencies

- None (starts the mission).

### Risks & Mitigations

- A negative case the emitter's own guard already rejects (e.g. `follow_up_type="pr"` with no `pr_number`) would pass vacuously before the change. Choose fields only the model constrains.

---

## Work Package WP02: Build the three payloads through their models (Priority: P0)

**Goal**: Each of the three emitters constructs its canonical payload model and persists its JSON dump; guards, envelope, dedup keys and the append primitive stay as they are.
**Independent Test**: WP01's module goes green and the pre-existing emitter suites still pass untouched.
**Prompt**: `/tasks/WP02-build-payloads-through-models.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, C-002, C-004

### Included Subtasks

T006 `emit_mission_reopened`: construct `MissionReopenedPayload` (function-local import from `spec_kitty_events.lifecycle`) after the `#1926` guard
T007 [P] `emit_follow_up_recorded`: construct `FollowUpRecordedPayload` after the `follow_up_type`/reference guards and the `#1926` guard
T008 [P] `emit_reviewer_self_approval`: construct `ReviewerSelfApprovalPayload` (function-local import from `spec_kitty_events.project_lifecycle`)
T009 Run the blast radius: `tests/specify_cli/status/`, the events-import architectural gate, ruff and mypy on the touched files

### Implementation Notes

- Pattern to match, from `emit_wp_created_local` in the same file:
  `payload: dict[str, Any] = Model(**fields).model_dump(mode="json", exclude_none=False)`.
- Keep the assignment annotated `dict[str, Any]`; the dump preserves key order and `None` optionals, so a valid emit serialises exactly as before.
- Do not wrap `ValidationError`, do not add a try/except, do not change `_build_envelope`, the dedup keys or the append call.
- Update the emitter docstrings where they claim the payload is a hand-built dict.

### Parallel Opportunities

- T006, T007 and T008 are three independent function bodies.

### Dependencies

- Depends on WP01 (the tests exist and are red first).

### Risks & Mitigations

- Accidentally reordering or dropping a `None` optional breaks ledger readers → assert key order in WP01's positive test and keep `exclude_none=False`.

---

## Work Package WP03: Record the change for operators (Priority: P1)

**Goal**: An `[Unreleased]` changelog entry that states the user-visible consequence and answers the issue's acceptance items.
**Independent Test**: The entry is present under `[Unreleased]`, cites `(#6438)`, and `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0.
**Prompt**: `/tasks/WP03-changelog-entry.md`
**Requirement Refs**: SC-004

### Included Subtasks

T010 Add the `[Unreleased]` entry to `docs/changelog/CHANGELOG.md`: impact-first bold lead with `(#6438)`, before/after, under 1,200 characters
T011 Run `uv run python -m scripts.docs.check_docs_freshness --ci` and confirm errors=0

### Implementation Notes

- The file is the canonical home; the root `CHANGELOG.md` is a symlink to it. Edit `docs/changelog/CHANGELOG.md` only.
- The entry must name the one user-visible consequence: a lifecycle payload the published contract rejects is now refused at emit time instead of being written.
- Record that the issue's third acceptance item was delivered by #6607, so a reader does not think it is pending.

### Parallel Opportunities

- None; a single authored paragraph.

### Dependencies

- Depends on WP02 (the entry describes the delivered behaviour).

### Risks & Mitigations

- Docs-freshness churn from shared caches → run the check, not a full regenerator.
