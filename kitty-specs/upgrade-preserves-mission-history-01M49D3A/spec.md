# Mission Specification: Upgrade must not rewrite healthy Mission history

**Mission Branch**: `issue-5811-upgrade-preserves-mission-history`
**Created**: 2026-10-06
**Status**: Draft
**Input**: Issues #5811 (P0) and #5812, with operator rulings of 2026-10-06 (see Intent Summary).

## Intent Summary (confirmed 2026-10-06)

A maintainer runs `spec-kitty upgrade --yes` on a project that is already up to date. Afterwards `git status` is clean: no Mission's status event log, status snapshot or directory has been touched. The mission-state repair runs only when a maintainer explicitly asks for it with `spec-kitty doctor mission-state --fix`, and even then it leaves a healthy event log byte-identical.

**Invariant:** the append-only `status.events.jsonl` of a Mission is never reshaped or re-ordered as a side effect of maintenance.

Operator rulings:
1. `upgrade` stops running the Team Kitty mission-state repair. It reports the blockers and points to `doctor mission-state --fix`, and it evaluates the gate only when drain is on, because Team Kitty is no longer supported (ADR `2026-10-06-1`). `--yes` stays non-interactive. This partly reverses the #4775 decision that `--yes` consents to the repair, and an ADR amendment records it.
2. #5812, residue directories classified as Missions, is part of this Mission as its own work package.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Routine upgrade leaves history untouched (Priority: P1)

A maintainer of a repository with many historical Missions runs `spec-kitty upgrade --yes` as routine maintenance. Some Missions carry Team Kitty readiness blockers. The upgrade finishes and changes no file under `kitty-specs/`.

