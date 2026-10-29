# Work Packages: Synthesis record integrity

**Inputs**: Design documents from `kitty-specs/synthesis-record-integrity-01M5ZBC9/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Requested. Every defect is fixed red-first through its pre-existing entry point (DIRECTIVE_034, DIRECTIVE_041).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests: full run keeps legacy edge of non-regenerated tactic/styleguide; dead `PROJECT_*` edge still stripped | WP01 | |
| T002 | Tidy-first: split the applies filter from the dead-edge filter in `_is_legacy_applies` (behaviour-preserving) | WP01 | |
| T003 | Apply the regenerated filter to the applies branch in `merge_project_overlay` and `_graph_delta` | WP01 | |
| T004 | Re-pin the tests that assert today's full-run strip; re-check CLI reconcile/report tests | WP01 | |
| T005 | Pin new reporting: dangling-endpoint conflict for a kept edge, prune behaviour, `reach_only_ids` parity | WP01 | |
| T006 | New module `synthesis_lock.py` (path, timeout constant, errors, re-entrant context manager) + unit tests | WP02 | [P] |
| T007 | Export through `charter.activation.api` | WP02 | |
| T008 | `restamp_bundle_hash` takes the lock | WP02 | |
| T009 | `charter synthesize` / `charter resynthesize` hold the lock over writing runs | WP02 | |
| T010 | CLI tests: held-lock refusal (other thread), positive control, `--json`, dry-run/list-topics, crashed holder | WP02 | |
| T011 | Red-first deterministic race test through `append_synthesized_activations` | WP03 | |
| T012 | Record read-merge-write takes the synthesis lock | WP03 | |
| T013 | Red-first warning test; rewrite `_UNREADABLE_RECORD_WARNING` | WP03 | |
| T014 | Legacy-record path warning test | WP03 | |
| T015 | Update `docs/api/charter-commands.md` (strip scope, lock refusal, record repair) | WP03 | |

---

## Work Package WP01: Full run keeps legacy edges it did not regenerate (Priority: P2)

**Goal**: A full `charter synthesize` strips a legacy `applies` edge only from artifacts it regenerated; the #6443 dead-edge rule is unchanged (#6456).
**Independent Test**: `pytest tests/charter/synthesizer/test_synthesize_reconcile.py tests/charter/synthesizer/test_styleguide_reach_only.py -q`.
**Prompt**: `tasks/WP01-full-run-keeps-legacy-edges.md`
**Requirement Refs**: FR-007, FR-008, FR-009, FR-010, NFR-002, NFR-003, C-005

### Included Subtasks

T001 Red-first tests: full run keeps legacy edge of non-regenerated tactic/styleguide; dead `PROJECT_*` edge still stripped (WP01)
T002 Tidy-first: split the applies filter from the dead-edge filter in `_is_legacy_applies` (WP01)
T003 Apply the regenerated filter to the applies branch in `merge_project_overlay` and `_graph_delta` (WP01)
T004 Re-pin the tests that assert today's full-run strip; re-check CLI reconcile/report tests (WP01)
T005 Pin new reporting: dangling-endpoint conflict, prune behaviour, `reach_only_ids` parity (WP01)

### Implementation Notes

- Commit order: red tests → behaviour-preserving split → fix → re-pins.

### Parallel Opportunities

- Independent of WP02/WP03 (different files).

### Dependencies

- None.

### Risks & Mitigations

- #6443 regression if the filters stay coupled → FR-010 test on a NOT-regenerated `PROJECT_*` directive.

---

## Work Package WP02: Run-wide charter synthesis lock (Priority: P1)

**Goal**: One re-entrant lock per worktree serializes writing synthesis runs and the bundle restamp (#6453).
**Independent Test**: `pytest tests/charter/synthesizer/test_synthesis_lock.py tests/charter/synthesizer/test_synthesis_lock_cli.py -q`.
**Prompt**: `tasks/WP02-run-wide-synthesis-lock.md`
**Requirement Refs**: FR-002, FR-003, FR-011, NFR-001, NFR-003, C-001, C-002, C-006

### Included Subtasks

T006 [P] New module `synthesis_lock.py` + unit tests (WP02)
T007 Export through `charter.activation.api` (WP02)
T008 `restamp_bundle_hash` takes the lock (WP02)
T009 `charter synthesize` / `charter resynthesize` hold the lock over writing runs (WP02)
T010 CLI tests: held-lock refusal, positive control, `--json`, read-only modes, crashed holder (WP02)

### Implementation Notes

- Lock taken right after `assert_charter_yaml_sound`; skipped for read-only modes; acquired via `ExitStack` (no new branch in the `# noqa: C901` bodies).

### Parallel Opportunities

- Can run alongside WP01.

### Dependencies

- None.

### Risks & Mitigations

- Vacuous same-thread tests → hold the lock from another thread; injectable timeout (no 10 s test waits).

---

## Work Package WP03: Created-artifacts record integrity (Priority: P1)

**Goal**: The record's read-merge-write runs under the synthesis lock, and its unreadable warning gives a safe repair step (#6453, #6455).
**Independent Test**: `pytest tests/charter/synthesizer/test_synthesize_activation_append.py -q`.
**Prompt**: `tasks/WP03-record-integrity.md`
**Requirement Refs**: FR-001, FR-004, FR-005, FR-006, NFR-003, C-003, C-004

### Included Subtasks

T011 Red-first deterministic race test through `append_synthesized_activations` (WP03)
T012 Record read-merge-write takes the synthesis lock (WP03)
T013 Red-first warning test; rewrite `_UNREADABLE_RECORD_WARNING` (WP03)
T014 Legacy-record path warning test (WP03)
T015 Update `docs/api/charter-commands.md` (WP03)

### Implementation Notes

- Uses `synthesis_lock` from WP02.

### Parallel Opportunities

- None (depends on WP02).

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- Barrier-based race hangs once the lock works → two-Event handshake with timeouts after the fix.
