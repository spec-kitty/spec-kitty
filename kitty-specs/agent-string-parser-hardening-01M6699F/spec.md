# Mission Specification: Harden the compact agent-string parser

**Mission Branch**: `issue-6755-agent-string-parser-hardening`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6755 — "Harden the compact agent-string parser: blank/whitespace segments and more than four segments". Found by the pre-merge squad on mission `status-contract-readers-01M5ZAAC` (#6400). Guidance from the operator: the three rows of the issue's table must change in `parse_agent_boundary_string` (src/specify_cli/status/models.py); the lenient free-text paths (`agent status emit`, `orchestrator-api`) keep storing such values whole as #6400 established; tests must cover each row; #2861's bare-tool rule stays intact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Whitespace segments stop fabricating identity (Priority: P1)

An operator passes a compact `--agent` value whose segments carry stray whitespace
(`--agent "claude: :"`, `--agent "claude\n"`). Today the stored structured actor
records `model: " "` or `tool: "claude\n"` — fabricated, unusable identity that
compares unequal to the same agent recorded cleanly. The user wants every segment
stripped and a segment that is blank after stripping treated as absent (`None`),
exactly as an empty segment already is.

**Why this priority**: This is silent identity corruption on every agent and
operator status write (since #6400 the parser shapes the stored actor for
`move-task`, `mark-status` and `add-history`), and the cheapest row to fix.

**Independent Test**: `parse_agent_boundary_string("claude: :")` returns
`("claude", None, None, None)`; `parse_agent_boundary_string("claude\n")`
returns `("claude", None, None, None)`; a CLI write with such an `--agent`
stores the stripped identity.

**Acceptance Scenarios**:

1. **Given** `--agent "claude: :"`, **When** the value is parsed, **Then** the model
   segment is `None` (a whitespace-only segment is absent, not `" "`).
2. **Given** `--agent "claude\n"`, **When** the value is parsed, **Then** the tool is
   `"claude"` (every segment is stripped).
3. **Given** `--agent "  "` (a tool that is blank after stripping), **When** the value
   is parsed, **Then** the parser refuses with the existing empty-tool `ValueError`.

---

### User Story 2 - More than four segments is refused, not silently truncated (Priority: P1)

An operator passes `--agent "a:b:c:d:e"`. Today the parser keeps `a:b:c:d` and
drops `e` silently, so the stored actor asserts an identity the operator never
gave. The user wants the explicit `--agent` paths (`move-task`, `mark-status`,
`add-history`) to refuse such a value before any write, with the same clean
refusal `mark-status` already prints for an unparseable `--agent`.

**Why this priority**: Silent data loss on the operator's explicit input; the
refusal machinery already exists on all three paths.

**Independent Test**: `spec-kitty agent tasks mark-status ... --agent "a:b:c:d:e"`
exits 1 with `Invalid --agent value: ...` and writes nothing; the parser raises
`ValueError` for a value with more than four segments.

**Acceptance Scenarios**:

1. **Given** `--agent "a:b:c:d:e"` on `move-task`, `mark-status` or `add-history`,
   **When** the command runs, **Then** it refuses before any write with the
   existing `Invalid --agent value: <reason>` refusal (exit 1).
2. **Given** a `--agent` value with exactly four segments, **When** the command
   runs, **Then** it is accepted as today (the full compact form still parses).

---

### User Story 3 - Lenient free-text paths keep storing whole values (Priority: P1)

A free-text `--actor` with more than four segments (or one that fails the compact
parser) reaching `agent status emit` or the `orchestrator-api` lifecycle commands
must keep being stored whole, as #6400 established — the hardening must not make
those paths refuse or truncate.

**Why this priority**: This is the guard against regressing #6400's contract; it
binds the fix's blast radius.

**Independent Test**: `actor_from_option("a:b:c:d:e", role)` stores the value
whole as `tool`; the existing #6400 tests for over-4-segment and unparseable
free-text actors stay green.

**Acceptance Scenarios**:

1. **Given** `--actor "migration:backfill a:b:c:d:e"` or any value with more than
   four segments, **When** it goes through the lenient builder, **Then** it is
   stored whole as `tool`, unchanged from #6400.
2. **Given** a recorded actor string with more than four segments, **When**
   identity projection (`actor_full_identity`, `_actor_key`) reduces it, **Then**
   it is treated as opaque text rather than silently truncated to four segments.

### Edge Cases

- A tool segment that is whitespace-only (`" "` / `"\n"`): refused as an empty
  tool, matching the existing empty-tool error.
- Exactly four segments with trailing/leading whitespace per segment: stripped,
  accepted.
- Fewer than four segments (e.g. `"claude:sonnet"`): unchanged — trailing
  segments pad to `None`.
- Empty interior segments (`"codex::planner-priti:"`): unchanged — `None`.
- A value that begins with `migration:` or has more than four segments reaching
  `actor_from_option`: never parsed, stored whole (pre-existing check, stays).
- Identity comparison of a previously recorded whitespace-bearing string:
  `actor_full_identity` already `.strip()`s each projected part, so comparisons
  are unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Strip every segment; blank-after-strip is None | As an operator, I want each segment of my `--agent` value stripped and blank segments treated as absent, so no whitespace-only identity is stored. | High | Open | [build] | no — paired with the clean-segment positive control on the same fixture |
| FR-002 | Refuse more than four segments on explicit `--agent` paths | As an operator, I want `move-task`, `mark-status` and `add-history` to refuse a `--agent` value with more than four segments, so no identity is silently truncated. | High | Open | [build] | no — paired with the four-segment acceptance row on the same fixture |
| FR-003 | Lenient paths keep whole-value storage | As an operator, I want `agent status emit` and `orchestrator-api` free-text `--actor` values stored whole, so #6400's no-data-loss contract holds. | High | Open | [ratchet] | no — pinned by existing #6400 tests |
| FR-004 | Tests cover each row of the issue table | As a maintainer, I want a failing-first test per row (whitespace segment, unstripped segment, >4 segments), so the hardening is pinned. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new authority | The hardening lives in `parse_agent_boundary_string` only; no second parser or duplicated segment-count check is introduced (single canonical authority). | Maintainability | High | Open |
| NFR-002 | Targeted test surface | The change is validated with the owning module's fast tier plus the CLI tests for the three explicit paths; no full heavy suite runs locally. | Process | High | Open |
| NFR-003 | mypy --strict clean | Changed code passes `mypy --strict` with no new errors. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | #6400 lenient contract | `actor_from_option` and the identity projections must keep storing/reading over-4-segment and unparseable free-text values whole; no data loss there. | Technical | High | Open |
| C-002 | #2861 bare-tool rule | The parser stays a thin, non-synthesizing boundary parser: absent segments stay `None`, never a tool-derived synthetic default. | Technical | High | Open |
| C-003 | One refusal message shape | The >4-segment refusal on the explicit paths uses the existing `Invalid --agent value: <reason>` channel; no new error surface. | Technical | High | Open |

### Key Entities

- **Compact agent string**: the `--agent tool:model:profile:role` CLI value; at
  most four `:`-separated segments.
- **Structured actor**: the `{tool, role, profile, model}` dict stored on status
  events since #6400.
- **Lenient builder**: `actor_from_option` — builds a structured actor from a
  free-text or recorded identity without refusing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each row of #6755's table has a regression test that was red on `main` and is green on the mission branch — [build] · no-op passable: no
- **SC-002**: `move-task`, `mark-status` and `add-history` refuse `--agent "a:b:c:d:e"` with exit 1 and `Invalid --agent value: ...` before any write — [build] · no-op passable: no
- **SC-003**: All existing #6400 lenient-path and #2861 bare-tool tests pass unchanged — [ratchet] · no-op passable: no
- **SC-004**: The diff stays inside `parse_agent_boundary_string`, its tests, the changelog and any docs the change touches — [build] · no-op passable: yes
