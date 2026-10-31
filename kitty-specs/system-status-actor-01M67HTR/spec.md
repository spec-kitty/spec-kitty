# Mission Specification: System status actor

**Mission Branch**: `issue-6722-system-status-actor`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6722 — "Structured actor for system status writers (migrations, consolidation bookkeeping, bootstrap, recovery, attestations)". Follow-up to #6400 (mission `status-contract-readers-01M5ZAAC`), whose spec boundary reads: "system writers (migrations, consolidation bookkeeping, bootstrap, recovery, attestations) keep their string actors; existing logs stay readable."

## Intent Summary (confirmed)

- **Primary actor**: anyone reading or writing `status.events.jsonl` — the CLI's own readers (reducer, gates, the Read API projection), the Java write/read services, and the operator who reads a board or an audit trail.
- **Trigger**: any status event the CLI writes on its own initiative instead of on an agent's or an operator command's: bootstrap seeds, lane recovery catch-up, consolidation done/approval bookkeeping, the review-artifact override annotation, the consolidation attestations, and the three in-process migration backfills.
- **Outcome**: those events carry the same 4-key structured actor that #6400 gave the agent and operator paths, with one new role value, `system`.
- **Question the issue asks**: does a system event get the same shape, e.g. `{tool: "migration:<id>" | "spec-kitty", role: "system", profile: null, model: null}`? **Answer: yes, with `tool` carrying the identity the writer records today** (Decision below).
- **Boundary**: the agent and operator write paths #6400 shipped are untouched; every reader projection is unchanged; logs written before this change keep reducing and keep classifying seeds; no event field is added.

## Decision: the shape of a system actor

A system status write records

```
{"tool": <the identity the writer records today>, "role": "system", "profile": null, "model": null}
```