**Why this priority**: This is the P0 defect (#5811). Today a no-op upgrade rewrote 560 authoritative event logs and reported success.

**Independent Test**: Through the CLI, against a fixture repository with committed, writer-shaped historical Missions and at least one blocker, run `upgrade --yes` and compare every pre-existing file byte for byte.

**Acceptance Scenarios**:

1. **Given** a repository with writer-shaped historical Missions and one Mission that carries a blocker, **When** the maintainer runs `spec-kitty upgrade --yes`, **Then** every `status.events.jsonl` and `status.json` is byte-identical and no file under `kitty-specs/` is created.
2. **Given** drain is on and blockers exist, **When** the maintainer runs `spec-kitty upgrade --yes`, **Then** the output names the blocker count, the finding codes and the command `spec-kitty doctor mission-state --fix`, and no Mission file changes.
3. **Given** drain is off, **When** the maintainer runs `spec-kitty upgrade --yes`, **Then** mission-state readiness is not evaluated at all (no readiness check runs) and the output contains no mission-state panel.
4. **Given** drain is on and blockers exist, **When** the maintainer runs `spec-kitty upgrade --yes`, **Then** the exit code is 0 and no `.kittify/mission-state-audit/` manifest is written.
5. **Given** `auto_commit` is enabled, **When** the maintainer runs `spec-kitty upgrade --yes`, **Then** the upgrade commit contains no `kitty-specs/` path.

---

### User Story 2 - Explicit repair is a no-op on healthy history (Priority: P1)

A maintainer runs `spec-kitty doctor mission-state --fix` on purpose. Missions whose logs were written by the current status writer come out byte-identical, in their original row order. Only Missions that really need repair change, and only their snapshots are rewritten.

**Why this priority**: The repair is shared by the doctor path. Unless its row shape and ordering match the live writer, the explicit repair keeps doing the same damage.

**Independent Test**: Generate rows from every `StatusEvent` field combination, run them through the repair's canonicalization, and compare the serialized bytes. Run the doctor fix on a healthy fixture and compare the files.

**Acceptance Scenarios**:

1. **Given** a log whose rows `StatusEvent.to_dict()` produced, without `reason_source` or `review_result` keys, **When** the repair runs, **Then** the log is byte-identical.
2. **Given** a row with a populated `reason_source`, **When** the repair runs, **Then** the value is preserved.
3. **Given** a log whose physical row order is not sorted by timestamp, **When** the repair runs, **Then** the row order is unchanged.
4. **Given** a Mission whose log the repair did not change but whose `status.json` differs from a fresh materialization, **When** the repair runs, **Then** `status.json` is left as is and the drift is reported.
4a. **Given** a Mission whose tracked state has no `lanes.json` or no `status.json` (for example a coordination-topology Mission whose primary checkout carries neither), **When** the repair runs, **Then** neither file is created.
5. **Given** a log with a duplicate event, a corrupt row or a legacy lane alias, **When** the repair runs, **Then** it still deduplicates, quarantines and normalizes as it does today.
6. **Given** a log with preserved non-lane rows (authoritative non-lane event types, annotation rows), **When** the repair runs, **Then** those rows are byte-preserved; canonicalization only ever reshapes lane rows.

---

### User Story 3 - Residue directories are not Missions (Priority: P2)

A repository has a `kitty-specs/<name>/` directory that holds only gitignored or untracked residue, for example a leftover lock file. The audit does not treat it as a Mission: it raises no `IDENTITY_MISSING` blocker and mints no `meta.json` or status files into it.

**Why this priority**: This is #5812. In the dogfooding repository it produced the blockers that triggered the repo-wide rewrite.

**Independent Test**: Through the CLI, create a residue-only directory beside a real Mission and run the audit and the doctor fix; check the findings and the untracked files.

**Acceptance Scenarios**:

1. **Given** `kitty-specs/ghost-01ABCDEF/` that holds only a gitignored lock file, **When** the mission-state audit runs, **Then** it reports no `IDENTITY_MISSING` blocker for it and lists it as non-blocking residue.
2. **Given** the same directory, **When** `doctor mission-state --fix` runs, **Then** no `meta.json`, `status.json`, `lanes.json` or event log is created in it.
3. **Given** a real legacy Mission (a tracked `spec.md`, tasks or event log but no identity), **When** `doctor mission-state --fix` runs, **Then** its identity is still backfilled.

---

### User Story 4 - Honest repair outcome (Priority: P2)

When the repair cannot process some Missions, its summary names each of them with the reason and does not claim the blockers are cleared.

**Why this priority**: The observed run reported `errors=52` next to "blockers cleared".

**Independent Test**: Run the repair on a fixture with one Mission whose log has a row that cannot be canonicalized; check the summary and the exit status.

**Acceptance Scenarios**:

1. **Given** a Mission with a row missing `to_lane`, **When** the repair runs, **Then** the summary names that Mission and the reason, does not report the blockers as cleared, and the command exits non-zero.

### Edge Cases

- A row that `StatusEvent` gains in a future release: the parity test is driven from the field list, so a new field cannot silently diverge.
- Mixed timestamp spellings (`Z`, `+00:00`, fractional seconds) in one log: no ordering is applied, so lexical comparison does not matter.
- A directory with a tracked `spec.md` or `meta.json` but no event log is a real Mission, not residue (the existing population rule "`spec.md` or `meta.json`" stays the single rule; "tracked" is part of the predicate).
- `upgrade --dry-run` keeps reporting without mutating anything.
- A project with `auto_commit` enabled: since `upgrade` no longer writes Mission files, nothing of this kind can be committed.

## Domain Language

| Canonical term | Meaning | Avoid |
|---|---|---|
| Mission | A directory under `kitty-specs/` with tracked Mission artifacts | feature |
| Residue directory | A `kitty-specs/` directory holding only untracked or gitignored files | ghost Mission, orphan Mission |
| Mission-state repair | The canonicalization performed by `repair_repo` | sync, migration (when meaning the repair) |
| Writer-shaped row | An event-log row byte-identical to what `StatusEvent.to_dict()` serializes | canonical row (ambiguous) |
| Drain | The hosted posture under which Team Kitty surfaces are shown (ADR `2026-10-06-1`) | sync |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Upgrade never repairs | As a maintainer, I want `spec-kitty upgrade`, including `--yes`, never to run the mission-state repair and never to change a file under `kitty-specs/`, so that routine maintenance cannot rewrite history. | High | Open | [build] | no |
| FR-002 | Upgrade reports blockers only under drain | As a maintainer, I want `upgrade` to evaluate the Team Kitty mission-state gate only when drain is on, and then to report the blocker count, finding codes and `spec-kitty doctor mission-state --fix`, so that an unsupported product never changes my repository. | High | Open | [build] | no |
| FR-003 | Writer and repair row shape parity | As a maintainer, I want every row that `StatusEvent.to_dict()` can produce to serialize byte-identically after the repair's canonicalization, checked over every subset of optional `StatusEvent` fields generated from the field list (the existing `test_canonical_row_allowlist_covers_every_status_event_field` stays green), with structured actors and populated `reason_source`, `review_result` and `mission_id` still preserved, so that healthy history is never reshaped. | High | Open | [build] | no |
| FR-004 | No physical re-ordering | As a maintainer, I want the repair to keep the existing physical row order of `status.events.jsonl`, so that the append-only record stays an append-order record. | High | Open | [build] | no |
| FR-005 | Snapshot rewrite only with a changed log | As a maintainer, I want the repair to rewrite `status.json` only for a Mission whose event log it changed, never to create a `status.json` or `lanes.json` that the Mission's tracked state lacks, and to report other snapshot drift, so that derived files do not churn silently. | High | Open | [build] | no |
| FR-006 | Residue directories are not Missions | As a maintainer, I want a `kitty-specs/` directory with no tracked Mission artifacts to raise no `IDENTITY_MISSING` blocker, to get no `meta.json` or status files, and to be reported as non-blocking residue, decided by one shared is-a-Mission predicate that both the mission-state audit and the repair use, so that leftovers are not turned into fake Missions (#5812). | High | Open | [build] | no |
| FR-007 | Honest repair outcome | As a maintainer, I want a repair that could not process some Missions to name each of them with the reason and not to report the blockers as cleared, and to exit non-zero, so that partial success is never shown as success. | Medium | Open | [build] | no |
| FR-008 | Doctor repair keeps its healing | As a maintainer, I want `doctor mission-state --fix` to keep deduplicating events, quarantining corrupt rows, normalizing legacy lane aliases, rebuilding wedged lanes and backfilling identity for real legacy Missions, so that genuinely broken Missions are still repaired. | High | Open | [ratchet] | yes — paired with the existing repair suites (`test_dup_key_repair.py`, `test_mission_state_repair_fidelity_e2e.py`, `test_mission_state_lanes_rebuild.py`) as the positive control |
| FR-009 | Red-first reproductions | As a maintainer, I want issue-pinned `p0_repro` tests for #5811 and #5812 that run through the CLI against a fixture with drain on and a real blocker (so the drain-off path cannot make them vacuously green) and fail on the base commit before the fix, so that the defects are proven and stay fixed. | High | Open | [build] | no |
| FR-011 | Single repair caller | As a maintainer, I want `doctor mission-state --fix` to be the only caller of the repo-wide repair, pinned by a test, so that upgrade cannot quietly start repairing again. | Medium | Open | [build] | no |
| FR-010 | Record the consent change | As a maintainer, I want an ADR amendment recording that `--yes` no longer consents to the mission-state repair, partly reversing #4775, so that the decision is traceable. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Clean no-op upgrade | A no-op `upgrade --yes` on a fixture with at least 3 writer-shaped historical Missions and 1 blocker leaves 0 modified and 0 untracked files under `kitty-specs/`, writes no `.kittify/mission-state-audit/` manifest, and its `git status --porcelain` matches that of a no-op upgrade on a blocker-free fixture. | Reliability | High | Open |
| NFR-002 | Code quality gates | 0 new ruff or mypy findings, and every touched function at cyclomatic complexity 15 or below. | Maintainability | High | Open |
| NFR-003 | Healthy log fidelity | 100% of healthy event logs (written by the current writer) are byte-identical after `doctor mission-state --fix`. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Terminology | Use the canonical term Mission, never "feature", in new code, messages and docs. | Technical | High | Open |
| C-002 | No history restoration | The Mission does not restore history that earlier runs already rewrote in consumer repositories; the release note says so. | Business | Medium | Open |
| C-003 | Non-interactive `--yes` | `upgrade --yes` stays fully non-interactive. | Technical | High | Open |
| C-004 | Single consent path | The repair's only consent path is the explicit `spec-kitty doctor mission-state --fix`. | Technical | High | Open |

### Key Entities

- **Mission status event log**: the append-only, authoritative record of work package lane transitions; its row order is the order of appending.
- **Status snapshot**: a derived materialization of the event log.
- **Mission-state blocker**: a Team Kitty readiness finding, such as `IDENTITY_MISSING`.
- **Residue directory**: a `kitty-specs/` entry with no tracked Mission artifacts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A routine upgrade on a repository with historical Missions and blockers leaves 0 changed files under `kitty-specs/`. — [build] · no-op passable: no
- **SC-002**: An explicit repair on healthy history changes 0 of its event logs. — [build] · no-op passable: no
- **SC-003**: A residue-only directory yields 0 blockers and 0 created files. — [build] · no-op passable: no
- **SC-004**: A partial repair never reports success: 100% of errored Missions are named in the outcome and the exit is non-zero; the plan characterizes the 52 errors seen in the dogfooding run. — [build] · no-op passable: no

## Assumptions

- Drain posture is read from the existing hosted-posture surface introduced with ADR `2026-10-06-1`.
- Rows that are not writer-shaped (legacy shapes, aliases) may still be normalized by the explicit doctor repair; only writer-shaped rows are required to be byte-identical.
- The reducer's own ordering is unaffected, so dropping the repair's sort does not change materialized lane state; the plan verifies this rather than assuming it.

## Out of Scope

- Restoring event logs already rewritten in consumer repositories (C-002).
- The wall-clock reducer ordering bug (#4941).
- Merging the several Mission-directory walkers into one (follow-up issue to be filed); this Mission only adds the shared is-a-Mission predicate and uses it in the mission-state audit and repair.
- Locally edited managed agent-profile files making `upgrade` exit 1 (#5745).
