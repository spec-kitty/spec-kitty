# Tasks: Criterion delivery labels and positive-control review doctrine (#5061)

**Mission**: `criterion-labels-positive-controls-01M3EWRT` · **Planning base / merge target**: `claude/research-squad-remediation-mission-fvdk93`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [quickstart.md](quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Write red-first wiring test for the new tactic (schema, scope edge, prompt render + fetch resolve) | WP01 | |
| T002 | Author `acceptance-criteria-non-vacuity` tactic YAML (labels + three rules) | WP01 | |
| T003 | Add step references from `acceptance-test-first` and `atdd-adversarial-acceptance` | WP01 | [P] |
| T004 | Scope the tactic in the software-dev review action index | WP01 | |
| T005 | Add §4b Criterion Non-Vacuity Check to the review prompt | WP01 | [P] |
| T006 | Regenerate DRG + pack manifest; adjudicate calibrator/reachability drift | WP01 | |
| T007 | Write red-first parser/coverage tests (same-fixture labelled + mis-placed rows; unlabelled twin) | WP02 | |
| T008 | Write live-template substantive-gate tests (scaffold non-substantive; Title/Story-filled control; id set unchanged) | WP02 | |
| T009 | Extend the spec template: FR columns, legend (pointer + marked gloss), `FR-EXAMPLE` example, SC suffix | WP02 | |
| T010 | Add label guidance to the specify prompt | WP02 | [P] |
| T011 | Regenerate specify snapshot baselines and review the diff | WP02 | |
| T012 | NFR-001 corpus check: declared-id sets before/after + bare-prose ratchet | WP02 | |
| T013 | Inventory override-only content for every drifted override (tracer entry) | WP03 | |
| T014 | Resync every override with a built-in counterpart (byte-identical copy) | WP03 | |
| T015 | Add a regression test that counterpart overrides equal their built-in source | WP03 | |
| T016 | Run resolver/runtime/fast-tier tests against the resynced overrides; fix fallout | WP03 | |

## Work Packages

### WP01 — Canonical non-vacuity tactic, DRG wiring, review prompt (Priority P1)

**Prompt**: [tasks/WP01-non-vacuity-tactic-and-review-wiring.md](tasks/WP01-non-vacuity-tactic-and-review-wiring.md) · ~260 lines
**Goal**: one built-in tactic owns the delivery labels, the no-op mark and the three review rules; it is scoped to the
software-dev review action and named in the review prompt. **Requirements**: FR-005, FR-006, FR-007, FR-008.
**Independent test**: `tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py` green; `spec-kitty doctrine regenerate-graph --check` fresh.

Included subtasks:

T001 Write red-first wiring test for the new tactic (WP01)
T002 Author `acceptance-criteria-non-vacuity` tactic YAML (WP01)
T003 Add step references from sibling tactics (WP01)
T004 Scope the tactic in the software-dev review action index (WP01)
T005 Add §4b Criterion Non-Vacuity Check to the review prompt (WP01)
T006 Regenerate DRG + pack manifest; adjudicate drift (WP01)

Dependencies: none. Risks: calibrator shifts derived review edges after an explicit scope entry.

### WP02 — Spec template labels, specify guidance, parser + gate pins (Priority P1)

**Prompt**: [tasks/WP02-spec-template-delivery-labels.md](tasks/WP02-spec-template-delivery-labels.md) · ~280 lines
**Goal**: authors see and fill delivery labels; labelling provably never changes declared ids, coverage, or the
substantive gate. **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-009.
**Independent test**: new tests in `tests/specify_cli/test_requirement_mapping.py` and
`tests/specify_cli/missions/test_substantive_gate_formats.py` green; specify snapshots regenerated.

Included subtasks:

T007 Write red-first parser/coverage tests (WP02)
T008 Write live-template substantive-gate tests (WP02)
T009 Extend the spec template (WP02)
T010 Add label guidance to the specify prompt (WP02)
T011 Regenerate specify snapshot baselines (WP02)
T012 NFR-001 corpus check (WP02)

Dependencies: none (the legend names the tactic id as a string). Parallel with WP01.

### WP03 — Full `.kittify/overrides` resync (Priority P2)

**Prompt**: [tasks/WP03-kittify-overrides-resync.md](tasks/WP03-kittify-overrides-resync.md) · ~220 lines
**Goal**: every `.kittify/overrides/missions/software-dev/` file with a built-in counterpart is byte-identical to it.
**Requirements**: FR-010.
**Independent test**: new override-parity test green; resolver/runtime tests green.

Included subtasks:

T013 Inventory override-only content (WP03)
T014 Resync every counterpart override (WP03)
T015 Add override-parity regression test (WP03)
T016 Run resolver/runtime/fast-tier tests; fix fallout (WP03)

Dependencies: WP01, WP02 (resync must copy the finished built-in tree).

## Parallelization

WP01 ∥ WP02 → WP03. MVP: WP01 (the reviewer-facing doctrine).
