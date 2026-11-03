# Mission Specification: Lifecycle vocabulary parity pin

**Mission Branch**: `issue-6876-lifecycle-vocabulary-parity`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue #6876 — "Frozen contract tools require the lifecycle event-type literals, blocking #6447's import". Operator guidance (batch 10): ground the issue against current `main` first; do not edit `src/specify_cli/status/lifecycle_events.py` (that literal deletion is #6447's parked mission); land only what #6876 can own.

## Intent Summary

- **Actors:** a core maintainer bumping the pinned `spec-kitty-events` release; any agent editing the CLI's lifecycle vocabulary; CI.
- **Trigger:** the twelve lifecycle event-type strings the CLI emits drift from the values `spec_kitty_events` publishes — the exact class #6876 was filed about.
- **Outcome:** core's own fast test suite fails with one named assertion the moment a lifecycle literal stops matching the package constant it claims to mirror, so a drift can no longer reach a consumer as a silent write of a retired event type.
- **Rule that always holds:** `LIFECYCLE_EVENT_TYPES` is exactly the twelve canonical types and `POST_MISSION_LIFECYCLE_EVENT_TYPES` exactly the two post-mission types, and the set stays *narrower* than the package's wide vocabulary (widening it would change which rows repair preserves and which appends the guard refuses).

### Grounding (why this issue's premise no longer holds in core)

`contracts/tools/event_mapping_check.py` and `contracts/tools/citation_check.py` — the two frozen tools whose static `ast` reads made imported constants fail — are **gone from core**. Commit `a212ccdf55` (*"refactor!: remove core's copies of the events service and contracts"*, 2026-11-01) deleted `contracts/` except `fixtures/`, `.github/workflows/contracts.yml`, and the D-9 freeze gate `tests/architectural/test_events_import_frozen.py`. That is ADR 2026-10-29-1 D-9's own exit ("the gate is removed together with `services/` at the cut-over", tracked by #6117), executed.

Consequences this mission is built on:

- No in-core gate requires the twelve names to be declared as literals, so #6447's import is not blocked in core. That deletion is #6447's change, not this mission's.
- The *assertion* those tools carried — that `LIFECYCLE_EVENT_TYPES` matches the canonical lifecycle vocabulary — now has no in-core owner in either direction: the tools left, and no test in `tests/` compares the CLI's twelve values with the package's.
- `spec-kitty-events` carries its own copy of `event_mapping_check.py` whose `DEFAULT_LIFECYCLE_SOURCE` still points at `src/specify_cli/status/lifecycle_events.py`; it only bites if that repo runs it against a core checkout, which is an upstream question (recorded in the issue matrix, not changed here).

So this mission lands the missing *local* assertion (the drift pin), and leaves the import to #6447.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A drifted lifecycle literal fails core CI, not a consumer (Priority: P1)

A maintainer bumps the pinned `spec-kitty-events` release, or an agent edits a lifecycle literal in `status/lifecycle_events.py`. One of the twelve values no longer matches the package constant of the same name. Running the status suite names the drifted constant and its two values, instead of the CLI continuing to emit an event type the package's validator and every downstream reader reject.

**Why this priority**: this is the whole defect class #6876 names. Without it, the copy can drift for releases with nothing in core noticing.

**Independent Test**: change one lifecycle literal in `src/specify_cli/status/lifecycle_events.py` to a plausible sibling value (for example `TASKS_STARTED = "TaskStarted"`), run the new test module, and confirm it fails naming `TASKS_STARTED`; revert and confirm green.

**Acceptance Scenarios**:

1. **Given** the twelve CLI constants and the twelve same-named `spec_kitty_events` constants, **When** each pair is compared, **Then** every pair is equal, and the assertion message names the constant that differs.
2. **Given** a lifecycle literal drifted by one character, **When** the status suite runs, **Then** exactly the parity assertion for that constant fails and the run is red.
3. **Given** the pinned package is installed, **When** the module runs, **Then** it makes no network call and needs no fixture on disk.

---

### User Story 2 - The CLI's lifecycle membership stays exactly twelve and two (Priority: P1)

