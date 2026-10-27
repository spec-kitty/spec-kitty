# Mission Specification: Status contract readers

**Mission Branch**: `issue-6400-structured-status-actor`
**Created**: 2026-10-27
**Status**: Draft
**Input**: Remediation mission M5: #6448 (derive the lane set from the shared events package with an explicit authorable subset) and #6400 (one structured actor shape, carrying the profile and where it came from, on every agent and operator status write path).

## Intent Summary (confirmed)

- **Primary actor**: an agent or operator moving a work package through its lanes, or marking subtasks, with `agent action implement`/`review`, `agent tasks move-task`, `agent tasks mark-status` or a review verdict; and the readers of the event log (gates, the Mission Status Read API, the future Java write core).
- **Trigger**: any status transition or annotation those commands write.
- **Outcome**: every such event names who acted in one structured shape: tool, role, profile, where the profile came from, and model. The lane set the CLI uses is derived from the shared events package, with the lanes an author may write named explicitly.
- **Rule**: a profile taken from the work package's plan (frontmatter) is marked as planned, never presented as the profile that ran, and never makes a self-review look independent.
- **Boundary**: system writers (migrations, consolidation bookkeeping, bootstrap, recovery, attestations) keep their string actors; existing logs stay readable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One actor shape on every agent and operator write (Priority: P1)

An agent implements a work package with `agent action implement WP01 --agent claude`, marks
its subtasks done, hands it to review with `move-task --to for_review`, and a reviewer approves
or rejects it. Every event this writes carries the same structured actor, with the role taken
from the action and the profile filled from the most authoritative source available.

**Why this priority**: consumers (Read API, the lifecycle event schema, the Java write core)
otherwise have to accept two shapes forever, and the profile is lost.

**Independent Test**: run the commands on a fixture Mission whose WP declares `agent_profile`,
read `status.events.jsonl`, assert every new event's actor shape, role, profile and
`profile_source`.

**Acceptance Scenarios**:

1. **Given** a WP with `agent_profile: python-pedro` and no `--profile`, **When** the implementer runs `move-task WP01 --to for_review --agent claude`, **Then** the transition and its paired note carry `{tool: claude, role: implementer, profile: python-pedro, profile_source: wp_frontmatter, model: null}`.
2. **Given** the same WP, **When** `move-task --to approved --agent claude-reviewer --profile reviewer-renata` runs, **Then** the actor is `{tool: claude-reviewer, role: reviewer, profile: reviewer-renata, profile_source: flag, ...}`.
3. **Given** a WP in review, **When** the reviewer rejects it back to `planned` or `in_progress`, **Then** the role is `reviewer`.
4. **Given** `--agent claude::python-pedro`, **When** a transition is written, **Then** `profile_source` is `agent_string`.
5. **Given** a dispatch `--invocation-id`, **When** a transition is written, **Then** `profile_source` is `invocation`.
6. **Given** no flag, no agent-string profile and no frontmatter profile, **When** an event is written, **Then** `profile` and `profile_source` are both `null`.

---

### User Story 2 - mark-status records a structured actor (Priority: P1)

An operator runs `agent tasks mark-status T001 --status done`, optionally naming the agent with
the new `--agent` option.

**Independent Test**: run mark-status with and without `--agent`; read the annotation.

**Acceptance Scenarios**:

1. **Given** no `--agent`, **When** mark-status runs, **Then** the actor is `{tool: user, role: implementer, profile: <WP agent_profile or null>, profile_source: <wp_frontmatter or null>, model: null}`, and the display identity stays `user`.
2. **Given** `--agent claude`, **When** mark-status runs, **Then** `tool` is `claude`.

---

### User Story 3 - Self-review still refused (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an implementer and an approver with the same tool and no asserted profile, both filled from frontmatter, **When** independence is judged, **Then** they are the same identity, exactly as today.
2. **Given** an asserted reviewer profile that differs from the implementer's asserted profile, **When** independence is judged, **Then** the result is unchanged from today.

---

### User Story 4 - Lanes come from the events package (Priority: P2)

A maintainer upgrades `spec-kitty-events`. The CLI's lane set follows it; the lanes an author
may write (frontmatter `lane`, forward-merge order) stay the nine post-genesis lanes in the
declared order, and a lane the package adds or drops is caught by a test rather than drifting.

**Independent Test**: contract tests on the derived constants against `spec_kitty_events.status.Lane`.

**Acceptance Scenarios**:

1. **Given** the installed package, **When** the lane constants load, **Then** the authorable lanes equal the package lanes minus `genesis`, in package order.
2. **Given** frontmatter `lane: genesis`, **When** WP metadata is validated, **Then** it is rejected as today.
3. **Given** the CLI's own `Lane` enum, **When** compared with the package, **Then** they differ only by the read sentinel `uninitialized`.

### Edge Cases

