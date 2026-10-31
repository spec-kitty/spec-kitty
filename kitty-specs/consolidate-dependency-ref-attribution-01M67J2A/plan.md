# Implementation Plan: Consolidate dependency-ref attribution (#6771)

**Branch**: `issue-6771-consolidate-dependency-ref-attribution` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/consolidate-dependency-ref-attribution-01M67J2A/spec.md`
**Input**: Mission specification from `kitty-specs/consolidate-dependency-ref-attribution-01M67J2A/spec.md`

## Summary

The closed-world attribution axis (`MergeOutcomeVerifier._unattributable_content`) flags every
content commit a lane's two-parent merge brought onto the target from an external dependency
branch, so a legitimately restacked mission cannot consolidate under `--strategy merge`, while
`--dry-run` (which returns before reconciliation) reports nothing.

The fix has two halves, both narrow and fail-closed:

1. **An explicit, recorded declaration.** `spec-kitty consolidate --dependency-ref <ref>`
   (repeatable) names the external ref a lane merged in. The claim builder resolves and
   verifies every declared ref — it must resolve, the mission branch must reach it, and none
   of its commits may sit on any mission spine (lane first-parent spines, the mission branch's
   first-parent spine) — and records the resulting exempt commit/blob/deletion sets on the
   claim. The verifier treats those commits exactly like commits that predate the window.
   An undeclared run is byte-for-byte today's behavior; a bad declaration REFUSEs before any
   ref moves.
2. **A forecast that agrees.** `--dry-run` builds the same claim (so a bad declaration refuses
   there too) and runs the same closed-world window scan over the content the landing would
   introduce (the mission branch plus the target), exiting non-zero and naming the commits —
   with the declaration that resolves them — before any ref moves.

Nothing widens the recognizer toward merge simulation (C-001): attribution stays "an approved
lane's own first-parent authorship" or "an explicitly declared, verified external ref".

## Technical Context

**Language/Version**: Python 3.11 (repo floor; `pyproject.toml`)
**Primary Dependencies**: Typer (CLI), Rich (console), `kernel.git` / `consolidation.git_probes` (git seams), `specify_cli.status` facade (event log)
**Storage**: git refs; `kitty-specs/<mission>/` artifacts; `.kittify/merge-state.json` (resumable consolidation state)
**Testing**: pytest; real-git-repo integration fixtures in `tests/terminus/conftest.py` (`build_coord_mission`, `restamp_approvals_at_lane_tips`, `run_terminus`); unit tests over `build_approved_wp_set` + `MergeOutcomeVerifier`
**Target Platform**: CLI (macOS/Linux), any git ≥ 2.38 repository
**Project Type**: single Python package (`src/specify_cli/`)
**Performance Goals**: an undeclared run adds zero git probes (NFR-001); a declared run adds one `rev-list` range per declared ref plus one first-parent range per lane and for the mission branch — all bounded by the window, never full history.
**Constraints**: fail-closed on any probe error; no new event-schema; no second copy of the spine rules.
**Scale/Scope**: ~4 source modules + 1 CLI option + 1 forecast step; ~500 lines of source change, dominated by docstrings.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the exempt sets are computed once in the claim builder
  (`resolve_external_dependency_refs`) and threaded to the verifier and the forecast; the
  window scan is one function (`_unattributable_in`) shared by `verify()` and the forecast.
- **ATDD-first / DIRECTIVE_034** — the red test drives the real CLI (`run_terminus`) and fails
  on today's `main`; the fix lands after it.
- **Locality of change (DIRECTIVE_024)** — no change to `_final_authored_walk`, the
  canceled-dependency machinery, or `describe()`'s pinned wording.
- **Fail-closed** — every new error path is a REFUSE; nothing new can PASS unevaluated.
- **No pack doctrine change** — this is product code, not doctrine; no `packs/` edit.

## Project Structure

### Documentation (this mission)

```
kitty-specs/consolidate-dependency-ref-attribution-01M67J2A/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # /spec-kitty.tasks output
└── traces/              # tooling-friction.md, approach.md, design-decisions.md
```

### Source Code (repository root)

```
src/specify_cli/
├── consolidation/
│   ├── reconciliation.py     # ApprovedWpCommitSet fields, resolve_external_dependency_refs,
│   │                         #   _unattributable_in (shared window scan), verifier exemptions,
│   │                         #   build_approved_wp_set(external_dependency_refs=...)
│   ├── phase_claim.py        # pass run.dependency_refs into the claim
│   ├── phase_gate.py         # defensive claim rebuild keeps them
│   ├── run_state.py          # _MergeRunState.dependency_refs
│   ├── state.py              # persist declared refs in the resumable record
│   └── forecast.py           # --dry-run closed-world forecast
└── cli/commands/
    └── consolidate.py        # --dependency-ref option, threading, help

