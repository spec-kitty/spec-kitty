# Implementation Plan: Optional Lamport clock consumer audit

**Branch**: `issue-6414-optional-lamport-clock-consumer-audit` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Issue #6414 (parent epic #6411). Discovery evidence: [research.md](./research.md).

## Summary

Record the audit the issue asks for — every core consumer of `Event.lamport_clock` and of
the `spec_kitty_events` ordering surface, each with a verdict and a proof test — and fix
the single defect it finds: `specify_cli.status.migrate_lifecycle_envelope` writes
`lamport_clock: 0` (a *clocked* position at zero) for legacy rows that never recorded a
clock, where the pinned contract has an explicit unclocked representation (`null`).
Everything else about the two 11.0 breaks (optional clock; 4-tuple
`status_event_sort_key`) is proven inert for core by tests over a mixed
clocked/unclocked stream. No ordering behaviour changes: the CLI keeps its wall-clock
`(at, event_id)` fold (#6609 owns that direction, parked post-GA).

## Technical Context

**Language/Version**: Python 3.11 (`pyproject.toml` `requires-python`), single package `src/`.
**Primary Dependencies**: `spec-kitty-events>=11.3.0,<12` (pinned floor; `pyproject.toml:80`) — the
ordering authority (`ordering.canonical_order_key`), `Event.lamport_clock: Optional[int]`.
**Storage**: append-only JSONL event logs (`kitty-specs/<mission>/status.events.jsonl`,
`.kittify/canonical-events.jsonl`); the migration rewrites whole files atomically with a
`.pre-migration.bak` snapshot.
**Testing**: pytest, tiered marks (`fast`, `integration`, `git_repo`); new tests are `fast`
except the migration tests, which reuse the existing suite's `integration` + `git_repo` marks.
**Target Platform**: Linux/macOS/Windows CLI (no platform-specific primitives added).
**Project Type**: single project (CLI).
**Performance Goals**: no measurable change; the migration is a one-shot upgrade pass, and the
added tests add < 5 s to their shards.
**Constraints**: no new import outside `specify_cli.status`; the migration stays idempotent and
whole-file atomic; the strict 14-key envelope keeps every key present (nullable as explicit `null`).
**Scale/Scope**: 1 production file (`status/migrate_lifecycle_envelope.py`), 1 reference doc,
3 test modules, 1 changelog entry.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status |
| --- | --- |
| Single canonical authority | Pass — the ordering key stays `spec_kitty_events.ordering.canonical_order_key`; core does not re-implement it, and the migration uses the contract's own unclocked representation instead of a local sentinel. |
| External contract packages (consume, do not fork) | Pass — read-only use of the pinned public package; no vendoring, no version bump, no shim. |
| ATDD-first / red-first | Pass — the migration fix lands after a failing test that goes through the existing `migrate_lifecycle_envelope` entry point. |
| Locality of change (DIRECTIVE_024) | Pass — one production edit at the exact line the issue named; the rest is documentation and tests. |
| Terminology canon (Mission vs Feature) | Pass — "mission" used throughout; "lifecycle envelope" / "status event" are the repo's own terms (`docs/context/`). |
| Documentation Standards | Pass — a reference page under `docs/development/reference/` plus one `[Unreleased]` changelog entry with a `(#6414)` reference. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Pass — targeted modules only; CI owns the full sweep. |
| Pre-existing Failure Reporting Rule | Pass — #6798/#6801/#6816/#5927 cited in the PR's `## Deferred` and the issue matrix. |

No violations; `## Complexity Tracking` not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/optional-lamport-clock-consumer-audit-01M68ZMF/
├── plan.md              # This file
├── research.md          # Phase 0 (discovery findings, done)
├── spec.md              # Mission specification
├── issue-matrix.json    # #6414 + the four cited pre-existing issues
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/status/
└── migrate_lifecycle_envelope.py     # the one production edit (sentinel 0 -> None)

docs/development/reference/
└── optional-lamport-clock-consumers.md   # the durable audit record

docs/changelog/
└── CHANGELOG.md                      # [Unreleased] entry (root CHANGELOG.md is a symlink)

tests/status/
├── test_optional_lamport_clock_consumers.py       # mixed-stream + inventory proofs (WP01)
└── test_optional_lamport_clock_migration.py       # red-first migration sentinel proofs (WP02)
```

**Structure Decision**: single project. The audit record is a `docs/development/reference/`
page because that directory already holds the consumer/contract references a maintainer
consults when a shared-package contract moves (see `docs/development/reference/` siblings),
and it is covered by `scripts.docs.check_docs_freshness`. Tests sit beside the existing
`tests/status/` suites they extend rather than in a new directory.

## Implementation Concern Map

### IC-01 — Mixed-stream proofs and the audit record

- **Purpose**: Turn the "no consumers found" claim into a checked inventory, and prove that a
  mixed clocked/unclocked stream cannot change core lane state.
- **Relevant requirements**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, SC-001, SC-003, SC-004
- **Affected surfaces**: `docs/development/reference/optional-lamport-clock-consumers.md`,
  `tests/status/test_optional_lamport_clock_consumers.py`, `docs/development/README.md` (index entry if one exists)
- **Sequencing/depends-on**: none
- **Risks**: the inventory test must not become a brittle "grep every file" statement; it scans
  `src/` for the ordering identifiers and requires each hit to be listed in the audit doc, so a
  new consumer fails loudly while a moved line does not.

### IC-02 — The migration sentinel

- **Purpose**: Stop the upgrade migration asserting a clocked position (`0`) for a row that never
  recorded a clock; emit the contract's unclocked representation (`null`) instead.
- **Relevant requirements**: FR-003, FR-004, FR-005, SC-002, SC-005
- **Affected surfaces**: `src/specify_cli/status/migrate_lifecycle_envelope.py` (module docstring +
  the one assignment), `tests/status/test_optional_lamport_clock_migration.py`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: none (the audit doc in IC-01 records the verdict IC-02 implements; they
  land in the same PR, order-independent)
- **Risks**: the migration is byte-identical-idempotent today — the fix must keep every envelope key
  present (only the value changes) so `_is_already_strict_shaped` still recognises a re-run, and
  already-migrated `0` rows must stay untouched rather than being rewritten.

## Phase Plan

- **Phase 0 — research (done)**: contract direction, consumer inventory, fix boundary (research.md D1-D5).
- **Phase 1 — design**: no data model or API contract changes; the only contract touched is the
  on-disk envelope value for one key, documented in the audit page's "Residual" section.
- **Phase 2 — tasks**: two work packages, IC-01 then IC-02 (single-branch topology, sequential).
- **Phase 3 — implement/review**: red-first for WP02; WP01's mixed-stream tests are
  characterization proofs that must pass on the untouched read paths and keep passing.