An agent editing the lifecycle vocabulary (today: deleting the literals for #6447; tomorrow: adding an event type) changes `LIFECYCLE_EVENT_TYPES` or `POST_MISSION_LIFECYCLE_EVENT_TYPES`. The membership is checked against the canonical twelve and the two post-mission types, and against the package's wider vocabulary, so a widening is a red test rather than a silent change to what repair preserves and what the append guard accepts.

**Why this priority**: the membership is the repair-preservation and append-guard set (#6447 triage, 2026-10-19). A change to it is a behaviour change even when every literal still matches the package.

**Independent Test**: temporarily add `MissionReopened`-like extra member to `LIFECYCLE_EVENT_TYPES` (or drop `WP_CREATED`), run the module, and confirm it names the membership mismatch; revert and confirm green.

**Acceptance Scenarios**:

1. **Given** the CLI's `LIFECYCLE_EVENT_TYPES`, **When** it is compared with the twelve canonical values, **Then** the sets are equal.
2. **Given** the CLI's `POST_MISSION_LIFECYCLE_EVENT_TYPES`, **When** it is compared with the two post-mission values, **Then** the sets are equal and both members are also in `LIFECYCLE_EVENT_TYPES`.
3. **Given** the package's own wider vocabulary, **When** the CLI's set is compared with it, **Then** the CLI's set is a strict subset, documented in the test as deliberate rather than an oversight.

---

### Edge Cases

- A lifecycle constant is renamed or removed in a future `spec-kitty-events` release: the parity test fails with the missing attribute named, rather than an `AttributeError` in unrelated code.
- A future edit binds the constants by import (#6447): every assertion keeps holding, because the test compares *values*, never how they are declared. The pin must not require literals — that is what the deleted frozen tools got wrong.
- The package gains a new lifecycle type the CLI does not emit: the parity test stays green (the CLI's set is narrower by design) while the strict-subset assertion documents why.
- The package's wide set shrinks below the CLI's set: the strict-subset assertion fails and asks for a decision instead of silently accepting a widened relationship.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Twelve-constant parity | As a maintainer, I want each of the twelve CLI lifecycle constants compared with the same-named `spec_kitty_events` constant so that a drifted copy fails locally. | High | Open | [build] | no — a test that asserts nothing about a renamed constant would pass; the parity assertion must name the value pair |
| FR-002 | Membership exactness | As an agent editing the vocabulary, I want `LIFECYCLE_EVENT_TYPES` and `POST_MISSION_LIFECYCLE_EVENT_TYPES` compared with the canonical twelve and two so that a membership change is a red test. | High | Open | [build] | no — asserted against the package values, not against the CLI's own constants |
| FR-003 | Narrower-by-design assertion | As a maintainer, I want the CLI's set asserted as a strict subset of the package's wide vocabulary so that the deliberately narrower membership is documented and a widening is caught. | Medium | Open | [build] | no |
| FR-004 | Rename/removal surfaces clearly | As a maintainer bumping the pin, I want a missing package constant to fail naming it so that the diagnosis is immediate. | Medium | Open | [build] | no |
| FR-005 | Declaration-agnostic | As the owner of #6447, I want the pin to pass unchanged when the literals become imports so that the two changes cannot deadlock each other. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fast and hermetic | The new module runs in under 2 seconds, marked `fast`, with no network access, no git repo and no temp-directory fixture. | Performance | High | Open |
| NFR-002 | Deterministic | The module's assertions are order-independent and produce the same result under `-p no:randomly` and with random ordering. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No edit to the vocabulary module | `src/specify_cli/status/lifecycle_events.py` is not modified: deleting its literals is #6447's parked mission, and a comment edit here would collide with it. | Technical | High | Open |
| C-002 | No new gate, no weakened gate | The change adds a test only. No existing check, allowlist, marker or threshold is relaxed, skipped or xfailed. | Technical | High | Open |
| C-003 | Core repository only | `spec-kitty-events`' own copy of `event_mapping_check.py` is out of scope; the observation is recorded, not changed. | Business | Medium | Open |
| C-004 | Proportional review | The change is additive test code with no production behaviour change: one reviewer round, not an adversarial squad. | Business | Low | Open |

### Key Entities

- **Lifecycle vocabulary**: the twelve event-type strings the CLI emits for project/mission/spec/plan/tasks/WP facts, plus the two post-mission types; owned by `specify_cli.status.lifecycle_events`, mirrored from `spec_kitty_events`.
- **Parity pin**: the test that holds the CLI's copy to the package's published values, replacing the assertion the deleted frozen contract tools carried.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Changing any one of the twelve literals in `lifecycle_events.py` makes the new module fail, and the failure message names that constant — proven by a recorded mutation audit on the PR head. — [build] · no-op passable: no
- **SC-002**: With the tree unmodified the module passes in under 2 seconds together with the rest of `tests/status/test_lifecycle_events*.py`. — [build] · no-op passable: no
- **SC-003**: The module still passes after #6447 replaces the twelve literals with imports, verified by applying that import locally and re-running it (not committed). — [ratchet] · no-op passable: no