- A legacy log with bare-string actors and 4-key dict actors still reads, reduces and displays exactly as before.
- A stored actor with an unknown extra key, or a non-string value, is still refused by the decoder.
- `profile_source` present without `profile` (or the reverse) is refused when decoding.
- A WP file that cannot be read, or has no `agent_profile`, yields `null` profile, never an error that blocks the transition.
- The `doing` alias still resolves at input boundaries.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Derived lane set | As a maintainer, I want the CLI's lane constants derived from `spec_kitty_events.status.Lane`, with the authorable (non-genesis) lanes named explicitly and in package order, so that the package is the one lane authority. | High | Open | [build] | no — the derivation names do not exist on the base, and a parity test fails if a hand-copied tuple drifts |
| FR-002 | Authorable-lane consumers unchanged | As an operator, I want frontmatter validation, transition validation and event-log merge ordering to keep rejecting or ordering `genesis` exactly as today, so that the derivation changes no behaviour. | High | Open | [ratchet] | yes — paired with FR-001's derivation on the same fixtures |
| FR-003 | Local Lane enum parity | As a maintainer, I want a test that fails when the CLI `Lane` enum and the package enum differ by anything but `uninitialized`. | Medium | Open | [build] | no — fails when a member is added to either side |
| FR-004 | Structured actor with provenance | As a consumer of the event log, I want every actor written by an agent or operator path to be `{tool, role, profile, profile_source, model}`, so that one shape carries who acted and where the profile came from. | High | Open | [build] | no — asserted per write path against today's bare-string output |
| FR-005 | Profile resolution order | As an operator, I want `profile` filled from the dispatch invocation, else `--profile`, else the profile segment of a compact `--agent`, else the WP's `agent_profile`, with `profile_source` set to `invocation`, `flag`, `agent_string` or `wp_frontmatter`, and both `null` when nothing is known. | High | Open | [build] | no — one fixture per source |
| FR-006 | Role from the action | As a reviewer of the log, I want `role` set by the action: `reviewer` for hops into `in_review`, `approved` or `done` and for any hop leaving `in_review` (including rejections), and for verdict notes; `implementer` for every other hop and for implementer notes and subtask marks. | High | Open | [build] | no — rejection and for_review hops assert opposite roles |
| FR-007 | move-task transitions and paired notes | As an operator, I want every `move-task` hop and its paired annotation to carry the structured actor, with or without `--profile`. | High | Open | [build] | no — today writes a bare string |
| FR-008 | mark-status actor and `--agent` | As an operator, I want `mark-status` to record the structured actor and accept an optional `--agent`, defaulting `tool` to `user` and `role` to `implementer`. | High | Open | [build] | no — today writes `"user"` |
| FR-009 | action implement/review annotations | As a consumer, I want the annotations `agent action implement` and `agent action review` write to carry the same structured actor as their transitions. | High | Open | [build] | no — today the annotations carry the bare agent string |
| FR-010 | Review verdict annotation | As a consumer, I want the verdict annotation (`issue-verdict` / review verdict persistence) to carry the structured actor with role `reviewer`. | High | Open | [build] | no — today writes `agent or "operator"` |
| FR-011 | Orchestrator-API and emit paths | As an integrator, I want `orchestrator-api` lifecycle transitions and `agent status emit` to write the structured actor. | Medium | Open | [build] | no — asserted against today's string |
| FR-012 | Readers accept every shape | As a consumer, I want the decoder to accept bare strings, legacy 4-key dicts and the new 5-key dict, and to keep refusing malformed dicts. | High | Open | [build] | no — the base decoder refuses the 5-key dict |
| FR-013 | Frontmatter fill never asserts identity | As an operator, I want `actor_full_identity` to drop a profile whose source is `wp_frontmatter`, so that reviewer≠implementer verdicts are identical to today's. | High | Open | [build] | no — a same-tool pair with different frontmatter-vs-asserted fills is asserted both ways |
| FR-014 | Display identity unchanged | As an operator, I want the snapshot/board actor (`actor_identity_str`) and the claim-matching key to stay the bare tool. | High | Open | [ratchet] | yes — paired with FR-004 fixtures |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra I/O on hot path | Resolving the frontmatter profile reads at most one WP file per command invocation; `move-task` wall time on the test fixture grows by under 5%. | Performance | Medium | Open |
| NFR-002 | Coverage | Changed and new lines reach at least 90% diff coverage. | Reliability | High | Open |
| NFR-003 | Quality gates | `ruff check`, `ruff format --check --force-exclude` and `mypy` report 0 issues on touched files; no new `noqa`/`type: ignore`; every touched function stays at complexity 15 or below. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new persistence path | No new append path; writes keep going through the existing status shells (ADR 2026-10-22-1). | Technical | High | Open |
| C-002 | Wall-clock ordering unchanged | Reducer ordering is untouched (#4941, #6609). | Technical | High | Open |
| C-003 | System writers out of scope | Migration, consolidation-bookkeeping, bootstrap, recovery and attestation actors stay strings; a follow-up issue tracks them. | Business | High | Open |
| C-004 | #6715 compatibility | Identity comparisons stay byte-identical to the base for every existing log; rebase after #6715 if it merges first. | Technical | High | Open |
| C-005 | Read API contract unchanged | `contracts/mission-status` schemas are not changed here; exposing `profile_source` is left to #6409. | Technical | Medium | Open |

### Key Entities

- **Actor**: who wrote an event. `tool` (agent handle, `user` for an unnamed operator), `role` (`implementer` or `reviewer`), `profile`, `profile_source`, `model`.
- **Profile source**: `invocation` (dispatch Op record), `flag` (`--profile`), `agent_string` (compact `--agent` segment), `wp_frontmatter` (planned profile from the WP), or `null`.
- **Authorable lanes**: the package lanes an author may write: every lane but `genesis`, in package order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the fixture Mission, 100% of events written by the seven named write paths carry the five-key actor; 0 bare-string actors. — [build] · no-op passable: no
- **SC-002**: On the fixture Mission whose WP declares a profile, 100% of those events carry a non-null profile with a non-null source. — [build] · no-op passable: no
- **SC-003**: Every legacy event-log fixture in the existing status test suites reduces to the same snapshot as on the base. — [ratchet] · no-op passable: yes
- **SC-004**: The CLI holds 0 hand-typed lane lists in `status_lanes.py`. — [build] · no-op passable: no

## Assumptions

- `spec_kitty_events` keeps `Lane` as an ordered enum in `spec_kitty_events.status` within the pinned major.
- The dispatch resolver can tell an `--invocation-id` binding from a `--profile` one; if not, the plan adds that distinction at the resolver boundary.
- The paired-annotation role for move-task follows its transition's role.