1. **The same 4-key shape.** One actor shape for every writer, which is what #6400 was for. No consumer — the CLI reader, the Read API projection, the Java write core — branches on who wrote the event.
2. **`role` gains exactly one value, `system`.** It names the kind of agency: the program wrote this event on its own initiative or on the operator's behalf, with no agent dispatch behind it. `implementer` and `reviewer` keep their meaning.
3. **`tool` is the identity the writer records today, unchanged**: `migration:backfill_runtime_state`, `migration:backfill_wp_status`, `migration:verdict_provenance_backfill`, `merge`, `recovery`, `finalize-tasks`, and the resolved operator identity for the attestations and the review-artifact override. Two rejected alternatives, and why:
   - `tool: "spec-kitty"` for every system writer collapses six auditable identities into one and destroys `is_migration_actor` for every newly written seed, so the gates that classify seeds would stop recognising them (the issue's own "gates must keep recognising them" bar).
   - A `migration:<id>` stripped of its prefix needs the same gates rewritten around `role` instead of the identity prefix, which re-decides #6093/#6271 for no gain and makes old and new rows classify by two different rules.
4. **`profile` and `model` are always `null`.** A system writer has no dispatch binding; nothing is filled in from a plan, an environment or a default (the #6400 rule, carried from `coord-commit-integrity-01KY5JS8#C-007`: a value absent everywhere stays `None`).
5. **No `profile_source`.** That key is #6721's, gated on an events release; this mission adds no fifth key.
6. **No wire change.** `spec_kitty_events.diary.decode_actor` requires `str | None` per value and does not enumerate `role`; the Java `Actor` handle is `^[A-Za-z0-9._:-]{1,128}$` and does not either. `system` therefore crosses both unchanged, with no events release and no frozen-path edit (ADR `2026-10-29-1` D-9 freezes `services/` and `contracts/`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A system write names itself in the one structured shape (Priority: P1)

The operator finalizes a mission's tasks, a crashed lane is reconciled, and a consolidation marks a merged work package done. Each event those three steps write carries `{tool, role: "system", profile: null, model: null}` instead of a bare string.

**Why this priority**: this is the issue's decision. Every other story is a consequence of it.

**Independent Test**: run bootstrap, recovery and the consolidation done bookkeeping on a fixture mission and read `status.events.jsonl`: every new event has exactly the four keys, `role == "system"`, `profile` and `model` `None`, and `tool` equal to the identity the writer recorded before.

**Acceptance Scenarios**:

1. **Given** a mission whose work packages have no events, **When** `finalize-tasks` bootstraps them, **Then** each seed event's actor is `{"tool": "finalize-tasks", "role": "system", "profile": null, "model": null}`.
2. **Given** a work package left in `claimed` by a crashed run, **When** the lane recovery sweep reconciles it, **Then** the catch-up transition's actor is `{"tool": "recovery", "role": "system", ...}` and the string `"recovery"` no longer appears on the event.
3. **Given** an approved work package merged into the target branch, **When** the done bookkeeping marks it done, **Then** the transition's actor is `{"tool": "merge", "role": "system", ...}`.
4. **Given** the same three writes, **When** the snapshot is materialized, **Then** each work package's snapshot `actor` slot reads exactly the tool (`finalize-tasks`, `recovery`, `merge`) — the display identity does not change.

---

### User Story 2 - A migration seed is still a seed, however it is shaped (Priority: P1)

A maintainer runs the three in-process backfills on a legacy mission. The seeds they write carry the structured system actor with `tool: "migration:<id>"`, and every gate that classifies seeds recognises them exactly as it recognises the string rows written before this change.

**Why this priority**: a seed that stops looking like a seed is silently treated as governed work — it would be counted as an implementation claim, void a consolidation window, or demand a review-exit note.

**Independent Test**: write one seed per migration writer, then assert `is_migration_actor` is true for each; reduce a log whose only in-progress claim is a seed and assert the seed is not the implementer of record and opens no consolidation window; run `validate_timestamp_continuity` over a log with a structured seed and assert it is exempt, as for a string seed.

**Acceptance Scenarios**:

1. **Given** the three backfills, **When** each writes its seed, **Then** `actor_identity_str(event.actor)` equals the `migration:<id>` string the writer used before, and `is_migration_actor(event.actor)` is true.
2. **Given** a reduced log whose latest claim into `in_progress` is a structured seed, **When** the implementer of record is read, **Then** the seed is skipped exactly as a string seed is (the answer is the same event, or `None`, as with the string).
3. **Given** a structured seed on a work package, **When** the consolidation work-window rule runs, **Then** the seed neither opens, closes nor extends a window.
4. **Given** a structured seed whose `at` ties the surrounding history, **When** `validate_timestamp_continuity` runs, **Then** the seed is exempt from the continuity check.
5. **Given** the same seed row written as a string (the shape this mission replaces), **When** each of the four readers above runs, **Then** it answers identically. The shape never decides the answer.

---

### User Story 3 - An existing log keeps reducing, and keeps verifying (Priority: P1)

An operator upgrades the CLI with a committed `status.events.jsonl` full of string-actor rows, reduces it, and re-runs `spec-kitty migrate backfill-runtime-state` to verify it. Nothing changes: the same snapshot, the same verdict.

**Why this priority**: the issue's own done-bar ("existing logs reduce unchanged"), and the one place where it can realistically break: the backfill's fail-closed payload verification compares a rebuilt seed row to the immutable row already in the log.

**Independent Test**: reduce a corpus of the repository's committed mission logs before and after the change and compare the resulting `status.json` bytes; then verify a corpus seeded before the change and assert `VerifyResult.ok`.

**Acceptance Scenarios**:

1. **Given** any committed mission log in `kitty-specs/`, **When** it is reduced, **Then** the snapshot is byte-identical to the snapshot the pre-change code produces.
2. **Given** a mission seeded by the pre-change code (string seeds), **When** `verify_backfill` runs on the new code, **Then** `ok` is true and `mismatches` is empty: an immutable row whose only difference is the actor's shape is sound, not tampering.
3. **Given** a mission seeded before this change whose seed row's identity is *different* (`migration:another_backfill`), **When** `verify_backfill` runs, **Then** it is still reported as a mismatch. The tolerance is shape-only.

---

### User Story 4 - An attestation records the operator without claiming a review role (Priority: P2)

The operator passes `--attest-approved-reviewed` / `--attest-canceled-superseded` to consolidation. The attestation event names the resolved operator identity in `tool`, says `role: "system"`, and is still identified as an attestation by its `policy_metadata` — never as a review.

**Why this priority**: it is the last family in the issue's list, and the only one whose identity is a person's rather than the program's.

**Independent Test**: run both attestation paths on a fixture and assert the stored actor; assert the approved-reviewed attestation is still excluded from the independent-reviewer read and the no-implementation read, exactly as before.

**Acceptance Scenarios**:

1. **Given** an approved work package, **When** `--attest-approved-reviewed "<why>"` records the attestation, **Then** the event actor is `{"tool": <resolved identity>, "role": "system", "profile": null, "model": null}` and `policy_metadata.attestation` is unchanged.
2. **Given** the same attestation, **When** the consolidation gate asks who approved the work package, **Then** the attestation is still skipped (`_is_operator_attestation`) and no review verdict is inferred from its `role`.
3. **Given** `--skip-review-artifact-check --skip-review-artifact-note "<why>"`, **When** the bypass is recorded, **Then** the annotation event's actor is the system actor while the override's own `ReviewOverride.actor` slot keeps the plain identity string (its pinned four-field shape is unchanged).

---

### User Story 5 - The rule is written down where a maintainer will look (Priority: P3)

A maintainer changing a status writer reads `docs/architecture/status-model.md` and finds the role vocabulary (`implementer`, `reviewer`, `system`), which writers use which, and why a system actor carries no profile.

**Independent Test**: read the section; it names all three role values, each system writer, and the null-profile rule, and `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry referencing #6722.

**Acceptance Scenarios**:

1. **Given** the docs, **When** a maintainer looks for "still strings", **Then** the sentence is gone and the system-writer rule stands in its place.
2. **Given** `docs/changelog/CHANGELOG.md`, **When** it is read, **Then** an `[Unreleased]` entry leads with the impact and cites `(#6722)`.

---

### Edge Cases

- **A system writer's `tool` carries a colon** (`migration:backfill_runtime_state`). `parse_agent_boundary_string` would split it, so the shared builder must not route a system identity through the compact-agent parser; the identity goes into `tool` whole, exactly as `actor_from_option` already keeps an unparseable recorded value whole.
- **A structured seed's `actor_full_identity`** differs from the string's in where the colon splits (`migration:x::` vs `migration:x:`). Every caller of that projection excludes seeds first; the mission proves the mixed-shape read is unaffected rather than changing the projection #6400/#6715 pinned.
- **A seed row that is already in the log** cannot be rewritten (rows are immutable and deduplicated on id), so pre-change and post-change rows coexist in one log. Both must classify as seeds and both must reduce to the same snapshot.
- **A caller-supplied actor** is not in scope: since #6754 (PR #6838) the emit shell refuses a caller value starting with `migration:`, so a seed can only come from an in-process writer. This mission must not depend on that PR having landed, and must not duplicate its guard.
- **An events release with a stricter `role` vocabulary** would refuse `system`. The installed floor does not enumerate `role`; a test pins that, so a future events release that does is caught here rather than at a user's log.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One builder for a system actor | As a maintainer, I want one function that builds the system actor so that no writer assembles the four keys by hand. | High | Open | [build] | no |
| FR-002 | Bootstrap seeds the system actor | As an operator, I want the `finalize-tasks` seed to carry the system actor so that bootstrap events name their writer in the one shape. | High | Open | [build] | no |
| FR-003 | Recovery catch-up uses the system actor | As an operator, I want a recovered lane's catch-up transition to carry the system actor so that recovery is auditable like every other write. | High | Open | [build] | no |
| FR-004 | Consolidation bookkeeping uses the system actor | As an operator, I want the merge-time approval replay, the done mark and the done-write refusal probe to carry the system actor so that consolidation events are one shape. | High | Open | [build] | no |
| FR-005 | The review-artifact override's event carries the system actor | As an operator, I want a recorded skip to name the program as the writer while its override slot keeps the operator identity, so that a durable bypass is still attributable to the person who asked for it. | Medium | Open | [build] | no |
| FR-006 | Both attestations use the system actor | As an operator, I want an attestation's event to carry the system actor with the resolved identity in `tool`, so that the attestation is one shape without claiming a review role. | Medium | Open | [build] | no |
| FR-007 | The three migration writers use the system actor | As a maintainer, I want every in-process backfill to write the system actor, so that a seed has one shape. | High | Open | [build] | no |
| FR-008 | `role` gains exactly one value | As a reader, I want the role vocabulary to be `implementer`, `reviewer` and `system`, so that the value set stays closed and known. | High | Open | [build] | no |
| FR-009 | Seed recognition is shape-blind | As a maintainer, I want one predicate per question ("is this a seed?", "is this *this* migration's seed?") that answers the same for the string and the structured shape, so that no gate learns a second rule. | High | Open | [build] | no |
| FR-010 | Pre-change seed rows still verify | As an operator, I want `migrate backfill-runtime-state` to accept an immutable seed row whose only difference is the actor's shape, so that an upgrade does not report my log as tampered. | High | Open | [build] | no |
| FR-011 | The decoder and the write core accept `system` | As a platform maintainer, I want a test pinning that `role: "system"` crosses the CLI decoder and the shared events decoder unchanged, so that a future events release that enumerates `role` is caught here. | High | Open | [build] | no |
| FR-012 | Readers are unchanged | As a maintainer, I want a mixed log (string seeds and structured seeds in one file) to reduce to the same snapshot as an all-string log, so that the shape never decides a verdict. | High | Open | [build] | no |
| FR-013 | The rule and the changelog are documented | As a maintainer, I want the actor section to state the system rule and the changelog to record it, so that the next writer follows it. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No invented identity | 100% of system-actor writes carry `profile: null` and `model: null`; a test asserts it for every writer site. | Correctness | High | Open |
| NFR-002 | No new field, no wire change | The stored event has exactly the 4 keys #6400 shipped; `profile_source` appears in no written row. | Compatibility | High | Open |
| NFR-003 | Existing logs reduce unchanged | The reduced snapshot of every committed `kitty-specs/*/status.events.jsonl` is byte-identical before and after. | Reliability | High | Open |
| NFR-004 | The touched surface stays green | `ruff check`, `ruff format --check` and `mypy` pass on every touched module; the status, migration, consolidation and lanes suites pass. | Maintainability | High | Open |
| NFR-005 | Bounded diff | No change under `services/`, `contracts/`, or to the agent/operator builders in `status/actor.py` beyond the additive system builder. | Process | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Nothing is invented | `tool` is the identity the writer records today and only that; `profile`/`model` stay `null` (`coord-commit-integrity-01KY5JS8#C-007`, the rule #6400 pinned). | Technical | High | Open |
| C-002 | `services/` and `contracts/` are frozen | ADR `2026-10-29-1` D-9 freezes them; the Java write core needs no change because the actor handle accepts any string. | Regulatory | High | Open |
| C-003 | Rows are immutable | A pre-change seed row is never rewritten; compatibility is proven by the readers, not by a migration of stored rows. | Technical | High | Open |
| C-004 | Sibling PR #6838 is not a dependency | #6754/#6838 refuses a caller-supplied `migration:` actor in the emit shell. This mission does not depend on it, does not duplicate it, and does not edit the shell. | Technical | High | Open |
| C-005 | The `ReviewOverride` shape is pinned | Its four `str` fields are referenced verbatim by other work packages; only the event's actor changes at the override site. | Technical | High | Open |
| C-006 | No second role authority | The role vocabulary lives in `status/actor.ActorRole` and nowhere else; no module re-lists the values. | Technical | Medium | Open |

### Key Entities

- **System actor**: the 4-key dict a system writer records — `{tool, role: "system", profile: null, model: null}`. Built by one function; never assembled inline.
- **Seed identity**: the `migration:<id>` string that names an in-process reconstruction. It survives as the actor's `tool`, so `is_migration_actor` and the reducer's seed arm keep their rule.
- **Seed row**: an immutable `status.events.jsonl` line. Its payload is compared by the backfill's fail-closed verification; only the actor's *shape* is tolerated as a difference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 13 system-writer emit sites across nine writer modules (bootstrap; recovery; two done-bookkeeping emits; the done refusal probe and the override annotation; two attestations; two emits each in `wp_status_backfill` and `backfill_runtime_state`; one in `verdict_provenance_backfill`) write the 4-key system actor, asserted by at least one test per writer family. — [build] · no-op passable: no
- **SC-002**: The reduced snapshot of every committed mission log in `kitty-specs/` is byte-identical before and after the change. — [ratchet] · no-op passable: no
- **SC-003**: A log mixing string-actor seeds and structured-actor seeds reduces to the same snapshot as the all-string log, and `verify_backfill` returns `ok` for both. — [build] · no-op passable: no
- **SC-004**: Zero written rows carry a fifth key; zero system rows carry a non-null `profile` or `model`. — [ratchet] · no-op passable: no
- **SC-005**: `docs/architecture/status-model.md` names the three role values and every system writer, and `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry citing `(#6722)`. — [build] · no-op passable: no

## Out of Scope

- The agent and operator write paths, the two existing role values, and the `profile_source`/frontmatter fill (#6721).
- The refusal of a caller-supplied `migration:` actor (#6754, sibling PR #6838).
- Any edit under `services/`, `contracts/`, or `acceptance-jvm/` (ADR `2026-10-29-1` D-9).
- The three non-status actor strings found in the survey that never reach a status event: `coordination/status_transition.py`'s read-only `"status-read"` request identity, `tasks_transition_core.py`'s throwaway `"cli"` wire probe, and `tasks/issue_matrix.py`'s `"finalize-scaffold"` commit actor.
- Re-writing, migrating or compacting stored event rows.
