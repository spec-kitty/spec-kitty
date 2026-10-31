# Implementation Plan: System status actor

**Branch**: `issue-6722-system-status-actor` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/system-status-actor-01M67HTR/spec.md` (issue [#6722](https://github.com/spec-kitty/spec-kitty/issues/6722))

## Summary

Give the system status writers the structured actor #6400 gave the agent and operator
writers. A system event records `{tool: <the identity it records today>, role: "system",
profile: null, model: null}` — one new role value, one additive builder, `tool` unchanged
so every reader projection and every seed gate keeps its exact rule. Thirteen emit sites in
nine writer modules move onto it, and two compatibility seams are made shape-blind so a log
written before the change keeps reducing and keeps verifying.

## Technical Context

**Language/Version**: Python 3.11 (`src/`), `spec-kitty-events >=11.3.0,<12` for the shared decoder
**Primary Dependencies**: `spec_kitty_events` (`diary.decode_actor`, `StatusTransitionPayload`), `pydantic` (event models), `pytest`
**Storage**: `status.events.jsonl` (append-only event log, `src/specify_cli/status/store.py`) + the derived `status.json` snapshot
**Testing**: `pytest`; red-first through the pre-existing entry points (`finalize-tasks`, `reconcile`, `consolidate`, `migrate *`, the status reducer); the repository's `tests/status`, `tests/unit/migration`, `tests/migration`, `tests/consolidation`, `tests/lanes` suites
**Target Platform**: CLI (`spec-kitty`), Python 3.11, Linux/macOS/Windows
**Project Type**: single Python package + a frozen Java service tree (untouched)
**Performance Goals**: no measurable change — one dict literal per event where a string literal was
**Constraints**: no fifth actor key (#6721 owns `profile_source`); no wire change; `services/` and `contracts/` frozen (ADR `2026-10-29-1` D-9); stored rows are immutable
**Scale/Scope**: 13 emit sites across 9 writer modules, 1 new role value, 1 new builder, 2 compatibility seams, 1 docs section, 1 changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Verdict |
| --- | --- |
| **Single canonical authority** | Pass. The role vocabulary stays in `status/actor.ActorRole`; the actor builder stays in `status/actor.py`; the seed predicate stays `status/models.is_migration_actor`. New: one system builder and, in `backfill_runtime_state`, a *narrower* per-migration predicate that becomes shape-blind instead of learning a second shape rule. |
| **ATDD-first / red-first** (DIRECTIVE_034) | Pass. Every writer family gets a failing test observed on the base before the writer changes; the compatibility seams get their failing verification test before the tolerance. |
| **Terminology canon (Mission, not feature)** | Pass. No new user-facing term; `role: "system"` is a value of an existing field, documented in `docs/architecture/status-model.md`. |
| **Locality of change** (DIRECTIVE_024) / **smallest viable diff** | Pass. Nine one-line actor changes + one builder + two seams; no module is restructured, no reader changed. |
| **Boy Scout Rule** (DIRECTIVE_025) | Bounded by C-004: the two adjacent rough edges found (the duplicate seed predicate, the second `role` list) are fixed *only* where the mission already edits; nothing else is swept in. |
| **`__all__` convention** (C-007) | Pass. The new builder and role member are exported from `status/actor.py` and `status/__init__.py` following the existing pattern. |
| **Proof trail** | Pass. Spec FR-001…FR-013 ↔ SC-001…SC-005, one test family per writer family, plus the before/after reduction corpus. |
| **NO_FULL_HEAVY_SUITES_IN_MISSION** | Pass. Targeted suites only, listed in the PR body. |
| **Frozen paths** (ADR `2026-10-29-1` D-9) | Pass. Nothing under `services/`, `contracts/`, `acceptance-jvm/`. |

No violations: **Complexity Tracking** is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/system-status-actor-01M67HTR/
├── plan.md              # this file
├── spec.md              # authored
├── research.md          # discovery + Phase 0 findings
├── reasons-canvas.md    # SPDD canvas
├── data-model.md        # Phase 1: the actor shapes, the role vocabulary, the compatibility rule
├── quickstart.md        # Phase 1: how to prove the change by hand
├── contracts/
│   └── system-actor.md  # Phase 1: writer → tool identity table, and the reader invariants
└── tasks.md             # Phase 2 (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── status/
│   ├── actor.py                 # + ActorRole.SYSTEM, + build_system_actor  (the only new authority)
│   ├── models.py                # docstrings only: the system shape is one of the accepted shapes
│   ├── __init__.py              # export the new builder next to its siblings
│   └── bootstrap.py             # WRITER 1: the finalize-tasks seed
├── lanes/recovery.py            # WRITER 2: the recovery catch-up
├── consolidation/
│   ├── done_bookkeeping.py      # WRITER 3: approval replay + done mark (+ the shared merge identity)
│   ├── preflight.py             # WRITER 4: the done-write refusal probe + the review-artifact override annotation
│   ├── approved_attestation.py  # WRITER 5
│   └── canceled_attestation.py  # WRITER 6
└── migration/
    ├── wp_status_backfill.py             # WRITER 7
    ├── backfill_runtime_state.py         # WRITER 8 (+ SEAM A: shape-blind seed predicate, SEAM B: shape-only verification tolerance)
    └── verdict_provenance_backfill.py    # WRITER 9

tests/
├── status/test_system_actor_6722.py            # the shape, the builder, the decoder, the reader invariants
├── unit/migration/test_system_actor_6722.py    # the three seed writers + the two seams
├── consolidation/test_system_actor_6722.py     # bookkeeping + both attestations + the override
└── lanes/test_system_actor_6722.py             # the recovery catch-up
```