tests/consolidation/
└── test_dependency_ref_attribution_6771.py   # red-first real-CLI repro + guard units
docs/
├── changelog/CHANGELOG.md    # [Unreleased] entry (root CHANGELOG.md is a symlink)
└── reference/…               # the consolidate strategy/recovery page the change touches
```

**Structure Decision**: single Python package; the change follows the existing consolidation
phase modules (claim → land → gate) rather than introducing a new module boundary, except for
the one resolver function that owns declaration verification.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| One new CLI flag plus a persisted state field | The issue asks for an explicit, recorded attribution; a silent auto-exemption would be a closed-world bypass (C-003) | Auto-attributing every merge second parent reproduces #4945: a removed WP riding a carrier lane is structurally identical |

## Implementation Concern Map

### IC-01 — Declaration resolution and verification

- **Purpose**: Turn operator-declared refs into a verified exempt commit/blob/deletion set, or REFUSE.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-002, NFR-003, C-001, C-002, C-003
- **Affected surfaces**: `consolidation/reconciliation.py` (`resolve_external_dependency_refs`,
  `_external_dependency_refusal`, `ApprovedWpCommitSet`, `build_approved_wp_set`)
- **Sequencing/depends-on**: none
- **Risks**: reusing the spine walk (C-002) rather than inventing a second one; keeping the
  empty-declaration path probe-free (NFR-001).

### IC-02 — Verifier exemptions (merge + squash)

- **Purpose**: Stop flagging the exempt set, without touching what else is flagged.
- **Relevant requirements**: FR-001, FR-006, FR-007, NFR-003, C-003
- **Affected surfaces**: `reconciliation.py` (`_unattributable_content`,
  `_unattributable_content_squash`, `_unattributable_in`, attribution hint on `VerifyResult`)
- **Sequencing/depends-on**: IC-01
- **Risks**: the `describe()` wording is pinned by the terminus suites — the recovery hint goes
  on `recovery_guidance()`, not inside `describe()`.

### IC-03 — CLI surface, run state and persistence

- **Purpose**: Carry `--dependency-ref` from the command line through the run record into the
  claim and the forecast.
- **Relevant requirements**: FR-005, NFR-004
- **Affected surfaces**: `cli/commands/consolidate.py`, `consolidation/run_state.py`,
  `consolidation/state.py`, `consolidation/phase_claim.py`, `consolidation/phase_gate.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `--resume` must re-derive the same claim; the declaration is persisted like the
  other run options so a resume does not silently lose it.

### IC-04 — Forecast parity

- **Purpose**: Make `--dry-run` build the claim and report the same closed-world verdict.
- **Relevant requirements**: FR-004, FR-005, NFR-004
- **Affected surfaces**: `consolidation/forecast.py`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: the forecast must not run merge-only axes (`_missing_approved` would false-fail
  before the landing); it scans the would-be window only.

### IC-05 — Docs, changelog and regression tests

- **Purpose**: Name the supported way to restack a mission, and pin the behaviors.
- **Relevant requirements**: SC-001..SC-004
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`, the consolidate recovery docs,
  `tests/consolidation/test_dependency_ref_attribution_6771.py`
- **Sequencing/depends-on**: IC-01..IC-04
- **Risks**: docs freshness (`check_docs_freshness --ci`) must stay at 0 errors; regenerate only
  the surface the diff touches.
