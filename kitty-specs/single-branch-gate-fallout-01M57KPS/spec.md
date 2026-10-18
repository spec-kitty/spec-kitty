# Mission Specification: single_branch gate fallout (#6370, #6369)

**Mission Branch**: `issue-6370-single-branch-gate-fallout`
**Created**: 2026-10-18
**Status**: Draft
**Input**: Operator brief: P0 nightly reds #6370 and #6369 (scenario 6 only), both fallout of the fail-closed single_branch evidence/independence gate shipped in #5939 (`f449e1a754`, `6af1d49bf9`, `efb63477`). The gate is intended and is not weakened.

## Context

#5939 added a fail-closed single_branch evidence and independence gate, in two places:

- **Consolidate claim-time axis** (`consolidation/reconciliation.py::_single_branch_evidence_refusal`). It refuses with `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` when `lanes.json` records no planning commit, `SINGLE_BRANCH_IMPLEMENTATION_MISSING` when no commit touches the WP's `owned_files`, and `SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT` when the implementer and the approver are the same actor.
- **Move-side gate** (`cli/commands/agent/tasks_move_task.py::_mt_require_single_branch_implementation`).

Two consumers outside the per-PR matrix were not updated with it and first went red on the 2026-10-18 nightly (run 39093948207):

- **#6370**: `tests/specify_cli/test_specify_topology_flag.py::test_single_branch_mission_survives_implement_and_merge_end_to_end` is a root-level, out-of-matrix e2e. Its fixture writes `lanes.json` with `planning_commit_sha=None`, and its seed records the same actor (`seed`) as implementer and approver.
- **#6369 scenario 6**: `tests/scenarios/mission/single-branch.feature`, "A work package with no committed work cannot go to review", asserts the output mentions "no implementation commit". The move-side gate now refuses that move *before* `lanes/for_review_gate.py` runs, with different wording ("Refusing to move WP01 into review without a committed implementation…"). The refusal is correct; only its words drifted from the sibling gates.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The single_branch e2e proves the supported path again (Priority: P1)

A maintainer relies on the nightly `specify-cli-out-of-matrix` lane. The single_branch implement + consolidate e2e must build its mission the way the supported flow does, so that its red/green tracks the product and not a stale fixture.

**Why this priority**: P0 red nightly. Red CI means no release.

**Independent Test**: run the one test. It passes, and consolidate still refuses when the fixture is reverted to either stale shape.

**Acceptance Scenarios**:

1. **Given** the fixture records the planning commit that finalize-tasks would record, and distinct implementer and reviewer actors, **When** the e2e consolidates with `SQUASH`, **Then** it lands both WPs and the four observable facts hold.
2. **Given** the fixture records no planning commit, **When** it consolidates, **Then** the claim refuses with `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` (the gate is unchanged).

### User Story 2 - The refusal for a review without committed work reads the same everywhere (Priority: P1)

A developer on a single_branch Mission who asks for review with no committed work gets a refusal. It names the missing implementation commit in the same words that `for_review_gate` and the consolidate axis use.

**Why this priority**: P0 red nightly (#6369, scenario 6). Consistent wording is also what scenarios and operators key on.

**Independent Test**: on a single_branch mission with ticked subtasks and no implementation commit, run `move-task WP01 --to for_review --json`. The command fails, its output contains "no implementation commit", and the WP stays `in_progress`.

**Acceptance Scenarios**:

1. **Given** the scenario-6 arrangement, **When** `move-task --to for_review` runs, **Then** it fails, mentions "no implementation commit", and the WP stays in `in_progress`.
2. **Given** committed work in the WP's `owned_files`, **When** the same move runs, **Then** it succeeds without `--force` (scenario 2 unchanged).

### Edge Cases

- `agent status emit --to for_review` (scenario 3) does not go through the move-side gate. It still refuses through `for_review_gate` with "no implementation commit".
- The `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` and `SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE` move-side refusals keep their wording. Neither is asserted by any scenario.
- The error code `SINGLE_BRANCH_IMPLEMENTATION_MISSING` is unchanged.

## Decision: scenario 6 (stable code vs wording)

The brief preferred asserting the stable error code. The code cannot be asserted from the scenario without a contract change. The non-owned `move-task --json` envelope prints only `{"error": <message>}`, and `test_context_error_envelope_is_opt_in` (`tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py`) pins `error_code` as opt-in to the owned-checkout path. Asserting the code would mean widening that pinned envelope for every `ActionContextError` refusal of move-task, which is a broader contract change than this P0 fallout warrants.

**Chosen: align the move-side refusal wording** with `for_review_gate` ("… cannot move to for_review: no implementation commit …") and with the consolidate axis ("… no implementation commit touching its owned_files …"). That unifies the three gates on one phrase. The scenario and its absorption-ledger note (which already promises the phrase) stay unchanged, and the code stays where it is. Decision moment `01M57KRSRE76R1AW5YEAFKMP8C`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | e2e fixture records the planning commit | As a maintainer, I want `_finalize_single_branch_lanes` to record the planning commit finalize-tasks records, so that the evidence window is computable. | High | Open | [build] | no — the test is red on main with `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` |
| FR-002 | e2e seed uses distinct implementer and reviewer | As a maintainer, I want `_seed_wp_approved` to record a distinct implementer and reviewer, so that the independence axis can confirm the review. | High | Open | [build] | no — once FR-001 is in, the test refuses with `SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT` |
| FR-003 | move-side refusal names the missing implementation commit | As a developer, I want the single_branch move-side refusal to say "no implementation commit" like its sibling gates, so that the wording is one vocabulary across the gates. | High | Open | [build] | no — scenario 6 is red on main; a focused unit test pins the phrase |
| FR-004 | audit other #5939 consumers | As a maintainer, I want every other test or scenario that #5939 left stale found and fixed or reported, so that the next nightly is not red again for the same cause. | Medium | Open | [folded] | yes — an empty audit finding is a valid outcome |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Lint/type clean | `ruff check`, `ruff format --check --force-exclude` and `mypy` report 0 issues on every changed file. | Quality | High | Open |
| NFR-002 | Targeted test policy | Only the targeted test files plus `make test-fast` are run. No `make test-full` and no full `tests/architectural/` sweep. | Process | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Gate not weakened | No change to the decision logic, codes or fail-closed behavior of the #5939 axis or the move-side gate; only the human message text of `SINGLE_BRANCH_IMPLEMENTATION_MISSING` changes. | Technical | High | Open |
| C-002 | Envelope unchanged | The non-owned move-task JSON envelope stays `{"error": ...}` (pinned by `test_context_error_envelope_is_opt_in`). | Technical | High | Open |
| C-003 | Scenario 6 only | #6369 scenarios 1–5 (charter / upgrade) are out of scope. | Business | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_single_branch_mission_survives_implement_and_merge_end_to_end` passes locally — [build] · no-op passable: no
- **SC-002**: The shell port of scenario 6 shows a failed move whose output contains "no implementation commit", with the WP left `in_progress`. A unit test pins the phrase — [build] · no-op passable: no
- **SC-003**: The existing #5939 guard tests (`tests/integration/test_5939_single_branch_autowalk_guards.py`, `tests/consolidation/test_single_branch_evidence_axis.py`) stay green — [ratchet] · no-op passable: yes
