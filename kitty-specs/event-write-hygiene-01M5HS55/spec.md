# Mission Specification: Event write hygiene: retire dead write doors and private events imports

**Mission Branch**: `feat/event-write-hygiene` (lands as `issue-6614-6607-event-write-hygiene`)
**Created**: 2026-10-22
**Status**: Draft
**Input**: Issues #6614 and #6607 (epic #6608, ADR 2026-10-14-1), operator steer of 2026-10-22.

## Intent Summary (confirmed)

- **Primary actor:** a core maintainer preparing the one-canonical-writer cut (ADR 2026-10-14-1, EventBridge #6603). A second actor is the reviewer of a future `spec-kitty-events` lock refresh.
- **Trigger:** the event-ledger writers-and-readers map (gap rows G-11, G-16 and G-18) lists write doors nobody uses, a private library import, and hosted-era names on the produce seam.
- **Outcome:**
  - Every write door to `status.events.jsonl` and to the invocation index that production does not use is gone.
  - Core imports no private `spec_kitty_events` / `spec_kitty_tracker` symbol.
  - The produce seam's names no longer say "saas".
  - Gates keep each of these from coming back.
- **Invariant:** observable behaviour does not change.
  - Every surviving write path writes the same bytes.
  - The produce seam still has no default handler, and every `fire_*` call is a no-op until something registers.
  - The dependency range and lockfile are untouched.
- **Operator rulings (Decision Moments recorded):**
  - Delete the dead hosted lifecycle builder, rather than replacing its private import.
  - Migrate the test seeding in this mission.
  - Keep no compatibility aliases for the frozen `spec-kitty/event-router`, including the old timeout environment variable.

This mission is a **bulk edit**. It renames the produce-seam identifiers (`saas_fanout` → `status_fanout` / `lifecycle_fanout`). It also moves every test that seeds the status log through the retired door onto a test-only seeding helper. `occurrence_map.yaml` (written during plan) records per-category rules.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Only real write doors remain (Priority: P1)

A maintainer wrapping the status write path in the EventBridge port can list every module that may append to `status.events.jsonl` or to the invocation index. Every name on that list is a live production path, and a gate refuses any new door.

**Why this priority:** dead doors make the canonical-writer cut look larger than it is, and one of them is a non-atomic append.

**Independent Test:** the raw-append allowlist gate and a new door-absence gate pass on the mission branch and fail when a deleted door is reintroduced.

**Acceptance Scenarios:**

1. **Given** the mission branch, **When** a module re-adds a plain `append_event(feature_dir, event)` to the status store, **Then** the door gate fails and names it.
2. **Given** the mission branch, **When** any module other than the invocation writer opens `ops-index.jsonl` for writing, **Then** the invocation-index gate fails.
3. **Given** a test that needs a pre-seeded status log, **When** it seeds rows, **Then** the rows go through the atomic write primitive and land byte-identical to what the old door wrote.

### User Story 2 - A lock refresh cannot flip strictness behind core's back (Priority: P1)

A reviewer of a `spec-kitty-events` lock refresh does not need to audit private library internals. Core imports none, and a boundary gate fails on any private import.

**Why this priority:** 11.1.0 widens a private map that used to switch strict validation on. Core's only reader of that map sits on a dead hosted path.

**Independent Test:** the shared-package boundary gate fails when a `src/` module imports `spec_kitty_events.<module>._name` or a `_`-prefixed module, and passes on the mission branch.

**Acceptance Scenarios:**

1. **Given** the mission branch, **When** the boundary gate scans `src/`, **Then** it finds no private `spec_kitty_events` / `spec_kitty_tracker` import.
2. **Given** a synthetic module that imports a private symbol, **When** the gate's scanner runs on it, **Then** it reports the import (non-vacuity).
3. **Given** the dead hosted lifecycle builder, **When** the mission lands, **Then** it no longer exists, and nothing in `src/` referenced it.

### User Story 3 - The produce seam speaks transport-neutral language (Priority: P2)

A future transport owner registers a status or lifecycle fan-out handler through transport-neutral names. The seam behaves exactly as before: no default handler, non-raising, bounded per-handler wall time.

**Why this priority:** "saas" is residue vocabulary after #6164 and misleads readers about what the seam is.

**Independent Test:** a stub-handler contract test registers a handler through the new names, fires each `fire_*` call and observes delivery. A reset registry is a no-op.

**Acceptance Scenarios:**

1. **Given** a fresh registry, **When** any `fire_*` is called, **Then** nothing is invoked and nothing raises.
2. **Given** a stub registered via the renamed registration function, **When** the matching `fire_*` is called, **Then** the stub receives the kwargs once.
3. **Given** the new timeout environment variable set to a value, **When** a handler runs, **Then** that bound applies. The old variable name has no effect.

### Edge Cases

- A test monkeypatches the deleted `store.append_event` to simulate a write failure. It is retargeted to the surviving primitive, or removed if it only tested the dead door.
- A test uses `append_event_log` for its contract validation. That validation lives on in `append_event_stream_log`, so the test moves there.
- Test files that reach into `spec_kitty_events` private internals (reducer helpers) are not production code and are out of scope. They get no allowlist (that would be priced debt); public equivalents are requested upstream.
- Documentation, the dead-symbol allowlist and the release coverage baseline that name deleted or renamed symbols are updated in the same change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Delete dead status write doors | As a maintainer, I want the non-atomic `store.append_event`, `append_event_verified` and `append_primary_checkout_event_verified` removed, with `_unsafe.__all__` shrunk (the `ALLOWED_CALLERS` baseline stays: `status_service` still imports live primitives), so that only live atomic primitives remain. | High | Open | [build] | no — the door gate fails on main, where these names still exist |
| FR-002 | Delete the dead coordination wrapper | As a maintainer, I want `coordination.status_service.append_event_log` removed, with its test seeds moved to `append_event_stream_log`, so that the coordination shell has one write funnel. | High | Open | [build] | no — the gate's forbidden-name list fails on main |
| FR-003 | Delete the duplicate invocation-index writer | As a maintainer, I want `invocations_cmd.append_to_index` removed and its tests retargeted onto the invocation writer, so that one module writes the index. | High | Open | [build] | no — the index gate fails on main |
| FR-004 | Test seeding helper | As a test author, I want a test-only helper that seeds status rows through the atomic primitive, so that about 195 test files keep their fixtures without the deleted door. | High | Open | [build] | no — imports of the deleted door fail collection |
| FR-005 | Door-absence and index-writer gates | As a reviewer, I want architectural gates that fail when a deleted door returns or a second index writer appears. Each has a non-vacuity floor and a self-test. | High | Open | [build] | no — red on main, with a same-fixture positive control |
| FR-006 | Delete the dead hosted lifecycle builder | As a maintainer, I want `build_saas_lifecycle_queue_event`, `_canonical_lifecycle_payload_for_saas` and `_validate_lifecycle_payload` removed, with the facade export and tests, so that core's only private library import goes with them. | High | Open | [build] | no — the private-import gate is red on main |
| FR-007 | Private-import boundary gate | As a reviewer, I want the shared-package boundary gate to fail on any `_`-prefixed module segment or imported name under `spec_kitty_events` / `spec_kitty_tracker` in every production root under `src/`, with no allowlist, so that the boundary is public-only. Test files that read library internals stay out of scope; public equivalents are requested upstream. | High | Open | [build] | no — red on main through `lifecycle_events.py` |
| FR-008 | Transport-neutral produce-seam names | As a maintainer, I want every "saas" identifier, log label and docstring in `status/adapters.py`, and their references, renamed to transport-neutral names with no aliases. The timeout variable becomes `SPEC_KITTY_STATUS_FANOUT_TIMEOUT`. | Medium | Open | [build] | no — the "no saas in adapters.py" check is red on main |
| FR-009 | Stub-handler contract test | As a future transport owner, I want a contract test that pins the empty-registry no-op, delivery to a registered stub and the bounded timeout through the new names, so that the rename keeps behaviour. | Medium | Open | [ratchet] | yes — paired with the empty-registry control on the same fixture |
| FR-010 | Docs and gap table | As a reader, I want the event-ledger architecture page's G-11, G-16 and G-18 rows and a changelog entry to reflect the closure, so that the gap table stays truthful. | Low | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behaviour preservation | 0 changes to bytes written by surviving write paths. The seeding helper produces byte-identical rows, proven by a test comparing against `serialize_event_line`. | Reliability | High | Open |
| NFR-002 | Quality gates | `ruff check`, `ruff format --check --force-exclude` and `mypy` report 0 issues on changed modules. No new suppressions. Complexity stays at or below 15. | Maintainability | High | Open |
| NFR-003 | Coverage | Diff coverage of at least 90% on changed `src/` lines. | Maintainability | Medium | Open |
| NFR-004 | Gate non-vacuity | Every new gate has a concrete floor of at least 1 scanned module or file and a self-mutation test that turns it red. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No dependency change | `uv.lock` and the `spec-kitty-events` / `spec-kitty-tracker` ranges stay untouched. | Technical | High | Open |
| C-002 | No canonical-writer work | Do not start the EventBridge port (#6603) or the Java writer (#6185 ruling). Add no new append path. | Technical | High | Open |
| C-003 | No hosted surfaces | Do not reintroduce or point at any hosted surface. No aliases are kept for `spec-kitty/event-router`. | Business | High | Open |
| C-004 | Packs untouched | Do not edit `packs/built-in/` or `packs/internal/`. | Technical | High | Open |
| C-005 | Red-first gates | Each new or extended gate is committed red against the pre-change tree before the change that turns it green. | Technical | High | Open |

### Key Entities

- **Write door:** a function outside the canonical shells that appends to an event log.
- **Produce seam:** the status/lifecycle fan-out registry that transports subscribe to (`status/adapters.py`).
- **Test seeding helper:** a test-only function that writes fixture rows through the production atomic primitive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 production-unused write doors to `status.events.jsonl` or the invocation index remain, verified by the gates. — [build] · no-op passable: no
- **SC-002**: 0 private `spec_kitty_events` / `spec_kitty_tracker` imports in `src/`. — [build] · no-op passable: no
- **SC-003**: 0 occurrences of "saas" (any case) in `status/adapters.py`. — [build] · no-op passable: no
- **SC-004**: Every test file that seeded the status log through the deleted door still passes with the same assertions. — [ratchet] · no-op passable: yes — paired with SC-001's gate on the same tree

## Assumptions

- A test that only exercised a deleted door's own behaviour (for example, the non-atomic append's monkeypatch tests) is deleted, not retargeted.
- Other "saas"/"hosted" residue outside the seam (for example `fanout_lifecycle_event_hosted` in `lifecycle_events.py`) is renamed only where it names the seam's own identifiers. The rest is recorded as follow-up, per Locality of Change.
