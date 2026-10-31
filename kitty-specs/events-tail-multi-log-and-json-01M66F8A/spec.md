# Mission Specification: events tail — multi-log selector and a meaningful --json

**Mission Branch**: `issue-6611-events-tail-multi-log-and-json`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6611 — "`spec-kitty events tail` covers only status.events.jsonl, and its --json flag has no effect". Guidance from the issue-to-mission delivery run: keep the change proportionate — a subscriber that can follow more than one ledger kind, and a `--json` flag that actually changes the output.

## Context

ADR 2026-10-13-2 D-2 makes the event ledger the publication seam and `events tail`
the local subscriber. Two gaps remain in
`src/specify_cli/cli/commands/events.py` (shell) over
`src/specify_cli/status/tail_reader.py` (core):

1. The command tails only a Mission's `status.events.jsonl`. The other ledger kinds
   the canonical writer names (decision log, run journal, glossary, Op logs, Mission
   v1 events, canonical events) cannot be followed. The #6603 writes gate
   (`tests/architectural/test_event_log_writes_gate.py`, `LOG_FAMILIES`) now names
   that log set, and the parked blocker (spec-kitty/spec-kitty-events#92 type
   registry) is closed, so the selector can list exactly the canonical kinds.
2. Its `--json` option is accepted but unused (`events.py`, `noqa: ARG001`), and no
   human-readable mode exists.