**Structure Decision**: single Python package; each new test module sits in the suite that
already owns the writer family it covers, so a maintainer looking for a reader's regression
finds it where its readers live. No new package, no new directory.

## Phase 0 — Research outcomes (see [research.md](research.md))

All clarified; nothing carried forward as `NEEDS CLARIFICATION`. The four load-bearing
findings:

1. The 4-key dict actor already flows through the whole pipeline (`TransitionRequest.actor`,
   `emit_inner_state_changed(actor=...)`), so no plumbing changes.
2. Neither the shared events decoder nor the Java `Actor` handle enumerates `role`, and both
   are frozen — `role: "system"` needs no events release and no frozen-path edit.
3. `actor_identity_str` maps a dict to its `tool`, so keeping the recorded identity in `tool`
   makes every seed gate shape-blind for free.
4. Exactly two seams break on a shape change: `backfill_runtime_state._is_migration_actor`
   (identity equality against the constant) and `backfill_runtime_state._seed_row_mismatch`
   (byte-semantic payload comparison against an immutable pre-change row).

## Phase 1 — Design

### The system actor

```
build_system_actor(tool: str) -> {"tool": tool, "role": "system", "profile": None, "model": None}
```

* `tool` is passed whole — never through `parse_agent_boundary_string`, which would split
  `migration:backfill_runtime_state` into a tool and a model.
* `profile` and `model` are literals, not arguments: there is no caller that may supply one,
  so "no invented identity" is enforced by the signature rather than by a rule in prose.
* An empty or blank `tool` raises, because an actor with no identity names nobody; every
  call site passes a non-empty constant or a resolved identity.

### Writer table (also `contracts/system-actor.md`)

| Writer site | `tool` |
| --- | --- |
| `status/bootstrap.py` | `finalize-tasks` |
| `lanes/recovery.py` | `recovery` |
| `consolidation/done_bookkeeping.py` (×2) | `merge` |
| `consolidation/preflight.py` — done-write refusal probe | `merge` |
| `consolidation/preflight.py` — override annotation event | resolved operator identity |
| `consolidation/approved_attestation.py` | resolved operator identity |
| `consolidation/canceled_attestation.py` | resolved operator identity |
| `migration/wp_status_backfill.py` (×2) | `migration:backfill_wp_status` |
| `migration/backfill_runtime_state.py` (×2) | `migration:backfill_runtime_state` |
| `migration/verdict_provenance_backfill.py` | `migration:verdict_provenance_backfill` |

`RECOVERY_ACTOR`, `WP_STATUS_BACKFILL_ACTOR` and the two `BACKFILL_ACTOR` constants keep
their names but hold the built dict; the `migration:` identity is also kept in a module
constant so the data-plane tests and the seams can compare an identity rather than a shape.

### Reader invariants the change must not move

1. `actor_identity_str(event.actor)` — identical for both shapes; the snapshot `actor` slot,
   the guards and the display stay byte-identical.
2. `is_migration_actor` — the prefix test on the projected identity; true for a string seed,
   true for a structured seed.
3. The reducer's seed arm (`status/reducer.py`) and `validate_timestamp_continuity` — both
   route through (2) since #6271, so they are unchanged by construction and pinned by test.
4. The consolidation work-window rule (`consolidation/wp_attribution.py`) — through (2).
5. `actor_full_identity` / `actor_compact_identity` — **not changed**. No reader compares a
   seed's full identity (every caller excludes seeds first, audited in `research.md` §3); a
   mixed-shape reduction test pins that the difference is unobservable.

### Compatibility seams

