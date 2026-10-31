# Work Packages: Opaque declared-command failure identity (#6751)

**Inputs**: `kitty-specs/opaque-failure-identity-01M67HQA/` — spec.md, plan.md, research.md, data-model.md, traces/
**Prerequisites**: spec.md, plan.md

**Tests**: required. Red-first per charter SO #4 / C-011: WP01 commits its failing repro (the issue's counterexample) before the fix, and shows it red on the planning base.

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`). Each WP has its own prompt in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first repro: the issue's counterexample through `parse_results` → `_classify_current_failures` returns `no_new_failures` on the base tree; same fixture carries the identical-opaque positive control and the exit-status-mismatch case | WP01 | |
| T002 | `BaselineFailure` gains `opaque` + `exit_code` (defaulted, additively serialized); `OPAQUE_FAILURE_TEST_ID` moves beside it as the single canonical constant; `from_dict` infers `opaque` for pre-change artifacts | WP01 | |
| T003 | `_whole_run_failure` carries the run's exit status and the opaque marker; `parse_results`/`_whole_run_failure` consume the canonical constant; `test_scope_source.py` assertions updated | WP01 | |
| T004 | `diff_baseline` matches opaque failures on the bound `(exit status, summary)` identity, never across named/opaque; named and JUnit behaviour unchanged; legacy-artifact test | WP01 | |
| T005 | `GateVerdict.candidate_exit_code`; `_classify_current_failures` records it and gives `no_new_failures` a baseline-relative reason; `_evaluate_via_scope_source` passes the observed `returncode` | WP02 | |
| T006 | Renderer appends the reason to the existing `no_new_failures` dim line only when present; parity fixtures keep their exact metadata and console string | WP02 | |
| T007 | Integration tests through `evaluate_with_scope(scope_source=…)`: nonzero candidate with only pre-existing failures → `no_new_failures` + exit status + reason; clean exit-0 → `no_new_failures` + exit 0; opaque mismatch → `new_failures` | WP02 | |

---

## Work Package WP01: A bounded opaque failure identity (Priority: P1)

**Goal**: An opaque declared-command failure carries its observed exit status and summary
as its comparable identity, and `diff_baseline` treats two opaque failures as the same
failure only when both match — named failures keep their existing name-based behaviour.
**Independent Test**: `tests/review/test_opaque_failure_identity.py` — the issue's
counterexample returns `new_failures` while the identical-opaque fixture returns
`no_new_failures`, both built from one fixture table.
**Prompt**: `tasks/WP01-bounded-opaque-identity.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-003, C-002, SC-001, SC-002, SC-003, SC-005

### Included Subtasks

T001 Red-first repro + positive controls (WP01)
T002 `BaselineFailure` identity fields + canonical constant (WP01)
T003 `_whole_run_failure` carries exit status (WP01)
T004 `diff_baseline` bound-identity comparison (WP01)

### Dependencies

- None.

### Risks & Mitigations

- `from_dict` must never raise for a pre-change artifact (NFR-003): read with `data.get`,
  infer `opaque` from the sentinel name, and let `exit_code` default to `None`.
- The named-failure path must be byte-identical: the comparison keeps the incumbent
  name-set semantics for non-opaque entries; a mixed named/opaque pair never matches.

---

## Work Package WP02: The verdict states what the candidate command did (Priority: P2)

**Goal**: A verdict reached from a real declared-command run carries the candidate's
observed exit status, and a baseline-relative `no_new_failures` says so in its reason —
without adding a metadata key the parity oracle would reject.
**Independent Test**: `tests/review/test_verdict_candidate_exit.py` drives
`evaluate_with_scope(scope_source=…)` end to end: nonzero-with-pre-existing → exit status
recorded and reason present; clean exit 0 → exit 0 recorded; opaque mismatch →
`new_failures`.
**Prompt**: `tasks/WP02-verdict-candidate-exit.md`
**Requirement Refs**: FR-004, C-001, SC-004

### Included Subtasks

T005 Verdict exit status + baseline-relative reason (WP02)
T006 Renderer + parity-oracle preservation (WP02)
T007 Integration tests through the gate (WP02)

### Dependencies

- WP01 (the classifier must distinguish opaque identities before the verdict can report
  the distinction honestly).

### Risks & Mitigations

- `tests/review/test_transition_gate_parity.py` asserts exact metadata equality and the
  exact console string against base-captured fixtures: never add a metadata key, and
  append the reason only when it is present (a fixture verdict has `reason: null`).
- The opt-in block predicate and the `NEW_FAILURES` render path are untouched (C-001):
  assert both in the WP02 tests.
