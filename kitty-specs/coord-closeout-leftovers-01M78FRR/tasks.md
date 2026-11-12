# Work Packages: Coordination closeout leftovers

**Inputs**: `kitty-specs/coord-closeout-leftovers-01M78FRR/` (spec.md, plan.md, research.md, research/code-grounding.md §1-7, data-model.md, contracts/cli-refusals.md, quickstart.md)
**Prerequisites**: plan.md, spec.md, the four resolved decisions under `decisions/`

**Tests**: required. Every code WP opens with a red-first test commit through the pre-existing entry point (charter Standing Order 4, C-011).

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: unit cells for one clear/restore helper of the PASS anchor | WP01 | |
| T002 | Add the helper to `ConsolidationState` | WP01 | |
| T003 | Route rollback / executor PASS-anchor writes through it | WP01 | |
| T004 | Red: e2e #7491 reproduction + negative control | WP02 | |
| T005 | Persist `coord_tip_after_projection` with the PASS anchor | WP02 | |
| T006 | Resume arm of `_late_window_base` uses the verified tip | WP02 | |
| T007 | Unit cells for the base selection; docstrings | WP02 | |
| T008 | #4380 item 2: truthful marker-kept teardown text | WP02 | |
| T009 | Red: squash refusal names paths and code | WP03 | [P] |
| T010 | `unlanded_projected_paths` with reasons | WP03 | |
| T011 | Gate renders code, paths, per-reason remedy | WP03 | |
| T012 | Stale rollback comment; existing tests follow the new call | WP03 | |
| T013 | Red: `archive reclaim` CLI test (happy path + refusals) | WP04 | [P] |
| T014 | Measure the absorption proof on a realistic fixture (R1) | WP04 | |
| T015 | Reclaim service module | WP04 | |
| T016 | `archive reclaim` subcommand; `archive create` pointer | WP04 | |
| T017 | Gate pin + JSON contract enumeration | WP04 | |
| T018 | Red: abort remedies and a non-consolidate caller | WP05 | |
| T019 | Neutral `RefAdvanceDirtyWorktreeError` text | WP05 | |
| T020 | Callers append their own remedy | WP05 | |
| T021 | Abort kept-record message by outcome | WP05 | |
| T022 | Red: local-mode Next steps for coord and flat lanes | WP06 | [P] |
| T023 | Topology-aware local arm | WP06 | |
| T024 | Controls stay byte-identical | WP06 | |
| T025 | `docs/api/cli-commands.md` rows | WP07 | |
| T026 | Changelog fragments | WP07 | |

---

## Work Package WP01: PASS-anchor pairing (tidy-first) (Priority: P1)

**Goal**: one place clears and restores the reconciliation PASS anchor, behaviour-preserving.
**Independent Test**: new unit cells green; `tests/consolidation/test_single_rollback_authority.py` green.
**Prompt**: `tasks/WP01-pass-anchor-pairing.md`
**Requirement Refs**: FR-004, C-001

### Included Subtasks

