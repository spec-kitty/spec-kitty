# Implementation Plan: Backfill runtime state on a slug-identified legacy Mission

**Branch**: `issue-6689-backfill-claim-slots` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/backfill-runtime-state-idempotent-claim-slots-01M67HR8/spec.md`
**Input**: Mission specification from `kitty-specs/backfill-runtime-state-idempotent-claim-slots-01M67HR8/spec.md`

## Summary

`migrate backfill-runtime-state` mints a deterministic `planned -> claimed` carrier row
whose envelope `mission_id` it collapses to `None` whenever the Mission's resolved id
equals its slug. `StatusEvent.to_dict()` omits the null field, so the persisted row carries
no `mission_id`; `read_event_stream` then re-resolves that row's slug through `meta.json`
and injects the slug-valued id back. The verifier's rebuilt expectation (`mission_id=None`)
therefore never equals the row read back off disk (`mission_id=<slug>`), and
`verify_backfill` refuses forever — the project-wide upgrade block of #6689.

The fix separates the two values `_mission_id` currently conflates: the **seed namespace**
(deterministic id input, unchanged: declared id or directory name) and the **envelope
identity** (what the row declares on disk: the `mission_id` `meta.json` declares, or
nothing when it declares none). Only the envelope changes, so every existing corpus keeps
its seed ids (idempotency, NFR-002) and the persisted bytes become exactly what every
reader already re-derives. Fail-closed behaviour is untouched: the verifier's tolerance
set is not widened anywhere.

## Technical Context

**Language/Version**: Python 3.11 (project floor; see `pyproject.toml`), typed with mypy
**Primary Dependencies**: Typer (CLI), pytest, `spec_kitty_events` reducer package — no new
dependency; the fix touches one module and adds no import beyond what is already there
**Storage**: JSONL event log (`status.events.jsonl`) + `meta.json` per Mission under
`kitty-specs/`; append-only, durability-verified writes via
`status._unsafe.append_event_stream_atomic_verified`
**Testing**: pytest (`tests/unit/migration/` for the engine, `tests/specify_cli/migration/`
for the CLI-facing regression); `pytest.mark.fast` for the pure-logic unit rows and a
CLI-driven end-to-end row through `spec-kitty migrate backfill-runtime-state`
**Target Platform**: operator CLI (Linux/macOS/Windows); no platform-specific code path
**Project Type**: single Python package (`src/specify_cli/`) with a pytest suite in `tests/`
**Performance Goals**: no measurable change — the fix reads `meta.json` once more per
Mission at seed-build time (already loaded for anchor synthesis in most paths); backfill is
a migration command, not a hot path
**Constraints**: seed `event_id`s must not change for any existing corpus (else a
half-migrated project gets a duplicate row per WP and loses idempotency); the verifier's
tolerance set must not grow; `status/store.py` (the reader) must not change
**Scale/Scope**: 1 source module (`src/specify_cli/migration/backfill_runtime_state.py`),
2 new test files, 1 changelog entry, 1 docs note in the upgrade how-to

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The carrier's envelope keeps exactly one constructor, `_claim_carrier`; both the builder and the pre-#2985 reference go through it (C-001). The declared-vs-namespace split is expressed once, in helpers beside `_mission_id`. |
| ATDD-first / red-first (DIRECTIVE_034) | The regression row is written and observed failing on `main` before the fix, through the real `migrate backfill-runtime-state` entry point. |
| Smallest viable diff + locality of change (DIRECTIVE_024) | One predicate's semantics change plus one new helper. No refactor of the verifier, no reader change, no `wp_status_backfill` change. |
| Fail-closed discipline | No new tolerance. The three fail-closed classes are re-proved on the same fixture in the same PR (FR-006, FR-007, NFR-003). |
| Terminology canon | "Mission", "seed carrier row", "declared mission id", "seed namespace" — no `feature*` vocabulary introduced. |
| No full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`) | Local runs are the touched test files plus the two owning migration suites; CI owns the rest. |
| Pre-existing failure reporting | Any red reproduced on pristine `origin/main` is named in the PR `## Deferred` with its issue reference (#6798, #6801, #6816 family). |

## Project Structure

### Documentation (this mission)

```
kitty-specs/backfill-runtime-state-idempotent-claim-slots-01M67HR8/
├── plan.md              # This file
├── research.md          # Phase 0 output (created at discovery, extended here)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — not created here)
```

No `contracts/` directory: this Mission defines no external interface (it changes an
internal migration's envelope construction). `meta.json` records `"contracts": "none"`
with a rationale, per the plan prompt's rule for interface-free missions.

### Source Code (repository root)

```
src/specify_cli/migration/backfill_runtime_state.py   # the fix (writer + expectation)
tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py
                                                     # red-first regression + fail-closed controls
tests/unit/migration/test_backfill_runtime_state.py   # existing unit suite (extended, unchanged assertions)
docs/changelog/CHANGELOG.md                           # [Unreleased] entry (#6689)
docs/development/how-to/*                              # upgrade/backfill note the change touches
```

**Structure Decision**: single-package layout; the fix lands where the defect lives
(`src/specify_cli/migration/backfill_runtime_state.py`) and the regression lands in the
Migration subsystem's own test directory (`tests/specify_cli/migration/`), matching the
per-issue file convention already used there (`test_residue_shared_walkers_6669.py`,
`test_mission_id_primary_leg.py`).

## Complexity Tracking

No charter violations. The Mission is a single-module correctness fix; the only complexity
added is one small helper that names an existing implicit distinction (declared identity vs
seed namespace).

## Implementation Concern Map

### IC-01 — Envelope identity is the declared mission id, the seed namespace is unchanged

- **Purpose**: Make the minted carrier row's envelope `mission_id` equal the value
  `meta.json` declares, so the row read back off disk is the row the verifier rebuilds;
  keep the seed-id namespace (`declared or directory name`) byte-identical so no existing
  corpus is re-seeded.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-009; NFR-001, NFR-004;
  C-001, C-002.
- **Affected surfaces**: `src/specify_cli/migration/backfill_runtime_state.py` —
  `_mission_id` (kept as the namespace authority), a new `_declared_mission_id` helper,
  `_claim_carrier` (the single envelope constructor), `_build_seed_events` and
  `_legacy_contract_carriers` (both callers).
- **Sequencing/depends-on**: none — this is the whole fix.
- **Risks**: any change that also moves the namespace root would silently re-seed every
  already-migrated corpus; a test must pin the seed id for the slug-identified Mission to
  its pre-fix value. `_seeded_frontmatter_slots` and `_verify_claim_slot_witnesses` also
  look up seed ids by namespace, so they must keep working unchanged.

### IC-02 — The proof: red-first regression through the production CLI, with fail-closed controls on the same fixture

- **Purpose**: Prove the reported shape converges through
  `spec-kitty migrate backfill-runtime-state --mission <slug>` (not a helper), that a second
  run is a no-op, and that the same fixture still aborts under tampering, a missing seed,
  and a stripped frontmatter.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-008; NFR-002, NFR-003; SC-001 –
  SC-003 (tactic `acceptance-criteria-non-vacuity`: one shared fixture, positive control for
  every refusal).
- **Affected surfaces**:
  `tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py` (new),
  `tests/unit/migration/test_backfill_runtime_state.py` (existing, extended).
- **Sequencing/depends-on**: IC-01.
- **Risks**: a regression that only asserts `verify_backfill(...).ok` would stay green if
  the verifier were weakened; the suite must assert the specific error text/class for each
  fail-closed class as well as the persisted row's bytes.

### IC-03 — The operator-facing record: changelog and the upgrade how-to

- **Purpose**: Tell an operator hitting this block what changed, that a re-run converges,
  and that a half-migrated project does not need a hand-edit.
- **Relevant requirements**: none directly (delivery hygiene); C-004 scope boundary.
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (`[Unreleased]`), the upgrade/backfill
  how-to that documents `migrate backfill-runtime-state`.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**: docs freshness gate (`scripts.docs.check_docs_freshness --ci`) must stay at
  errors=0; regenerate only the surface this diff touches.
