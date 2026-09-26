# Implementation Plan: Silent-Write Hardening Residuals

**Branch**: `fix/silent-write-hardening-residuals` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/silent-write-hardening-residuals-01M37QN4/spec.md`

## Summary

Close the three residual silent-write weaknesses that PR #4938's landing-pass squad confirmed still-live on current `main`, and close #4993 (epic #2720):

- **A (P1)** — Invert `doctor mission-state --fix`'s non-lane preservation from a registry **allowlist** to **preserve-by-default + explicit denylist**, so an unregistered future authoritative `event_type` (which the durable reader already preserves) is never silently quarantined. Extend the `_registry_authoritative_quarantine_violations` fail-closed guard to cover non-registry authoritative rows. Ship behind an ADR because it changes what `--fix` prunes.
- **B (P2)** — Consolidate the two divergent `charter.yaml` `catalog.mission` readers (ruamel round-trip vs `YAML(typ="safe")`) onto one shared accessor delegating to the canonical charter loader.
- **C (P3)** — Harden the traces merge driver's 3-way base-aware stale-drop path: recognize `~~~` fences equivalently to backtick fences, and give blocks a non-colliding key so duplicate headings do not collide. No broad contract refactor.

Technical approach = collapse the reader/repair contract into one rule (A), one canonical read path (B), and two bounded correctness edges (C). All three are independent seams (no shared guard — see C-001).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ruamel.yaml (already present — canonical charter loader), Typer/Rich (CLI, unchanged); no new dependencies (spec C-004)
**Storage**: append-only `status.events.jsonl` (authoritative mission event log); `charter.yaml` (project governance config); `traces/<category>.md` (mission trace artifacts)
**Testing**: pytest (+ existing red-first regression suites under `tests/status/`, `tests/**/test_mission_state_repair.py`, `tests/**/merge_driver*`, charter reader tests)
**Target Platform**: Linux/macOS/Windows CLI (`spec-kitty`)
**Project Type**: single project (`src/` + `tests/`)
**Performance Goals**: no perf regression; repair/merge-driver are batch/interactive, not hot-path
**Constraints**: fail-closed toward retention (spec C-003); byte-faithful traces merge (NFR-004); no `asset_preservation` routing (C-001); no traces-contract refactor (C-002); keep the #4938-folded duplicate-`event_id` guard fix intact (SC-005)
**Scale/Scope**: 3 findings, ~6 source files, 1 new ADR, 1 shared accessor; bounded surgical change set

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — Finding A collapses the reader's permissive contract and the repair's preserve contract into ONE rule powered by the existing `status/lifecycle_events.py` authority; Finding B collapses two `catalog.mission` readers into ONE accessor. Both move *toward* canonical sources (DIRECTIVE_001). ✅
- **Decision documentation (DIRECTIVE_003)** — Finding A's behavioral change to `--fix` pruning is recorded in a new Accepted ADR under `docs/adr/3.x/` (FR-003). ✅
- **DDD + tiered rigour** — status event-log repair and merge semantics are high-rigour (data-loss adjacent) → red-first tests + fail-closed guard; charter reader and traces edges are moderate. ✅
- **ATDD-first / red-first** — each finding ships with a test that fails against the pre-fix code and passes after (spec Independent Tests; SC-001/SC-003). ✅
- **Locality of change (DIRECTIVE_024)** — three bounded seams; no cross-cutting refactor (C-002 fences the traces driver). ✅
- **Campsite (DIRECTIVE_025)** — folds in the adjacent B + C hardening the squad surfaced while the context is loaded; corrects #4993's reader count. ✅
- **Terminology canon** — Mission vocabulary only (C-005). ✅

No violations to justify → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/silent-write-hardening-residuals-01M37QN4/
├── plan.md              # This file
├── research.md          # Phase 0 output (denylist determination, canonical loader, seam recipes)
├── data-model.md        # Phase 1 output (event classification model, accessor contract)
├── quickstart.md        # Phase 1 output (how to verify each finding)
├── contracts/           # Phase 1 output (repair-preservation contract, accessor contract, traces-merge contract)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── status/
│   ├── store.py                 # is_non_lane_event (reader) — reference contract for A (read; likely unchanged)
│   └── lifecycle_events.py      # AUTHORITATIVE_NON_LANE_EVENT_TYPES registry + predicate (A: guard authority)
├── migration/
│   └── mission_state.py         # _is_preserved_non_lane_row, _canonicalize_status_row,
│                                #   _registry_authoritative_quarantine_violations (A: invert + extend guard)
├── cli/commands/
│   ├── charter/generate.py      # _read_catalog_mission_from_charter_yaml (B: delegate to shared accessor)
│   └── merge_driver.py          # _TRACE_FENCE_MARKER, _split_trace_blocks, _trace_block_key,
│                                #   _drop_stale_theirs_trace_blocks (C: tilde fence + block-key)
└── charter_runtime/preflight/
    └── references_refresh.py    # _read_catalog_mission_and_template_set (B: delegate to shared accessor)

# New shared accessor home: TBD in Phase 0 (Q2) — a module reachable from both cli.commands.charter
# and charter_runtime without a layer violation; likely alongside the canonical charter loader.

docs/adr/3.x/
└── 2026-09-23-N-mission-state-repair-preserve-by-default.md   # A: ADR (FR-003)

tests/
├── status/                      # non-lane registry + repair tests (A)
├── (mission_state repair test)  # extend red-first (A)
├── (charter reader tests)       # accessor parity (B)
└── (merge_driver traces tests)  # tilde fence + duplicate heading (C)
```

**Structure Decision**: single-project layout; changes are surgical edits to the seams above plus one shared accessor module and one ADR. No new top-level packages.

## Complexity Tracking

*No Constitution Check violations — section intentionally empty.*

## Parallel Work Analysis

The three findings are independent seams that touch disjoint files, so they parallelize cleanly after a shared research base.

### Dependency Graph

```
Phase 0 research (denylist + accessor home + seam recipes)
        │
        ├── Finding A: invert repair + extend guard + ADR   (status/, migration/)   [largest]
        ├── Finding B: single catalog.mission accessor       (charter/, charter_runtime/)
        └── Finding C: traces-driver hardening               (merge_driver.py)
        │
        └── Tracker close-out: #4993 close + reader-count correction (docs/changelog)
```

### Work Distribution

- **Sequential (shared base)**: Phase 0 research settles the denylist (A) and the accessor home (B) before implementation lanes open.
- **Parallel streams**: A, B, C touch disjoint files → three lanes with no file contention.
- **Lane ownership**: A ⇒ `status/lifecycle_events.py`, `migration/mission_state.py` (+ `status/store.py` read-only reference), ADR; B ⇒ `charter/generate.py`, `charter_runtime/preflight/references_refresh.py`, new accessor module; C ⇒ `cli/commands/merge_driver.py`.

### Coordination Points

- **Shared surfaces (landing-time regen, not lane contention)**: `docs/changelog/CHANGELOG.md`, `docs/api/cli-commands.md` (only if a help string changes), `src/specify_cli/_completion_manifest.json` — regenerate against current main at finalize/landing.
- **Concurrent PR #4950 alignment**: verified disjoint source + zero semantic coupling; if both edit `docs/*`/manifest, resolve as an ordinary rebase merge (per operator: no `doctor.py` fence needed).
- **Integration test**: full non-lane preservation + duplicate-`event_id` dedup suite green (SC-005), proving A changed the default without regressing preserved classes.
