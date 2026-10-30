# Mission Specification: Caller-supplied migration actors are not seeds

**Mission Branch**: `issue-6754-migration-actor-cli-spoofing`
**Created**: 2026-10-30
**Status**: Draft
**Input**: spec-kitty/spec-kitty#6754 — "CLI-supplied `migration:` actors are treated as reconstruction seeds (seed spoofing via `--actor` / `--agent`)". Found by the pre-merge adversarial squad on `status-contract-readers-01M5ZAAC` (#6400); pre-existing on `main`, deliberately left there by #6400 and tracked here.

> **Intended distinction (from the issue).** A reconstruction seed is a best-effort
> restatement of history that the log already records; it is produced in-process by a
> migration module and is treated differently from a live decision (it yields to live
> history in the reducer's seed arms, skips `validate_timestamp_continuity`, never opens or
> closes a consolidation work window — FR-011, ADR `2026-09-29-1` — and is exempt from the
> review-exit force-note rule, #5446). The issue's Option 1 is that this capability belong
> to in-process migration writers alone, and that a caller-supplied identity shaped like a
> seed be refused at every free-text boundary. Option 2 (an explicit seed field on the
> events contract) needs a `spec-kitty-events` release and the Java write core
> (spec-kitty-events#92) and is out of scope here.

## Intent Summary (confirmed)

- **Primary actor**: an agent, orchestrator or operator that passes an identity to a status-writing CLI command.
- **Trigger**: a caller-supplied `--actor` (or `--agent`) value that begins with `migration:`.
- **Outcome**: a caller can no longer produce a `migration:` actor. A caller-supplied seed-shaped identity is refused, loudly, before any state changes; the only producers of a `migration:` actor are the in-process migration writers, which bypass the emit shell through the private `specify_cli.status._unsafe` append seam.
- **Rule**: the refusal is a refusal, never a silent rewrite. The value is not stripped, escaped or re-parsed into a live-looking actor, so no log ever records an identity the caller did not write and did not mean.
- **Boundary**: the surfaces that today record a caller-supplied identity *verbatim* (the emit shell's two lenient callers and the hidden `implement --actor`). Explicit `--agent` values keep the operator's recorded 2026-10-29 ruling (strict compact parse: tool `migration`, never a seed), and an identity already recorded as a seed stays a seed when it is re-recorded from the log.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A caller cannot write a reconstruction seed (Priority: P1)

An agent or an external orchestrator runs a status-writing command with `--actor migration:backfill`
(through `agent status emit`, an `orchestrator-api` lifecycle verb, or the compatibility
`implement --actor`). The command refuses, prints why, exits non-zero, and appends nothing.

**Why this priority**: today the same command succeeds and the event it writes is
indistinguishable from a genuine seed, so a live transition can be made to look like
reconstruction — exempt from the review-exit note, invisible to consolidation windows and
skipped by timestamp continuity.

**Independent Test**: on a fixture Mission, invoke each of the three refusing surfaces with
`--actor migration:backfill`; assert exit 1, the canonical refusal message, and a
byte-identical event log.

**Acceptance Scenarios**:

1. **Given** a WP in `planned`, **When** `agent status emit WP01 --to claimed --actor migration:backfill` runs, **Then** it exits 1 with the refusal, and `status.events.jsonl` is unchanged.
2. **Given** the same WP, **When** the same emit runs with `--json`, **Then** the output is the canonical machine error envelope and no event is appended.
3. **Given** a Mission, **When** `orchestrator-api start-implementation`, `start-review`, `transition` or `append-history` runs with `--actor migration:x`, **Then** each returns a failure envelope with `error_code: USAGE_ERROR`, exits 1, and leaves the log and the worktree untouched.
4. **Given** a Mission, **When** `spec-kitty implement WP01 --mission <slug> --actor migration:x` runs, **Then** it exits 1 with the refusal and no claim event, and no lane worktree is created.

---

### User Story 2 - Legitimate reconstruction still works (Priority: P1)

The upgrade migrations that reconstruct history keep writing seeds; a seed already in the log
keeps its seed status when a later command re-records that identity.

**Why this priority**: a fix that broke reconstruction (or that silently demoted a recorded
seed to a live decision) would be worse than the defect.

**Independent Test**: run the three migration backfills on a fixture; assert their actors are
still `migration:` and still reduce as reconstruction seeds. Re-record a recorded seed identity
through `move-task` and `add-history`; assert it stays a seed.

**Acceptance Scenarios**:

1. **Given** a Mission with frontmatter history and no event log, **When** the wp-status backfill runs, **Then** every seed row's actor is `migration:backfill_wp_status` and reduces as a reconstruction seed.
2. **Given** a log whose `for_review -> in_review` claim carries `migration:backfill`, **When** `move-task WP01 --to approved` runs with no `--agent`, **Then** the approval's actor is still the seed and still reduces as one (#6400's pinned behaviour).
3. **Given** the same log, **When** `agent tasks add-history WP01 --note x` runs with no `--agent`, **Then** the recorded seed identity is re-recorded unchanged.

---

### User Story 3 - An explicit `--agent` stays a live actor (Priority: P2)

An agent types `--agent migration:x` on `move-task`, `mark-status`, `add-history` or
`agent action implement/review`. The value is parsed like any compact `tool:model:profile`
string: tool `migration`, not a seed.

**Why this priority**: this is the operator's recorded 2026-10-29 ruling, already implemented
and tested; the mission must not regress it while closing the `--actor` hole, and the
asymmetry between the two options must be deliberate and documented.

**Independent Test**: run each of those commands with `--agent migration:x`; assert the stored
actor is `{tool: "migration", ...}` and is not a seed.

**Acceptance Scenarios**:

1. **Given** a WP in `planned`, **When** `move-task WP01 --to claimed --agent migration:x` runs, **Then** the actor is `{tool: migration, role: implementer, model: x}` and `is_migration_actor` is False.
2. **Given** a WP, **When** `mark-status` or `add-history` runs with `--agent migration:x`, **Then** the actor's tool is `migration`, not a seed.
3. **Given** any of the above, **When** the actor is handed to the shared package reducer, **Then** it does not reduce as a reconstruction seed.

### Edge Cases

- `--actor "migration:"` (empty suffix) is refused: the prefix alone is what classifies a seed.
- `--actor Migration:x` (capitalised) is not a seed today and is not refused; the classification stays the exact, case-sensitive prefix it is now.
- `--actor " migration:x"` (leading space) is not a seed today (the projection does not start with the prefix) and is left alone.
- A refusal happens before any lock, worktree allocation, event append or snapshot materialization; a partial write is never possible.
- A structured (dict) actor whose `tool` starts with `migration:` — the shape #6400 writes — is refused on the same terms as a bare string.
- A legacy log that already contains a caller-produced `migration:` row keeps reading, reducing and displaying exactly as today; the fix changes what can be *written*, never how a stored row is read.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One refusal authority | As a maintainer, I want one canonical predicate and message for "this caller-supplied identity would be recorded as a reconstruction seed" in `status/models.py`, next to the prefix and classification it mirrors, so that no surface invents its own wording or rule. | High | Open | [build] | no — the symbol does not exist on the base |
| FR-002 | `agent status emit --actor` refused | As an operator, I want `agent status emit --actor migration:*` refused before any write, with the canonical message and exit 1 (the machine error envelope under `--json`). | High | Open | [build] | no — the base writes the event and stores the seed |
| FR-003 | orchestrator-api refused | As an external orchestrator, I want `start-implementation`, `start-review`, `transition` and `append-history` to refuse a seed-shaped `--actor` with a failure envelope carrying the already-contracted `error_code: USAGE_ERROR`, before any state change, so no allowlist or contract artifact has to move. | High | Open | [build] | no — the base records the seed on all four |
| FR-004 | `implement --actor` refused | As a compatibility caller, I want the hidden `implement --actor migration:*` refused before workspace allocation and before the claim, so the legacy surface cannot seed either. | High | Open | [build] | no — the base writes a bare-string seed claim |
| FR-005 | Fail-closed lenient builder | As a maintainer, I want `actor_from_option` to refuse a seed-shaped value unless the caller declares the value came from the record (`recorded=True`), so a future caller that forgets the guard is refused instead of spoofed, and the two legitimate recorded-identity callers opt in explicitly. | High | Open | [build] | no — the base keeps the value whole unconditionally |
| FR-006 | Recorded seeds keep their status | As a consumer of the log, I want a `migration:` identity that is re-recorded from the log (a recorded reviewer/agent, not a caller flag) to stay a reconstruction seed, unchanged from today. | High | Open | [ratchet] | yes — paired with FR-002/FR-003 on the same fixtures |
| FR-007 | Explicit `--agent` unchanged | As an agent, I want an explicit `--agent migration:x` on `move-task`, `mark-status`, `add-history` and `agent action implement/review` to keep its recorded behaviour: strict compact parse, tool `migration`, never a seed. | High | Open | [ratchet] | yes — the existing #6400 tests are the pin |
| FR-008 | Migration writers unchanged | As a maintainer, I want the in-process migration writers to keep producing seeds through the private `_unsafe` append seam, with no change to their actor strings or their reducibility. | High | Open | [ratchet] | yes — same fixtures, no diff in their output |
| FR-009 | Refusal/allowed matrix pinned | As a reviewer, I want one matrix test file that drives each refused surface and each allowed form through its real entry point, so the boundary is stated in tests rather than inferred from a diff. | High | Open | [build] | no — the refused arms fail on the base |
| FR-010 | No silent rewrite | As an operator, I want the refusal to leave the value as typed — never stripped of its prefix, escaped or re-parsed into a live-looking actor — so the log never records an identity I did not write. | High | Open | [build] | no — asserts the absence of a rewrite on the base's spoof fixture |
| FR-011 | Docs and changelog | As a maintainer, I want the `--actor` help text, the operator docs that describe seeds, and the `[Unreleased]` changelog entry to state the refusal and its compatibility consequence. | Medium | Open | [build] | no — the base documents the old behaviour |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No partial state | A refused invocation appends 0 events, materializes 0 snapshots, creates 0 worktrees and takes no write lock; the event log is byte-identical after the attempt. | Reliability | High | Open |
| NFR-002 | No extra I/O on the hot path | The guard is a string predicate on an already-parsed option: no file read, no lock, no git call, and no measurable change to a successful command's wall time on the fixture. | Performance | Medium | Open |
| NFR-003 | Coverage | Changed and new lines reach at least 90% diff coverage. | Reliability | High | Open |
| NFR-004 | Quality gates | `ruff check`, `ruff format --check --force-exclude` and `mypy` report 0 issues on touched files; no new `noqa`/`type: ignore`; every touched function stays at complexity 15 or below. | Maintainability | High | Open |
| NFR-005 | One predicate, N call sites | The refusal rule exists once; the surfaces call it. A test fails if a surface hand-rolls its own prefix check. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No events-contract change | No new event field and no wire-shape change; `spec_kitty_events`' decoder and the Java write core are untouched (that is the issue's Option 2, deferred to spec-kitty-events#92). | Technical | High | Open |
| C-002 | No new append path | Writes keep going through the existing status shells (ADR `2026-10-22-1`); the migration writers keep their existing `_unsafe` seam. | Technical | High | Open |
| C-003 | Reader side untouched | `is_migration_actor`, the reducer's seed arms, `validate_timestamp_continuity` and the consolidation work-window rule are not modified; only what a caller may *write* changes. | Technical | High | Open |
| C-004 | System writers out of scope | Consolidation bookkeeping, bootstrap, recovery and attestation actors (non-status writers) are not audited here; a caller-visible `--actor` that reaches a status write is. | Business | Medium | Open |
| C-005 | Compatibility stated | The refusal is a behaviour change for any caller that relied on `--actor migration:*`; the changelog entry names it and the remedy in one line. | Business | High | Open |

### Key Entities

- **Reconstruction seed**: an event row whose actor is shaped like `migration:<module>`; a best-effort restatement of history, never a live decision.
- **Caller-supplied identity**: the value of an `--actor` (or `--agent`) option as typed on the command line.
- **Recorded identity**: an identity read back out of the event log or a dispatch record, re-recorded by a later command without a caller flag.
- **Refusing surfaces**: `agent status emit --actor`, `orchestrator-api {start-implementation,start-review,transition,append-history} --actor`, `implement --actor`.
- **Allowed forms**: explicit `--agent` on `move-task`/`mark-status`/`add-history`/`agent action implement|review`; a recorded identity re-recorded with no caller flag; in-process migration writers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 of the 3 refusing surfaces writes a `migration:` actor; each exits 1 with the canonical message and leaves the event log byte-identical. — [build] · no-op passable: no
- **SC-002**: 100% of the allowed forms keep today's stored actor and seed classification (0 diffs on the existing #6400 fixtures). — [ratchet] · no-op passable: yes
- **SC-003**: The 3 in-process migration writers' seed rows are unchanged in actor and reducibility. — [ratchet] · no-op passable: yes
- **SC-004**: The refusal rule exists in exactly 1 place, with every surface calling it. — [build] · no-op passable: no

## Assumptions

- The three migration writers (`wp_status_backfill`, `backfill_runtime_state`, `verdict_provenance_backfill`) continue to write through `specify_cli.status._unsafe`; if one later routes through the emit shell, it declares `recorded=True` (it is the record) and the refusal does not fire.
- No supported workflow passes `migration:` through a CLI `--actor` today (the issue's grep, re-checked in this Mission's grounding pass and by the test matrix).
- `spec_kitty_events`' `diary._is_reconstruction_seed` keeps keying on the actor prefix for this Mission's lifetime; the explicit-event-field replacement is the deferred Option 2.
