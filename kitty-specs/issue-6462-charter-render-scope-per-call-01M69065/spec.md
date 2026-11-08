# Mission Specification: Render only the charter scope the command reads (#6462)

**Mission Branch**: `issue-6462-charter-render-scope-per-call`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6462 — "Every CLI call re-renders full charter context (90-150s/call) with irrelevant catalog-miss warnings". Grounding comment on the issue records what reproduces on current `main` and what does not.

## Problem statement

The report's headline magnitude does not reproduce on `4.0.0rc8` at this repository's
scale, but the *mechanism* it names does, and it is measurable per invocation as work
performed rather than seconds:

1. **The offering catalog is scanned whole, for every caller.**
   `charter.activation.catalog.load_offering_catalog()` reads and parses all eight
   built-in domains on every call — **265 shipped YAML documents** in this repo's pack —
   while `resolve_project_governance()` reads only `paradigms`, `directives` and
   `template_sets` (**52 files**), and `default_interview()` only `paradigms` and
   `directives` (**52 files**). `GovernanceResolution.tactics/styleguides/toolguides/
   procedures` are hard-coded `[]`, so five of the eight scans are pure waste on the
   persona render that every workflow call performs.
2. **A structural marker drags in the whole profile catalog and its lineage graph.**
   The read-only `agent tasks status` board builds the full `ActiveCharterService`
   (pack context, activation ledger, offering service) and a complete
   `AgentProfileRepository` — **26 profile files plus 13 DRG fragments** — to answer
   `profile.sentinel` for the work packages on the board. The lineage graph is loaded
   eagerly in `AgentProfileRepository.__init__` even though it is only read by
   `get_ancestors`/`get_children`/channel-reachability, which this path never calls.