- **Seam A** (`backfill_runtime_state._is_migration_actor`): becomes "the projected identity
  equals *this* migration's identity", so it recognises the row the same module wrote before
  the change. Kept deliberately narrower than the shared prefix predicate (it answers "this
  backfill's seed", not "any seed") and documented as such.
- **Seam B** (`backfill_runtime_state._seed_row_mismatch`): after the existing two
  tolerances, tolerate a row whose only difference from the rebuilt expectation is the
  actor's *shape* — same projected identity, both shapes in {str, 4-key dict}. A different
  identity stays a hard mismatch. Rows are immutable and deduplicated on `event_id`, which
  is why the tolerance lives here and not in a rewrite of stored rows.

### Alternatives considered

1. **Keep system writers on strings** (answer the issue "no"). Rejected: the issue's premise
   is the two-shape debt, and #6400 already deferred it once.
2. **`tool: "spec-kitty"` for every system writer.** Rejected: collapses six auditable
   identities into one and breaks `is_migration_actor` for every new seed.
3. **Strip `migration:` from `tool` and classify seeds by `role`.** Rejected: re-decides
   #6093/#6271 and leaves old rows classified by a different rule than new ones.
4. **Add a `role: "operator"` for the attestations.** Rejected: a second new value for one
   family; the attestation is identified by `policy_metadata`, and the operator identity is
   already in `tool`.
5. **Migrate stored rows to the new shape.** Rejected: rows are immutable, and C-003 forbids
   rewriting them; the readers are the compatibility surface.

### Risks

| Risk | Mitigation |
| --- | --- |
| The shape leaks into a gate through a projection not in the audit | A mixed-shape reduction test over a constructed log, plus the byte-identical corpus test over every committed mission log. |
| A pre-change seed row is reported as tampered | Seam B, with a paired negative test on a genuinely different identity. |
| Overlap with sibling PR #6838 on `status/actor.py` | Additive lines only (a new enum member and a new function); no existing builder, constant or predicate touched. |
| A future events release enumerates `role` | FR-011 test pins the decoder's actual rule, so the failure appears here and not at a user's log. |

## Complexity Tracking

Empty — no Charter Check violations.

## Implementation Concern Map

### IC-01 — The system actor authority and the role vocabulary

- **Purpose**: one builder and one new role value, so no writer assembles the four keys by hand and the vocabulary stays closed.
- **Relevant requirements**: FR-001, FR-008, FR-011, NFR-001, NFR-002, C-001, C-006
- **Affected surfaces**: `src/specify_cli/status/actor.py`, `src/specify_cli/status/models.py` (docstrings), `src/specify_cli/status/__init__.py`
- **Sequencing/depends-on**: none (first)
- **Risks**: the builder must not route the identity through `parse_agent_boundary_string`; the enum member must not leak into `role_for_hop`, which stays a two-value answer for a hop.

### IC-02 — The interactive-surface system writers (bootstrap, recovery, consolidation bookkeeping, override)

- **Purpose**: move the writers whose event the operator sees in a board or an audit trail — bootstrap seeds, recovery catch-up, merge bookkeeping, the done-write refusal probe, and the review-artifact override annotation — onto the system actor.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-005, C-005
- **Affected surfaces**: `src/specify_cli/status/bootstrap.py`, `src/specify_cli/lanes/recovery.py`, `src/specify_cli/consolidation/{done_bookkeeping,preflight}.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: at the override site the delta slot's pinned `str` shape must stay a string while the event actor becomes structured — two different values from one variable.

### IC-03 — The attestation writers

- **Purpose**: both consolidation attestations record the resolved operator identity in `tool` and `role: "system"`, without gaining a review role or losing their `policy_metadata` identity.
- **Relevant requirements**: FR-006
- **Affected surfaces**: `src/specify_cli/consolidation/{approved_attestation,canceled_attestation}.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the approved-reviewed attestation is skipped by the reviewer read on `policy_metadata`, never on `role`; a test must hold that line.

### IC-04 — The migration seed writers and the two compatibility seams

- **Purpose**: the three in-process backfills write structured seeds that still classify as seeds, and a corpus seeded before the change still verifies.
- **Relevant requirements**: FR-007, FR-009, FR-010, FR-012, C-003
- **Affected surfaces**: `src/specify_cli/migration/{wp_status_backfill,backfill_runtime_state,verdict_provenance_backfill}.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the highest-risk concern. Seam A must not widen to the shared prefix predicate; Seam B must tolerate shape and nothing else.

### IC-05 — The proof: corpus, mixed-shape and decoder pins

- **Purpose**: the tests that prove the readers did not move — a before/after reduction over every committed mission log, a mixed-shape log reduction, the seed-gate matrix, and the decoder/role pin.
- **Relevant requirements**: FR-011, FR-012, NFR-003, SC-002, SC-003, SC-004
- **Affected surfaces**: `tests/status/`, `tests/unit/migration/`, `tests/consolidation/`, `tests/lanes/`
- **Sequencing/depends-on**: IC-02, IC-03, IC-04 (it asserts their outputs)
- **Risks**: the corpus comparison needs the pre-change reducer output, taken on the base commit before the writers change (red-first), not from a rewrite.

### IC-06 — Docs and changelog

- **Purpose**: replace the "Still strings" boundary with the system-actor rule and the three-value role vocabulary, and record the change.
- **Relevant requirements**: FR-013, SC-005
- **Affected surfaces**: `docs/architecture/status-model.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-05 (written against proven behaviour)
- **Risks**: the status-model page is not in the docs-freshness generated set; verify with `check_docs_freshness --ci` rather than a rebuild.
