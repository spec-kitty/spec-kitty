# Mission Specification: mark-status owner authority

**Mission Branch**: `issue-6463-mark-status-owner-authority`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6463 — `tasks mark-status` silently resolves to the wrong work package when subtask ids collide across work packages.

## Context and grounding

The reported headline defect (a bare `T001` shared by several work packages made
`mark-status` no-op against the alphabetically first WP) is **already fixed on
`main`** by #5953: `--wp` scopes the mark (`tasks.py:981`) and
`_resolve_task_owners` refuses a shared id before anything is written, pinned by
`test_repeated_subtask_requires_wp_and_scoped_mark_is_idempotent`.

What survives is the residue that made the original report look silent: **the
ownership decision is not single-sourced, and the write path re-derives it by
first match.** Three concrete, reproduced failures on `main@35318ef51c`:

1. **Mixed sources are not unioned, so an id two WPs claim looks unique.**
   `_owners_for_task` is `authored_roster_owners(...) or history_wp_ids(...)` — the
   authored roster *replaces* the `tasks.md` claim instead of joining it. A
   legacy WP file with no `subtasks:` frontmatter that lists the id in a
   structured `tasks.md` row is therefore invisible. Reproduced: WP01 roster
   `[T001]`, WP02 legacy with `## WP02 / Subtasks: T001`, and an unscoped
   `mark-status T001 --status done` records `{'T001': 'done'}` on **WP01** with no
   refusal — the operator working WP02 gets a silent wrong-WP write.
2. **A bare `WP<digits>` id is exempted from every ownership check** (the
   `re.fullmatch(r"WP\d+")` `continue`), so a subtask id that collides with a
   work-package id is never scoped, never refused, and the legacy resolvers claim
   it. Reproduced: a `tasks.md` WP index table (`| WP02 | Foundation | T002 |`)
   plus `mark-status WP02 --status done` records the bogus subtask
   `{'WP02': 'done'}` **on WP02** and exits 0, instead of the documented
   "mark-status does not change work-package lanes" rejection.
3. **The write path attributes by first match.** `_ms_emit_subtask_state` falls
   back to `_resolve_history_wp_id(...) or owning_wp_from_authored_roster(...)`
   whenever the resolution phase recorded no owner, so the WP that receives the
   event is decided by document order / alphabetical filename — a second source
   of truth on the only surface that writes.

The danger the issue names is *silent* wrong-WP writes. The mission makes
resolution unambiguous and single-sourced, and refuses loudly where it cannot be.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An ambiguous subtask id is refused, not guessed (Priority: P1)

An implementer marking the subtasks of the WP they are working on types the bare
ids. When more than one work package claims an id — through an authored roster,
through a structured `tasks.md` row, or through both — the command refuses before
writing anything and names every owner plus the `--wp` that selects one.

**Why this priority**: this is the issue's failure mode; a wrong-WP write corrupts
the review gate's completion authority for a WP nobody touched.

**Independent Test**: a mission with WP01 authoring `T001` in its roster and a
legacy WP02 claiming `T001` in a structured `tasks.md` row; unscoped
`mark-status T001 --status done` exits 1 with both owners named and no event is
appended; each `--wp` writes only its own WP.

**Acceptance Scenarios**:

1. **Given** WP01 authors `T001` and legacy WP02 claims `T001` in a structured `tasks.md` row, **When** `mark-status T001 --status done` runs without `--wp`, **Then** it exits 1 naming `WP01, WP02`, suggests `--wp WP01` or `--wp WP02`, and appends no status event.
2. **Given** the same mission, **When** `mark-status T001 --status done --wp WP02` runs, **Then** exactly one event is appended, carrying `wp_id: WP02`.
3. **Given** the same mission, **When** `mark-status T001 --status done --wp WP09` runs, **Then** it exits 1 naming the real owners and no event is appended.

---

### User Story 2 - A subtask id that collides with a work-package id stays unambiguous (Priority: P1)

A WP id typed into `mark-status` must never be silently recorded as a subtask, and
a subtask genuinely named like a WP id is only marked when the caller says which
work package owns it.

**Why this priority**: it is the collision class in the issue title, and it is
what makes a wrong-WP write look like a success today.

**Independent Test**: a `tasks.md` with a WP index table; bare `mark-status WP02`
exits 1 with the lane-transition rejection and writes nothing. A mission whose
WP01 roster authors `WP02` as a subtask: unscoped `mark-status WP02` refuses with
the owner named; `--wp WP01` marks it on WP01 only.

**Acceptance Scenarios**:

1. **Given** a `tasks.md` whose WP index table has a `| WP02 | … |` row and no WP authors `WP02` as a subtask, **When** `mark-status WP02 --status done` runs, **Then** it exits 1 with the "mark-status does not change work-package lanes" rejection and appends no event.
2. **Given** WP01 authors `WP02` as a subtask, **When** unscoped `mark-status WP02 --status done` runs, **Then** it exits 1 naming WP01 as the owner and pointing at the lane transition for the WP itself, and appends no event.
3. **Given** the same mission, **When** `mark-status WP02 --status done --wp WP01` runs, **Then** exactly one event is appended, carrying `wp_id: WP01` and `subtasks: {"WP02": "done"}`.