Measured baseline on `main` `dfe9efb0e8`, isolated `HOME`, warm caches (recorded in
`traces/tooling-friction.md`; the host is shared with ~20 concurrent agents, so call
counts — not seconds — are the asserted quantity, per #6858):

| Command | Shipped-doc parses | of which needed | Charter-service builds |
|---|---|---|---|
| `charter context --action implement` | 265 | 52 | 1 |
| `agent tasks status --mission <m>` | 107 | ≤ 70 | 1 |

Catalog-miss warnings are **not** part of this fix: on this project they measure 0–2 per
call after per-process deduplication (#4572) and the `SCOPE_FILTERED` quieting for
`agent_profile` misses, and the charter-offering scope rule deliberately keeps a
scope-filtered styleguide warning (`tests/charter/test_context_catalog_miss.py`). Changing that contract is a governance ruling, not a bug fix (see Deferred).

## Scope boundary

**In scope**

- `load_offering_catalog()` gains an explicit domain scope; the two governance call
  sites request exactly the domains they read.
- `AgentProfileRepository` stops parsing the shipped DRG at construction time; lineage
  accessors build it on first use.
- Deterministic census guards (counts of parsed shipped documents, not wall clock) that
  fail if either regression returns.
- Changelog entry and the affected architecture/README notes.

**Out of scope (explicitly not touched)**

- Any cross-process render cache, TTL, or on-disk memo of charter state, and any
  `--no-charter-render` fast-path flag. The issue proposes both; triage records that no
  cache architecture is pre-approved, and #5526's per-change in-process memo is the
  established pattern this mission stays inside.
- The catalog-miss warning contract (`_QUIET_SCOPE_FILTERED_KINDS`, the scope-filtered
  styleguide warning, `CharterCatalogMissWarning` semantics).
- The `ActiveCharterService` sole door (charter-sole-door-bypass-closure-01KZ3WAA):
  no new `charter.offering.*` import from `specify_cli`, no second profile reader.
- Governance resolution semantics: resolved paradigm/directive/template-set selection,
  diagnostics, deny nets and activation gating are unchanged.
- Startup-asset freshness (`prepare_startup_assets`, #4211) and mission-step /
  mission-type repository scans.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A workflow render stops parsing doctrine it never reads (Priority: P1)

An operator runs `spec-kitty next`, `spec-kitty agent action <step>`, or
`spec-kitty charter context --action <action>` in a project whose pack carries
tactics, styleguides, toolguides and profiles for stacks it does not use. The persona
render still produces byte-identical charter context, but it no longer parses the
domains the render does not consult.

**Why this priority**: it is the exact mechanism the issue reports — every workflow call
rendering "full charter context" — and it is on the hottest path (every step of every
mission).

**Independent Test**: run `spec-kitty charter context --action implement` under a
counting harness that records each shipped document parsed; assert the render parses no
file from the tactic/styleguide/toolguide/procedure/agent-profile domains and stays
within a fixed ceiling. Fails on `main`, passes after.

**Acceptance Scenarios**:

1. **Given** a project whose charter selects paradigms and directives, **When**
   `charter context --action implement` renders, **Then** the resolved governance
   selections, diagnostics and rendered text are identical to `main`, and no
   out-of-scope domain file is parsed.
2. **Given** the same project, **When** `load_offering_catalog()` is called with an
   explicit domain scope, **Then** only that domain's files are read and
   `domains_present` names exactly the scanned, present domains.
3. **Given** a caller that passes no scope, **When** it loads the catalog, **Then**
   behaviour is exactly as before (all eight domains).

### User Story 2 - A read-only board stops loading the lineage graph (Priority: P2)

An operator runs `agent tasks status` repeatedly to watch a mission. The 👤 marker
still appears for human-in-charge work packages, the board is byte-identical, but the
command no longer parses 13 DRG fragments to draw it.

**Why this priority**: the same root cause ("render what you don't need") on a
read-only, frequently-called command, but a smaller absolute slice than Story 1.

**Independent Test**: run `agent tasks status` under the same counting harness; assert
zero shipped-graph parses and a fixed ceiling on total shipped-doc parses, and that a
mission with a claimed human-in-charge work package still renders `👤`.

**Acceptance Scenarios**:

1. **Given** a mission whose work packages carry `agent_profile: human-in-charge`,
   **When** the board renders, **Then** the marker is present exactly as on `main`.
2. **Given** any project, **When** a lineage accessor (`get_ancestors`,
   `get_children`, channel reachability) is used, **Then** the graph is built on first
   use and results are unchanged.
3. **Given** a repository whose DRG cannot be loaded, **When** only the profile map is
   read, **Then** no graph load is attempted and no `DRGLoadError` is raised; the
   pre-existing empty-graph degradation still applies once a lineage accessor is used.

### Edge Cases

- A scope naming an unknown domain: fail closed with a `ValueError`, never a silently
  empty catalog.
- An empty scope: legal (a caller that needs no domain); zero files scanned and
  `domains_present` empty.
- A scoped domain whose directory is absent: unchanged semantics — empty set, absent
  from `domains_present`.
- A caller reading a field it did not scope: the guard tests pin that the two governance
  call sites' scope is exactly the set of fields they read, so a future edit that starts
  reading tactics must widen the scope or fail its census test.
- Repository constructed with an explicit `drg=`: unchanged, no lazy path taken.
- A malformed `.kittify/config.yaml` still raises `ActiveCharterConfigError` (fail-closed
  contract untouched).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Catalog domain scope | As a charter consumer, I want `load_offering_catalog` to accept an explicit domain scope so that it reads only the domains I consult. | High | Open | [build] | no — the scan set itself is the deliverable |
| FR-002 | Governance resolver scopes its reads | As an operator, I want `resolve_project_governance` to request only paradigms, directives and template sets so that a persona render stops parsing five unrelated domains. | High | Open | [build] | no — 211 files of work are removed |
| FR-003 | Interview defaults scope their reads | As a charter consumer, I want `default_interview` to request only paradigms and directives so that interview defaults do not scan the whole pack. | Medium | Open | [build] | no |
| FR-004 | Lazy lineage graph | As an operator, I want `AgentProfileRepository` to build its DRG on first lineage use so that profile-map readers do not pay 13 fragment parses. | Medium | Open | [build] | no |
| FR-005 | Scope census guards | As a maintainer, I want deterministic tests that count parsed shipped documents per command so that a wider render cannot return unnoticed. | High | Open | [ratchet] | no — the ceiling is the invariant |
| FR-006 | Unknown-domain refusal | As an operator, I want a scope naming an unknown domain to fail closed rather than yield an empty catalog. | Medium | Open | [build] | no |
| FR-007 | Changelog and docs | As a maintainer, I want an `[Unreleased]` changelog entry and the touched module notes to state the scope rule so that the next caller scopes its read. | Low | Open | [build] | yes — a docs-only pass would not satisfy FR-001/002 |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Persona render parse ceiling | `charter context --action implement` parses at most 60 shipped documents (baseline 265) and zero from the tactic/styleguide/toolguide/procedure/agent-profile domains. | Performance | High | Open |
| NFR-002 | Read-only board parse ceiling | `agent tasks status` parses zero DRG fragments (baseline 13) and at most 70 shipped documents in total (baseline 107). | Performance | High | Open |
| NFR-003 | Output parity | Resolved governance selections, diagnostics and rendered charter text are byte-identical to `main` for every action (`specify`, `plan`, `tasks`, `implement`, `review`, `merge`) on this repository. | Correctness | High | Open |
| NFR-004 | No wall-clock regression | Interleaved A/B medians for both commands show no regression; absolute seconds are reported, never asserted (shared host, #6858). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No render cache or bypass flag | No cross-process catalog/charter cache, TTL, or `--no-charter-render` flag; only the existing in-process, per-change memoisation shape (#5526) may be used. | Technical | High | Open |
| C-002 | Single charter door | New charter reads live in `charter.activation` / `charter.offering` and stay behind the documented service seam; no second catalog or profile reader is introduced in `specify_cli`. | Technical | High | Open |
| C-003 | Warning contract unchanged | `CharterCatalogMissWarning` semantics, per-process dedup and the scope-filtered warning behaviour stay exactly as they are. | Regulatory | High | Open |
| C-004 | Backwards-compatible signature | `load_offering_catalog()` with no arguments keeps today's behaviour for every existing caller, including `charter validate` and JSON context surfaces. | Technical | High | Open |

### Key Entities

- **OfferingCatalog**: the deterministic set of available ids per built-in domain, plus
  `domains_present`. Gains an explicit domain scope; an unscanned domain contributes an
  empty set and is absent from `domains_present`.
- **AgentProfileRepository**: layered reader (built-in → org → project) of agent
  profiles; its DRG-backed lineage becomes on-demand instead of constructor-time.
- **GovernanceResolution**: the resolved paradigms/directives/template set. Its shape and
  values must not change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `charter context --action implement` parses ≤ 60 shipped documents, down from 265 (≥ 77 % fewer), with zero out-of-scope domain files — [build] · no-op passable: no
- **SC-002**: `agent tasks status` parses zero DRG fragments (down from 13) and ≤ 70 shipped documents (down from 107) — [build] · no-op passable: no
- **SC-003**: Rendered charter context and resolved governance selections are byte-identical to `main` for all six actions — [ratchet] · no-op passable: no
- **SC-004**: A maintainer alerted by a future "CLI is slow" report can point at the census guard that names the exact command and domain that grew its read set — [build] · no-op passable: no
