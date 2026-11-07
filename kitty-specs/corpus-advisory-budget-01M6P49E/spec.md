# Mission Specification: Corpus advisory suite budget you can defend

**Mission Branch**: `issue-7206-corpus-advisory-budget`
**Created**: 2026-11-05
**Status**: Draft
**Input**: Issue [#7206](https://github.com/spec-kitty/spec-kitty/issues/7206) — "Advisory corpus
suite job runs at its 20-minute budget and times out on unrelated PRs".

**Operator guidance recorded here.** Measure where the budget goes *before* choosing a fix; do not
just raise the number. A budget expiry must not read as a test failure (#4437). Never skip, xfail or
weaken a gate; the advisory lane's selection semantics stay exactly as they are.

## Problem Statement

`.github/workflows/packs.yml` runs the advisory job `built-in-corpus-suite`
(`built-in / -m corpus suite (advisory)`) with `timeout-minutes: 20` and job-level
`continue-on-error: true`. The job executes `pytest -m "corpus and not windows_ci"` over the whole
`tests/` tree (1 624 corpus items from 103 of 4 429 modules).

Measured over 55 recent advisory-job runs on `main` and PR heads, the job's **p95 duration is
20.3 min — 102 % of the cap** (successful runs cluster at 18m47s–19m14s; four runs were killed at
the budget with `The job has exceeded the maximum execution time of 20m0s` and no failing test).
Raw job logs decompose a PR run: collection ≈ 8 min (40 %), the content-addressed wall-clock
policy scan ≈ 3.5 min (18 %, no cache on PR runs by design), test execution ≈ 6.3 min (31 %), job
overhead ≈ 0.5 min. The issue's acceptance criterion is a **p95 of at most 75 % of
`timeout-minutes`**.

Those two fixed costs are not corpus-lane work, and they cannot be removed from this lane without
breaking invariants other guards pin:

- `tests/ci/test_corpus_blocking_home.py` requires the advisory lane to select a corpus test at any
  path in the tree, so a static path shard would silently drop the next corpus module (#3008);
- `tests/ci/test_contracts_routing.py` requires the job to run exactly one pytest invocation, so a
  matrix of shard legs is rejected by the selection model the repository enforces.

Therefore the honest fix is to derive the cap from the measurement using the repository's own
recorded-headroom convention (#5378) and to make a budget expiry legible as **INCOMPLETE**, never
as a passing run and never as a failing test.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The cap is derived from measurement, not picked (Priority: P1)

As a maintainer reading a red advisory check, I want the job's cap to be the one implied by its
measured worst case, so that "ran out of budget" is an anomaly again instead of the normal outcome
of an unrelated PR.

**Why this priority**: This is the issue's acceptance criterion. Without it a lander still cannot
tell a slow advisory lane from a real regression, which is the reported harm.

**Independent Test**: run the extended cap guard against `packs.yml`: with the current
`timeout-minutes: 20` it fails naming the required cap; with the derived cap it passes. The guard
reads only the workflow text, so it runs in the `fast` tier.

**Acceptance Scenarios**:

1. **Given** the advisory job records its measured maximum suite wall-clock above
   `timeout-minutes`, **When** the cap is smaller than `ceil((max + 0:30) × 1.5)`, **Then** the cap
   guard fails naming the job, the cap and the required value.
2. **Given** the derived cap is in place, **When** the guard runs, **Then** it passes, and the
   recorded p95 ÷ cap is at most 0.75 (measured: 20.3 min ÷ 31 min = 65 %).
3. **Given** the guard's own check, **When** the recorded max-suite line is removed or the cap is
   lowered below the required value, **Then** the guard goes red (mutation control, same fixture).

### User Story 2 - A budget expiry reads as INCOMPLETE, not as a failed test (Priority: P2)

As a lander triaging a red advisory check, I want a run that ran out of time to say so in its own
annotation, so that I do not have to open the raw log to discover that no test failed (#4437).

**Why this priority**: The issue's second sentence. Raising the cap removes the common case; the
legible notice removes the diagnostic cost of the remaining ones.

**Independent Test**: read `packs.yml`; the suite step carries its own `timeout-minutes` strictly
below the job cap, and the `if: failure()` advisory notice names the suite as incomplete and
advisory rather than failed.

**Acceptance Scenarios**:

1. **Given** the suite step exceeds its own timeout, **When** the job continues, **Then** the
   advisory notice step runs (it is `if: failure()`, which a step-level timeout reaches) and emits
   a warning stating the corpus suite did not finish and is advisory.
2. **Given** the suite passes, **When** the job finishes, **Then** no notice runs and the job keeps
   `continue-on-error: true`; the advisory result still never blocks `packs-gate` or `router-gate`.
3. **Given** a run is killed by its budget, **When** anyone reads the check, **Then** it is not
   green — green never means "tests passed that did not run".

### User Story 3 - The measurement survives in the repository (Priority: P3)

As the next maintainer touching this lane, I want the decomposition (collection / policy scan /
execution) and the rejected alternatives written where the cap lives, so that the next budget
change starts from data instead of a guess.

**Why this priority**: Without it the rationale decays into folklore and the cap is bumped blindly
next time.

**Independent Test**: read the workflow comment above `timeout-minutes` and the gate-mechanics
reference; both state the measured split, the derivation and why sharding was rejected.

**Acceptance Scenarios**:

1. **Given** the changed workflow, **When** a maintainer reads the job, **Then** the recorded
   headroom line and the rationale comment state the measurement, the formula and the rejected
   alternatives with their pinned guards.
2. **Given** the docs build, **When** the reference page is read, **Then** the advisory corpus
   lane's budget and its derivation are described next to its ownership statement.

### Edge Cases

- **The lane gets slower than the recorded max.** The guard's comment is the single place to
  update: bumping the recorded `max-suite` without bumping the cap fails the guard, and bumping the
  cap without re-recording the max leaves the comment stale but green; the comment states the rule.
- **A future corpus module lands in a new directory.** Unchanged behaviour: the lane still selects
  it by marker over the whole tree (no path shard was introduced), so it still runs.
- **Someone lowers the cap back to 20 "to save runner minutes".** The guard fails; lowering it
  requires re-recording a smaller measured max, which the measurement does not support.
- **The wall-clock policy scan changes shape.** The recorded decomposition names it as the second
  fixed cost; it is a comment, not a gate, so it cannot cause a false red.
- **The job is killed at the job cap anyway (e.g. checkout hangs).** The step-level timeout fires
  first, so the advisory notice runs and the log explains itself.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Cap derived from the recorded measured max | As a maintainer, I want the cap guard to require `ceil((max-suite + 0:30) × 1.5)` for the advisory corpus job, so that the cap cannot be chosen by feel. | High | Open | [build] | no — the guard must fail on the pre-fix `timeout-minutes: 20` (red-first receipt) |
| FR-002 | Recorded headroom line on the job | As a maintainer, I want the advisory job to record `max-suite`, the run window and the formula directly above `timeout-minutes`, so that the derivation is reviewable where the value lives. | High | Open | [build] | no — the pre-fix job has no such line; the guard reports its absence |
| FR-003 | Cap raised to the derived value | As a lander, I want the cap to be at least the guard's required value so that measured p95 ÷ cap ≤ 0.75. | High | Open | [build] | no — 20 does not satisfy the derivation (measured max 19m55s ⇒ required 31) |
| FR-004 | Step-level budget below the job cap | As a lander, I want the suite step to carry its own `timeout-minutes` strictly below the job cap, so that a step timeout can still run the notice step. | Medium | Open | [build] | no — the pre-fix suite step has no step-level timeout |
| FR-005 | Budget expiry notice is legible | As a lander, I want the advisory notice to state that the suite did not finish, is advisory and is not a test failure, so that a timeout is not mistaken for a regression. | Medium | Open | [build] | no — the pre-fix notice only fires on `failure()` and says only "corpus suite failed" |
| FR-006 | Selection semantics unchanged | As a maintainer, I want the marker, the deselect set, `continue-on-error`, the trigger and the `packs-gate.needs` exclusion to be byte-identical, so that no coverage is lost or duplicated. | High | Open | [ratchet] | no — pinned by existing live guards, asserted unchanged here |
| FR-007 | Rationale and rejected alternatives recorded | As the next maintainer, I want the measured decomposition and why sharding was rejected written next to the cap, so that the next budget decision starts from data. | Medium | Open | [build] | no — the pre-fix job has no rationale comment |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Acceptance ratio | Measured p95 duration of the advisory job over the recent run population is at most 0.75 × `timeout-minutes` (20.3 min ÷ 31 min = 65 %). | Performance | High | Open |
| NFR-002 | Headroom | The cap is at least `ceil((measured max suite + 30 s) × 1.5)`, machine-checked by the guard. | Reliability | High | Open |
| NFR-003 | Guard cost | The new/extended guards read workflow text only: no CI run, no pytest collection, `fast` tier, < 2 s. | Performance | Medium | Open |
| NFR-004 | Honest green | No path makes an unfinished or killed advisory run read as passing; `continue-on-error` is unchanged and job-level. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No path shard or matrix | The job keeps exactly one pytest invocation with no positional paths: `tests/ci/test_corpus_blocking_home.py` (tree-wide reach, #3008) and `tests/ci/test_contracts_routing.py` (one invocation) pin it. | Technical | High | Open |
| C-002 | No gate weakened | Marker expression, deselect set, `continue-on-error: true`, the `needs: [changes]` trigger and the exclusion from `packs-gate.needs` are unchanged. | Technical | High | Open |
| C-003 | Reuse the existing convention | The headroom formula is the repository's own (#5378), not a new one invented for this lane. | Technical | Medium | Open |
| C-004 | Advisory posture | The job stays advisory: nothing in this mission may make it block a PR. | Business | High | Open |

### Key Entities

- **Advisory corpus job**: the `built-in-corpus-suite` job in `.github/workflows/packs.yml`, its
  trigger, cap, step budget and notice step.
- **Headroom record**: the structured comment above `timeout-minutes` — measured max suite, run
  window and formula — parsed by the cap guard.
- **Cap guard**: the check that turns the record into a required cap; extended from the nightly and
  module workflows to this job.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: p95 duration of the advisory job ÷ `timeout-minutes` ≤ 0.75 over the measured run
  population (20.3 ÷ 31 = 65 %; pre-fix 20.3 ÷ 20 = 102 %). — [build] · no-op passable: no
- **SC-002**: The cap guard fails on `timeout-minutes: 20` and passes on the derived cap, with a
  mutation control proving both directions. — [build] · no-op passable: no
- **SC-003**: Selection semantics are byte-identical (marker, deselects, `continue-on-error`,
  trigger, `packs-gate.needs` exclusion) and every existing live guard over the lane stays green.
  — [ratchet] · no-op passable: no
- **SC-004**: A budget expiry produces an explicit advisory/INCOMPLETE annotation rather than a
  bare cancellation with no explanation. — [build] · no-op passable: no