---

### User Story 3 - The write path has one ownership authority (Priority: P2)

The event that records completion is attributed only from the ownership decision
the command already made; when an id reaches the emit with no recorded owner the
command refuses instead of first-matching a work package.

**Why this priority**: defense in depth — it removes the mechanism that turns any
future divergence (a filename spelling, a second derivation) into a silent
wrong-WP write.

**Independent Test**: an emit whose state carries an updated id with no owner in
`task_wps` raises/refuses and writes no event, on a fixture where the old
first-match fallback would have found a WP.

**Acceptance Scenarios**:

1. **Given** an updated subtask id with no owner in the resolved owner map, **When** the emit phase runs, **Then** it refuses before writing any event and names the id.
2. **Given** a resolved owner map, **When** the emit runs, **Then** the event's `wp_id` is exactly the recorded owner — `_resolve_history_wp_id`/`owning_wp_from_authored_roster` are never consulted.

### Edge Cases

- A roster that cannot be read still fails closed before any write (unchanged, #5953).
- A `--wp` that owns none of the requested ids still refuses with the owner list (unchanged).
- `--wp` given for a `WP`-shaped id that no WP authors as a subtask → lane-transition rejection, not "not a subtask of" (the id is a work package, not a subtask).
- Both sources name the same single WP → not ambiguous; unscoped mark proceeds exactly as today (no new refusal for the shipped single-authority shape).
- Repeated mark → still an honest no-op (`already_satisfied`), no duplicate event.
- Unreadable/absent `tasks/` directory → unchanged NOT_FOUND path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Union the two ownership sources | As an implementer, I want an id claimed by an authored roster and by a structured `tasks.md` row in different WPs treated as shared, so that neither source hides the other. | High | Open | [build] | no — the red case (legacy WP02 claim invisible) writes WP01 today |
| FR-002 | Scope `WP`-shaped subtask ids | As an implementer, I want a `WP<digits>` id that a WP authors as a subtask to obey the same `--wp`/ambiguity rules as any other id, so that a WP id can never be silently recorded as an unscoped subtask. | High | Open | [build] | no — the red case writes a bogus `WP02` subtask today |
| FR-003 | Reject bare WP ids before legacy row shapes | As an operator, I want `mark-status WP02` on a WP that authors no such subtask to fail with the lane-transition rejection, so that a WP index-table row or inline list cannot claim a work-package id. | High | Open | [build] | no — a WP index table row makes it "succeed" today |
| FR-004 | Attribute the emit from the recorded owner only | As a maintainer, I want the completion event's `wp_id` to come only from the resolved owner map, so that document order can never choose the target. | High | Open | [ratchet] | no — the fallback first-matches today |
| FR-005 | Refuse an unattributable updated id | As a maintainer, I want an updated id with no recorded owner to refuse before any event is written, so that an unknown owner fails loud instead of writing somewhere. | High | Open | [build] | no — the red invariant test attributes via fallback today |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new failure mode for the shipped shapes | The shipped `software-dev` `tasks.md` (plain subtask lines, no structured rows) must produce byte-identical `mark-status` behaviour: no new refusal, same event payload, same `--json` envelope. | Compatibility | High | Open |
| NFR-002 | Refusals precede writes | Every new refusal exits 1 before `status.events.jsonl` is appended: verified by asserting the event log is absent/unchanged after each refusal. | Reliability | High | Open |
| NFR-003 | Targeted suite only | Verification runs the `mark-status`/tasks CLI suites, not the full heavy tree (`NO_FULL_HEAVY_SUITES_IN_MISSION`). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No `--wp` contract change | `--wp` keeps its type, spelling and success semantics; only the refusal surface grows. | Technical | High | Open |
| C-002 | One owner derivation | The write path must not add a third ownership derivation; the authored-roster owner map is the single authority and `tasks.md` contributes only structured rows. | Technical | High | Open |
| C-003 | Changelog + docs | The user-visible refusal change gets an `[Unreleased]` changelog entry and an update to the `mark-status` docs/help surface it touches. | Business | Medium | Open |

### Key Entities

- **Owner map**: the per-mission map of subtask id → the work packages that claim it (authored `subtasks:` frontmatter plus structured `tasks.md` rows).
- **Scoped mark**: a `mark-status` invocation carrying `--wp`, whose resolved owners must include that WP.
- **Completion event**: the `InnerStateChanged` annotation whose `wp_id` and `subtasks` delta are the sole subtask-completion authority.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The three reproduced wrong-WP writes (mixed-source, WP-shaped unscoped, WP-index-row) each exit 1 and append no event, proven by new tests that are red on `main@35318ef51c` and green on the branch. — [build] · no-op passable: no
- **SC-002**: The emit path contains no ownership fallback: no `_resolve_history_wp_id`/`owning_wp_from_authored_roster` call remains in the write path, guarded by a test that fails if an unattributable id is first-matched. — [ratchet] · no-op passable: no
- **SC-003**: The existing `mark-status` suites (including the #5953 regression) pass unchanged, so no shipped shape gains a refusal. — [folded] · no-op passable: no
