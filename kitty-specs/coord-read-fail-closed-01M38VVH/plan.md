# Implementation Plan: Coord Reads Fail Closed

**Branch**: `fix/coord-read-fail-closed` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/coord-read-fail-closed-01M38VVH/spec.md`

## Summary

Close two P0 destructive-write bugs (#4959 tracer clobber, #4966 decision-ledger husk split-brain) at their shared root: the placement **read** seam (`src/mission_runtime/resolution.py`) returns an empty-PRIMARY document on an unresolved/unmaterialised coord-topology read, and readers act on it as authoritative. Per operator decision `DM-01M38VWD3KKSSTZNCK9V00N3TJ`, the fix is **seam-level**: the read seam **raises** a typed fail-closed error on an unresolved/unmaterialised coord read (extending the posture it already has for the `NONE`/deleted state, #4403), so both surfaces and any future reader inherit fail-closed. The load-bearing work is the **blast-radius audit**: every caller of the read seam must handle the raise (refuse / materialise / resolve-to-authoritative), non-coord callers must be unaffected, and any caller legitimately relying on empty-PRIMARY must be adapted explicitly.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none new (spec C-004). Stdlib + existing mission_runtime placement seam, retrospective tracer writer, decisions service, acceptance reader.
**Storage**: coord-topology partitions — `traces/<cat>.md`, `decisions/` ledger + `meta.json` (authoritative/PRIMARY partition) vs the status-only coordination worktree husk (`status.events.jsonl`/`status.json`).
**Testing**: pytest, ATDD red-first per ADR 2026-07-17-1 — issue-pinned `@pytest.mark.regression` repros RED through the pre-existing entry point before the fix, then demoted to focused tests.
**Target Platform**: `spec-kitty` CLI (Linux/macOS/Windows), incl. fresh-clone / CI-runner checkouts where the coord worktree is unmaterialised.
**Project Type**: single project (`src/` + `tests/`).
**Performance Goals**: none affected (read-path resolution, not a hot loop).
**Constraints**: seam-level contract (C-001); do NOT touch `surface_resolver._coord_branch_exists` / `doctor coordination --fix` (C-002, #4979/#4950); fail-closed toward retention (C-003); preserve `NONE` raising + leave non-coord topologies unaffected (C-005).
**Scale/Scope**: 1 seam contract change + 2 surface adaptations + a full seam-caller audit; ~4-6 source files + tests + an ADR (behavioral change to a shared seam warrants a decision record).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority (DIRECTIVE_001)** — the fix centralises the fail-closed rule at the one read seam rather than scattering per-reader checks; removes the "reader silently trusts empty-PRIMARY" class. ✅
- **Decision documentation (DIRECTIVE_003)** — a shared-seam behavioral change (a read that used to return empty now raises) is recorded in an ADR; the locus decision is already in `DM-01M38VWD`. ✅
- **DDD + tiered rigour** — this is data-safety / destructive-write territory → highest rigour: red-first repros for both defects, blast-radius audit, fail-closed toward retention. ✅
- **Locality vs blast radius (DIRECTIVE_024 / RECONCILE_CHANGE_SCOPE_TENSIONS)** — the operator chose the broader seam-level locus over the narrower per-reader fix precisely to close the class; the audit bounds the blast radius explicitly. ✅
- **Campsite (DIRECTIVE_025)** — corrects the wrong `decisions/service.py` docstring while in the file. ✅
- **Scope guard** — C-002 fences off #4979's seam; terminology canon (C-006). ✅

No unjustified violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/coord-read-fail-closed-01M38VVH/
├── plan.md              # This file
├── research.md          # Phase 0 — the seam-caller blast-radius audit + fix-shape decisions
├── data-model.md        # Phase 1 — coord-surface state model + fail-closed contract
├── quickstart.md        # Phase 1 — how to verify each defect (red-first)
├── contracts/           # Phase 1 — read-seam fail-closed contract; tracer + decision-ledger contracts
├── tracer-approach.md / tracer-design-decisions.md / tracer-tooling-friction.md   # seeded now, appended during implement
└── tasks.md             # Phase 2 (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/mission_runtime/
└── resolution.py                 # SEAM: coord-state→surface (~1961-1968) + placement_seam (~2201) — raise on unresolved/unmaterialised coord read (extend NONE posture)

src/specify_cli/
├── retrospective/tracer_writer.py         # #4959: _read_current_coord_content (~144), base_content (~251) — fail closed + refuse undecodable byte
├── decisions/service.py                   # #4966: _resolve_mission_id (~151), _mission_dir (~204) — resolve to authoritative partition; fix docstring (~157)
├── acceptance/__init__.py                 # reference: _has_blocking_clarification_marker (~666) reads PRIMARY ledger — the partition service.py must agree with
└── <seam callers surfaced by the Phase-0 audit>   # adapt each to handle the raise; non-coord callers unaffected

docs/adr/3.x/
└── 2026-09-24-N-coord-read-fail-closed.md          # ADR: read seam raises on unresolved/unmaterialised coord read

tests/  # red-first repros + regression: resolution seam, tracer-append, decisions service, accept, coord integration
```

**Structure Decision**: single-project; one seam contract + two surface adaptations + audited caller adaptations + one ADR. No new packages.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*

## Parallel Work Analysis

### Dependency Graph

```
Phase 0 audit (enumerate + classify EVERY read-seam caller)
        │
   [Foundational] Seam contract: resolution.py raises typed error on unresolved/unmaterialised coord read (+ ADR)
        │   (every surface/caller depends on the raise existing)
        ├── Surface: tracer-append fail-closed (#4959)
        ├── Surface: decision-ledger resolve-to-authoritative (#4966)
        └── Caller adaptations from the audit (bucket-a coord readers; bucket-c empty-PRIMARY relyers)
        │
   Docs/CHANGELOG close-out (#4959/#4966)
```

### Work Distribution

- **Sequential (foundational)**: the seam-raise contract lands FIRST — the surfaces and caller adaptations all depend on the typed error existing and on the audit's classification.
- **Then parallel-ish**: tracer-append (#4959) and decision-ledger (#4966) surfaces are disjoint files; caller adaptations partition by owning module.
- **Risk-gated**: bucket-c callers (any that legitimately rely on empty-PRIMARY) must be adapted in the same change that makes the seam raise, or they break — the audit identifies them before implementation.

### Coordination Points

- The seam-raise WP is the integration point; surfaces + caller-adaptations rebase on it.
- Full coord/non-coord regression suite green (NFR-002) proves the raise didn't break topology-agnostic or non-coord callers.
