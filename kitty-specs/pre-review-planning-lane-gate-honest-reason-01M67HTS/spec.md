# Mission Specification: An honest pre-review gate reason for a planning-lane WP

**Mission Branch**: `issue-6792-planning-lane-gate-honest-reason`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6792 — "Pre-review gate reports 'no changed files detected' for a planning-lane WP that committed changes (#2741's message acceptance does not hold)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A planning-lane WP's gate record tells the truth (Priority: P1)

A maintainer moves a `planning_artifact` work package from `in_progress` to
`for_review` after committing its deliverables on the mission's target branch.
The pre-review regression gate still skips cheaply (it has no lane diff to
scope), but the reason it records now says *why* — the committed diff was not
inspected because this is a planning-lane WP — instead of claiming that no files
changed, which the commit on disk contradicts.

**Why this priority**: The gate is non-blocking for this case, so nothing is
broken at runtime; what is broken is the audit record. A maintainer reading
`pre_review_gate.reason` after a review cycle is told something false about
their own commit, and #2741 explicitly asked for "committed-diff not inspected"
at minimum. An honest record is the whole value of this mission.

**Independent Test**: In a git repository whose `HEAD` is the mission target
branch and whose only diff against it is empty (the planning-lane shape), move a
`planning_artifact` WP with a committed deliverable to `for_review` and read the
recorded `pre_review_gate` payload: outcome stays `no_coverage`, the reason names
the planning lane and the uninspected committed diff, and no test subprocess runs.

**Acceptance Scenarios**:

1. **Given** a mission whose `lanes.json` puts WP09 in `lane-planning` and whose WP09 frontmatter declares `execution_mode: planning_artifact`, **and** WP09's deliverables are committed on the target branch (clean tree, empty lane diff), **when** WP09 moves to `for_review`, **then** the recorded pre-review verdict is `no_coverage` with a reason that names the planning lane and states the committed diff was not inspected, and that reason does not claim "no changed files detected".
2. **Given** the same mission shape, **when** WP09 moves to `for_review`, **then** no scoped test command runs (the cheap skip is preserved) and the transition is not blocked (`blocked: false`, transition applied).
3. **Given** a code-change WP with an empty lane diff (the control on the same fixture shape), **when** it moves to `for_review`, **then** the reason remains the existing "no changed files detected for this WP" wording — the new reason is reserved for the planning lane.

---

### User Story 2 - The existing non-planning behaviour is untouched (Priority: P2)

Any WP that is not a planning-lane WP keeps exactly the pre-review gate
behaviour it has today: the same empty-diff reason, the same binding resolution,
the same dispatch, the same blocking semantics.

**Why this priority**: The fix must be a narrow reinterpretation of one
short-circuit, not a change to the gate's policy. A regression here would be
worse than the misleading string.

**Independent Test**: The pre-review gate test modules stay green with their
assertions unmodified; a new control assertion on the same fixture proves the old
reason still fires for a non-planning WP.

**Acceptance Scenarios**:

1. **Given** any existing pre-review gate test that asserts an outcome, reason or console line, **when** the suite runs after the change, **then** it passes with no assertion weakened or removed.

---

### Edge Cases

- **Planning lane with genuinely no changes**: the WP is a `planning_artifact` and truly changed nothing. The empty-diff short-circuit fires and the reason is the same planning-lane wording. This is honest: the committed diff was not inspected either way — the gate cannot distinguish "nothing committed" from "committed on the base branch" without a second source of truth, and it does not try.
- **Planning lane WP with dirty (uncommitted) deliverables**: `changed_files` is non-empty, so the gate behaves exactly as today (it scopes and may dispatch). The new reason applies only to the empty-diff short-circuit.
- **`lanes.json` absent or unreadable, frontmatter silent**: classification is unknown; fall back to today's wording. A corrupt `lanes.json` must never turn a non-blocking skip into a crash (the gate's fail-open envelope still owns that).
- **A `code_change` WP that a single-branch mission placed in `lane-planning`**: its frontmatter declares `execution_mode: code_change`, so it keeps today's wording — an explicit code-change mode always wins over lane membership.
- **`--json` and human output**: both surfaces render the same reason (the JSON payload's `pre_review_gate.reason` and the human console warning are built from the same verdict).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Planning-lane empty-diff reason | As a maintainer, I want the gate's recorded reason for a planning-lane WP to name the planning lane and the uninspected committed diff, so that the audit record does not contradict my commit. | High | Open | [build] | no |
| FR-002 | Planning classification is the lane seam's | As a maintainer, I want planning-lane classification to come from the existing execution-mode / lane authorities rather than a second string literal, so that the two cannot drift. | High | Open | [ratchet] | no — asserted by pairing the planning case with the code-change control on one fixture |
| FR-003 | Non-planning empty-diff wording unchanged | As a maintainer, I want every non-planning WP with an empty diff to keep the existing "no changed files detected" reason, so that the change stays scoped to the planning lane. | High | Open | [ratchet] | no — the control arm asserts the old reason, which a blanket rewrite of the message would break |
| FR-004 | Cheap skip and fail-open preserved | As an operator, I want the planning-lane arm to dispatch no gate and run no tests, and to keep the non-blocking outcome, so that an honest reason costs nothing. | High | Open | [ratchet] | no — paired with an assertion that the dispatch path is not reached on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded resolution cost | The classification adds at most one frontmatter scalar read and, only when that scalar is absent, one `lanes.json` read; it spawns no git subprocess and no test run. | Performance | High | Open |
| NFR-002 | No gate weakening | The change adds no skip, xfail, marker or silencing flag, and leaves the terminal/block precedence in `aggregate_verdicts` untouched. | Reliability | High | Open |
| NFR-003 | One reason, every surface | The JSON `pre_review_gate.reason` and the human console line render the identical string, produced once by the verdict. | Operability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Scope is the reason, not the gate policy | Only the empty-diff short-circuit's reason selection changes; binding resolution, scope selection, dispatch, aggregation and the two hard-stops are untouched. | Technical | High | Open |
| C-002 | Canonical seams only | Planning-lane identity is asked through `specify_cli.lanes.compute.is_planning_lane` / `WorkProductKind.PLANNING_ARTIFACT`; no `"lane-planning"` literal is introduced outside those seams. | Technical | High | Open |
| C-003 | No new dependency or config key | The change introduces no new CLI flag, config key, environment variable or dependency; operators get the honest reason by upgrading. | Business | Medium | Open |

### Key Entities

- **Pre-review gate verdict**: the recorded `no_coverage` outcome plus its `reason` string; the only surface this mission changes.
- **Planning-lane WP**: a work package whose `execution_mode` is `planning_artifact`, or whose `lanes.json` lane satisfies `is_planning_lane`, and whose deliverables therefore live on the target branch rather than in a lane worktree.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reproduction test built on a real git repository (HEAD on the target branch, one committed planning-lane deliverable, clean tree) fails on the pre-fix code with the false reason and passes after the fix with the planning-lane reason — [build] · no-op passable: no
- **SC-002**: The three existing pre-review gate test modules under `tests/specify_cli/cli/commands/agent/` and `tests/review/` pass with zero assertion changes — [ratchet] · no-op passable: no
- **SC-003**: On the same fixture, the code-change control arm still records the "no changed files detected" reason — [ratchet] · no-op passable: no
- **SC-004**: The scoped-test dispatch path is never entered for the planning-lane arm (asserted by spying on dispatch), and the transition applies — [ratchet] · no-op passable: no