T001 Red: unit cells for one clear/restore helper of the PASS anchor (WP01)
T002 Add the helper to `ConsolidationState` (WP01)
T003 Route rollback / executor PASS-anchor writes through it (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Behaviour change sneaking into a tidy step: the existing rollback suites must stay green unchanged.

---

## Work Package WP02: Resume after the kept-only-copy remedy completes (#7491) (Priority: P1)

**Goal**: a resume with a verified landing starts the late window at the verified post-projection tip.
**Independent Test**: the #7491 reproduction resumes to exit 0; the negative control still refuses.
**Prompt**: `tasks/WP02-resume-late-window-base.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-013, C-002

### Included Subtasks

T004 Red: e2e #7491 reproduction + negative control (WP02)
T005 Persist `coord_tip_after_projection` with the PASS anchor and write the landed-coordination ref (WP02)
T006 Resume arm of `_late_window_base` uses the verified tip (WP02)
T007 Unit cells for the base selection; docstrings (WP02)
T008 #4380 item 2: truthful marker-kept teardown text (WP02)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- An unverified tip is unsound: guard with `landing_verified_for_resume` and ancestry.

---

## Work Package WP03: Squash projection refusal names what did not land (#5867) (Priority: P2)

**Goal**: the refusal carries `SQUASH_PROJECTION_NOT_LANDED`, the paths, a reason and remedy each.
**Independent Test**: provoked refusal output lists the path and the code.
**Prompt**: `tasks/WP03-squash-projection-refusal-paths.md`
**Requirement Refs**: FR-009, FR-014, NFR-004

### Included Subtasks

T009 Red: squash refusal names paths and code (WP03)
T010 `unlanded_projected_paths` with reasons (WP03)
T011 Gate renders code, paths, per-reason remedy (WP03)
T012 Stale rollback comment; existing tests follow the new call (WP03)

### Dependencies

- Depends on WP02 (shares `phase_gate.py`).

---

## Work Package WP04: Archive reclaim (#4041) (Priority: P1)

**Goal**: `spec-kitty archive reclaim <mission>` reclaims an archived Mission's coordination triple safely.
**Independent Test**: after reclaim, no coordination worktree, branch or marker remains; each refusal changes nothing.
**Prompt**: `tasks/WP04-archive-reclaim.md`
**Requirement Refs**: FR-005, FR-006, FR-007, FR-008, C-003, NFR-005

### Included Subtasks

T013 Red: `archive reclaim` CLI test (happy path + refusals) (WP04)
T014 Measure the absorption proof on a realistic fixture (R1) (WP04)
T015 Reclaim service module (WP04)
T016 `archive reclaim` subcommand; `archive create` pointer (WP04)
T017 Gate pin + JSON contract enumeration (WP04)

### Dependencies

- Depends on WP02 (reads the landed-coordination ref WP02 writes).

### Risks & Mitigations

- R1 resolved by operator ruling (Decisions 01M78HNKEQPPZMY24JZVJG2MNF, 01M78JC7ZBJM0CY442BKDGBP7V): the proof is the recorded landing (merged_at + live coordination tip at or behind `refs/spec-kitty/landed-coordination/<branch>`), not `is_absorbed`.

---

## Work Package WP05: An `--abort` refusal completes the abort (#7600) (Priority: P2)

**Goal**: no `--abort` refusal tells the operator to resume, except the labelled kept-verified-landing case.
**Independent Test**: dirty-checkout abort prints "re-run `--abort`"; review fast-forward text has no consolidate advice.
**Prompt**: `tasks/WP05-abort-remedies.md`
**Requirement Refs**: FR-011, FR-012

### Included Subtasks

T018 Red: abort remedies and a non-consolidate caller (WP05)
T019 Neutral `RefAdvanceDirtyWorktreeError` text (WP05)
T020 Callers append their own remedy (WP05)
T021 Abort kept-record message by outcome (WP05)

### Dependencies

- Depends on WP01 (shares `rollback.py`).

---

## Work Package WP06: Topology-aware accept "Next steps" (#7599) (Priority: P2)

**Goal**: accept never says "No merge needed" while lanes or a coordination branch remain to consolidate.
**Independent Test**: local-mode accept on a coordination Mission and on a flat lanes Mission prints a consolidate step.
**Prompt**: `tasks/WP06-accept-next-steps.md`
**Requirement Refs**: FR-010

### Included Subtasks

T022 Red: local-mode Next steps for coord and flat lanes (WP06)
T023 Topology-aware local arm (WP06)
T024 Controls stay byte-identical (WP06)

### Dependencies

- None.

---

## Work Package WP07: Reference docs and changelog (Priority: P3)

**Goal**: operator reference and changelog match the shipped behaviour.
**Prompt**: `tasks/WP07-docs-and-changelog.md`
**Requirement Refs**: C-007

### Included Subtasks

T025 `docs/api/cli-commands.md` rows (WP07)
T026 Changelog fragments (WP07)

### Dependencies

- Depends on WP02, WP03, WP04, WP05, WP06.