The existing shell docstring already anticipates the selector: the surface
resolution "Returns the directory rather than the file so a later log selector
(#6611) can join another log name onto the same resolution."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Follow any canonical ledger kind (Priority: P1)

As a mission operator watching a run, I want `spec-kitty events tail --mission
<slug> --log <kind>` so that I can follow the decision log, run journal, glossary,
Op lifecycle log, Mission v1 events or the project's canonical events — not only
the status stream.

**Why this priority**: This is the issue's primary gap; ADR D-2's "local
subscriber" cannot subscribe to most of the ledger today.

**Independent Test**: `events tail --mission <slug> --log decisions --once --json`
streams rows from the mission's `decisions.events.jsonl` on its resolved status
surface; today the flag does not exist (red test).

**Acceptance Scenarios**:

1. **Given** a mission with events in its decision log, **When** `events tail
   --mission <slug> --log decisions --once --json`, **Then** the decision rows are
   printed as JSON lines, in file order, from the resolved status surface (the same
   directory resolution as `status`).
2. **Given** a mission with no decision log yet, **When** the same command runs,
   **Then** it prints nothing and exits 0 (wait-for-file semantics, as in
   `event-push-watch-channel-01M1K6W2#FR-008`, carry over).
3. **Given** `--log run` and a mission with run journals under
   `.kittify/runtime/runs/`, **When** the command runs, **Then** the most recently
   modified `run.events.jsonl` belonging to that mission is tailed.
4. **Given** `--log run` and no run journal belonging to the mission, **When** the
   command runs, **Then** it refuses with a typed `run_log_unavailable` stderr
   envelope and non-zero exit (it must not silently tail another mission's run).
5. **Given** an unknown `--log` value, **When** the command runs, **Then** Typer's
   choice validation rejects it as a usage error before any file access.

### User Story 2 - A human-readable default and a meaningful --json (Priority: P2)

As a human operator, I want `events tail` to print readable one-line summaries by
default and `--json` to opt into machine-readable JSON lines, so that the flag
actually changes the output (the `docs query --json` precedent) instead of being a
no-op.

**Why this priority**: The issue's second gap; the flag is dead surface today.

**Independent Test**: the same tail invocation with and without `--json` produces
different output — JSON lines versus one-line human summaries.

**Acceptance Scenarios**:

1. **Given** any selectable log with events, **When** `events tail ... --once`
   (no `--json`), **Then** each event prints as one plain-text line: timestamp,
   event type, compact payload — with no Rich markup/ANSI on stdout.
2. **Given** the same invocation with `--json`, **Then** output is byte-identical
   to today's JSON-lines behaviour, including the reader-injected `tail_offset` /
   `tail_invariant` keys (scripted consumers keep their cursor contract).
3. **Given** a `log_truncated` signal, **When** in human mode, **Then** it prints
   as a visible truncation warning line, not as raw JSON.
4. **Given** human mode, **When** any event prints, **Then** the reader-injected
   `tail_offset`/`tail_invariant` keys are not shown (they are cursor plumbing, not
   content).

### User Story 3 - Resume and refusal semantics carry over to every kind (Priority: P3)

As a scripted subscriber, I want `--from-offset`/`--from-invariant` to validate
against whichever log `--log` selected, so a restart resumes exactly where the
consumer stopped, on any ledger kind.

**Why this priority**: Keeps the existing cursor contract honest as the surface
widens; cheap because the core is path-generic.

**Independent Test**: `--log decisions --from-offset <bad>` refuses with the
existing `invalid_resume_offset` envelope computed against the decision log.

**Acceptance Scenarios**:

1. **Given** a selected log and a valid prior cursor, **When** resuming with
   `--from-offset`/`--from-invariant`, **Then** only post-cursor events stream
   (unchanged core semantics, new path).
2. **Given** a selected log and an out-of-range offset, **When** resuming,
   **Then** the command refuses with `invalid_resume_offset` on stderr and exit 2.
3. **Given** `--from-invariant` without `--from-offset` on any kind, **When** the
   command runs, **Then** the existing `usage_error` refusal fires before any file
   access.

### Edge Cases

- `--log status` (the default): behaviour must be byte-identical to today for
  `--json` invocations — scripted consumers of the status stream must not notice
  the change.
- A coordination-routed mission: `decisions` joins `decisions.events.jsonl` onto
  the same resolved status surface as `status` (both streams are COORD-partition);
  an unmaterialized surface still starts empty rather than erroring
  (`event-push-watch-channel-01M1K6W2#FR-008`).
- Multiple run journals for one mission: the most recently modified one wins;
  state.json rows missing `mission_id` (legacy) fall back to matching
  `mission_slug`; a run dir with an unreadable state.json is skipped, not fatal.
- A missing/unreadable project-level log (glossary, ops, canonical): the poll
  reports `file_present=False` and the stream waits — never a crash.
- Corrupt interior JSON line in any log: the existing core contract applies
  (raise), unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `--log` kind selector | As an operator, I want `--log <kind>` so I can choose which canonical ledger to follow. | High | Open | [build] | no — a table-driven test resolves every kind |
| FR-002 | Per-kind path resolution | As an operator, I want each kind resolved to its canonical path so the tail reads the real ledger. | High | Open | [build] | no — same fixture proves each mapping |
| FR-003 | Latest-run resolution for `run` | As an operator, I want `--log run` to follow my mission's latest run journal so I don't need to know run ids. | High | Open | [build] | no — red on selection and refusal branches |
| FR-004 | Human-readable default output | As a human operator, I want readable one-line summaries by default so I can watch a ledger without parsing JSON. | High | Open | [build] | no — same fixture rendered both ways |
| FR-005 | `--json` JSON-lines mode | As a scripted consumer, I want `--json` to emit the existing JSON-lines envelope so my cursor contract is unchanged. | High | Open | [ratchet] | no — byte-stability pinned against today's output |
| FR-006 | Resume validation per selected log | As a scripted consumer, I want `--from-offset`/`--from-invariant` validated against the selected log. | Medium | Open | [folded] | no — refusal path exercised on a non-status kind |
| FR-007 | Typed refusal for a missing run journal | As an operator, I want a typed `run_log_unavailable` refusal when no run journal belongs to my mission, so a wrong mission never silently shows another's run. | Medium | Open | [build] | no — refusal branch test |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Shell stays loop-free | The CLI shell gains no `while`/`time.sleep`; all polling stays in the core (`tail_reader.py`) — verified by the existing architectural expectation for this module. | Architecture | High | Open |
| NFR-002 | Plain stdout in human mode | Human-mode output uses plain `print` (no Rich markup/ANSI escapes) so piped output is clean, matching the `docs query` JSON contract. | Compatibility | High | Open |
| NFR-003 | Deterministic human rendering | The same event dict always renders to the same line (sorted payload keys, fixed field order), for stable tests and diffs. | Reliability | Medium | Open |
| NFR-004 | No resolution regressions | `--log status --json` output for an existing fixture is byte-identical to the pre-mission output (no reformatting, no reordering). | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Only canonical kinds | The `--log` choices are exactly the ledger kinds the #6603 gate names and the issue lists: `status`, `decisions`, `mission`, `run`, `glossary`, `ops`, `canonical`. No invented kinds; further kinds (ops-index, op-closures, propagation-errors, policy audit, archive registry) are deferred. | Scope | High | Open |
| C-002 | Reuse resolution seams | Path resolution reuses `resolve_surface_dir_or_typed_error`, `resolve_mission_handle`, `locate_project_root` and `mission_event_log_path`-style joins; no new mission-resolution code. | Technical | High | Open |
| C-003 | Terminology canon | `--mission` only (no legacy feature alias); log-kind names follow the writers' own file names. | Governance | High | Open |
| C-004 | Core untouched | `status/tail_reader.py` is not modified except, if strictly needed, additive re-exports; the reader is path-generic already. | Technical | Medium | Open |
| C-005 | Default flip is deliberate | Changing the default output from JSON to human-readable is accepted pre-GA (4.0.0rc) and must be called out in the changelog with before/after. | Business | High | Open |

### Key Entities

- **LogKind**: the selector's enum — one of `status`, `decisions`, `mission`,
  `run`, `glossary`, `ops`, `canonical`. Maps to a path resolution rule
  (mission-scoped via the resolved status surface or feature dir; project-scoped
  under the repo root; run-scoped under `.kittify/runtime/runs/`).
- **TailCursor / PollResult / ResumeRefused**: unchanged core entities
  (`status/tail_reader.py`); the mission only feeds them different paths.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `events tail --mission <slug> --log <kind> --once --json` streams rows for every kind in C-001's list from its canonical path (table-driven; fails on main today — no `--log` flag exists). — [build] · no-op passable: no
- **SC-002**: The same invocation without `--json` prints one plain-text line per event; with `--json` it is byte-identical to main's current output for the status kind. — [build] · no-op passable: no
- **SC-003**: `--log run` selects the most recently modified run journal belonging to the resolved mission and refuses with `run_log_unavailable` when none does. — [build] · no-op passable: no
- **SC-004**: `--from-offset` misuse refuses identically on a non-status kind (`invalid_resume_offset` / `usage_error` envelopes, exit 2). — [folded] · no-op passable: no

## Assumptions

- `ResolvedMission` carries `mission_id` (ULID), `mission_slug` and `feature_dir`
  (verified: `src/specify_cli/context/mission_resolver.py`), which is enough to
  join the glossary log (`.kittify/events/glossary/<mission_id>.events.jsonl`,
  `state/contract.py` pattern) and Mission v1 events
  (`feature_dir/mission-events.jsonl`, `runtime_bridge_composition.py`).
- Run journals live at `.kittify/runtime/runs/<run_id>/run.events.jsonl` with a
  sibling `state.json` whose `MissionRunSnapshot` carries `mission_id`/`mission_slug`
  (optional for legacy runs; slug fallback) — verified in
  `runtime/next/_internal_runtime/engine.py`.
- The Op lifecycle log `kitty-ops/lifecycle.jsonl` is the Op log a subscriber
  follows (`invocation/lifecycle.py`); the index/closure/error siblings stay
  deferred (C-001).
- Pre-GA (4.0.0rc) is the right time to flip the human/JSON default (C-005); the
  issue explicitly asks for the human-readable mode.

## Issue Matrix

| Issue | Scope | Verdict slot | Notes |
|-------|-------|--------------|-------|
| #6611 | in-scope | (WP resolves) | both gaps: multi-log `--log` selector (FR-001/002/003/007) and meaningful `--json` (FR-004/005) |
