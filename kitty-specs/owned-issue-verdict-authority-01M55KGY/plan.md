# Implementation Plan: Owned issue-verdict authority

**Branch**: `owned-issue-verdict-authority-01M55KGY` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/owned-issue-verdict-authority-01M55KGY/spec.md`

## Summary

Thread the validated `OwnedCheckout` fact through the `agent mission issue-verdict` command and
the fail-closed write-target gate (`coordination.surface_resolver.resolve_for_write` →
`mission_runtime.write_target_degrade`) so an owned-only mission can record issue-matrix
verdicts via `--owned-checkout` (and via flagless adoption from inside the owned checkout).
Also thread the owned fact through the coord-owned read + legacy-migration path
(`coord_read_dir_for` / `_resolve_read_dir` / `_migrate_if_needed`) per the resolved scope
decision. This is the twin of the merged #6023 acceptance-verdict fix; it reuses that fix's
carrier pattern and owned test fixtures. The only net-new surface over #6023 is the shared
`write_target_degrade` gate, which `issue-verdict` reaches (via `resolve_for_write`) and
`acceptance-verdict` does not.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), existing `specify_cli` / `mission_runtime` / `coordination` layers; no new deps
**Storage**: `issue-matrix.json` per mission (unchanged format); event log / status files via existing writers
**Testing**: pytest; red-first integration tests reusing #6023 owned R/P/S fixtures (`tests/integration/test_owned_acceptance_authority_6023.py`, `test_p0_repro_6023_owned_acceptance_verdict.py`); `p0_repro`-marked reproduction; mission_runtime unit tests for the gate functions
**Target Platform**: Linux/macOS dev + CI
**Project Type**: single project (CLI/control-plane)
**Performance Goals**: N/A (no hot path changed)
**Constraints**: additive `owned=None` keyword args only; import direction `specify_cli → coordination → mission_runtime` preserved; issue-matrix format and locked-writer semantics unchanged; three unrelated `write_target_degrade` callers stay byte-identical
**Scale/Scope**: ~3–4 source files (`issue_verdict.py`, `coordination/surface_resolver.py`, `mission_runtime/write_target_degrade.py`, optionally `mission_runtime/resolution.py::coord_read_dir_for`) + tests + changelog/CLI-reference

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Brownfield onboarding / architectural alignment**: PASS — change rides existing seams; mirrors the proven #6023 pattern; no new authority or placement seam (C-001).
- **ATDD-first / red-first (DIRECTIVE test discipline)**: PASS — a failing owned repro lands before the fix (C-003); `p0_repro` reproduction included.
- **Tiered rigour / fail-closed**: PASS — fail-closed refusal preserved for an owned fact that does not resolve a real mission (NFR-001); no silent fallback to the repository root.
- **Shared-helper backward-compat**: PASS — the three unrelated callers of `write_target_degrade.assert_coord_write_materialized` keep `owned=None` defaults and stay byte-identical (FR-005).
- **Test economy (DIRECTIVE_041)**: PASS — new tests guard real owned behavior through the existing entry points; ratchet rows carry same-fixture positive controls; no shape-pins or inert self-compares.
- **Layer rules**: PASS — no new reverse import edge; `mission_runtime` gains only additive params.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-issue-verdict-authority-01M55KGY/
├── plan.md              # This file
├── spec.md
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

(No `contracts/` — this mission defines no new interfaces; `meta.json` records `contracts: none` with rationale.)

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/issue_verdict.py      # command surface: option + do_issue_verdict + _resolve_write_dir/_resolve_read_dir/_migrate_if_needed + locked writer passthrough + flagless adoption
src/specify_cli/coordination/surface_resolver.py         # resolve_for_write: add owned passthrough
src/mission_runtime/write_target_degrade.py              # resolve_write_target_or_degrade / _mission_meta_exists / assert_coord_write_materialized: owned-aware (additive None default)
src/mission_runtime/resolution.py                        # coord_read_dir_for: owned param for coord-owned read (scope decision)

tests/integration/                                       # red-first owned issue-verdict authority test + p0-repro (reuse #6023 fixtures)
tests/<mission_runtime path>/                            # unit tests for the three gate functions' owned param + byte-identity of the 3 unrelated callers
docs/changelog/CHANGELOG.md                              # Fixed entry
docs/reference/cli (regenerated)                         # issue-verdict --owned-checkout option
```

**Structure Decision**: Single project. Changes ride three existing layers in strict
`specify_cli → coordination → mission_runtime` direction; no new modules.

## Complexity Tracking

*No Charter Check violations — not applicable.*

## Implementation Concern Map

> Concerns, not work packages. `/spec-kitty.tasks` turns these into executable WPs.
> A `single_branch` mission runs WPs sequentially; the dependency order below is load-bearing.

### IC-01 — mission_runtime write-target gate owned-awareness

- **Purpose**: Make the fail-closed gate recognize an owned-only mission when handed the owned fact, so it stops refusing a genuinely-present owned mission — while leaving its three unrelated callers byte-identical.
- **Relevant requirements**: FR-002, FR-005, NFR-001, NFR-002
- **Affected surfaces**: `src/mission_runtime/write_target_degrade.py` (`resolve_write_target_or_degrade`, `_mission_meta_exists`, `assert_coord_write_materialized`); downstream `resolve_placement_only` already owned-capable
- **Sequencing/depends-on**: none (foundation)
- **Risks**: shared helper with 3 other callers (decision-log default target, bookkeeping-commit target, status-transition write target) — the new `owned` param MUST default `None` and be proven byte-identical for them; the `establish_coord_write_location(..., owned=None)` hard-code must become a passthrough

### IC-02 — resolve_for_write owned passthrough

- **Purpose**: Carry the owned fact from the command across the coordination seam into the gate.
- **Relevant requirements**: FR-002
- **Affected surfaces**: `src/specify_cli/coordination/surface_resolver.py::resolve_for_write`
- **Sequencing/depends-on**: IC-01
- **Risks**: thin; keep the public signature additive (`owned=None`)

### IC-03 — issue-verdict command owned wiring + flagless adoption

- **Purpose**: Add `--owned-checkout` to the command, resolve ownership once (mirror #6023), and thread the fact through resolution, the write dir, the read/migration dir, and the locked re-read/splice/write.
- **Relevant requirements**: FR-001, FR-004, FR-006
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/issue_verdict.py` (`issue_verdict_command`, `do_issue_verdict`, `_resolve_write_dir`, `_resolve_read_dir`, `_migrate_if_needed`, `_locked_reread_splice_and_write`); reuse `_owned_checkout.OwnedCheckoutOption` / `resolve_owned_or_refuse`, `LIFECYCLE_OWNED_TOPOLOGIES`
- **Sequencing/depends-on**: IC-02
- **Risks**: `write_issue_matrix` already accepts `owned` — must actually pass it; preserve fail-closed when the owned fact resolves no mission (NFR-001)

### IC-04 — coord-owned read path threading

- **Purpose**: Thread the owned fact through the coord-owned read + legacy-matrix migration so an owned coord mission reads/migrates from the owned surface, not the repository root (resolved scope decision).
- **Relevant requirements**: FR-003
- **Affected surfaces**: `src/mission_runtime/resolution.py::coord_read_dir_for`; `issue_verdict._resolve_read_dir` / `_migrate_if_needed`; `tasks/issue_matrix_migration.py` call
- **Sequencing/depends-on**: IC-03
- **Risks**: `coord_read_dir_for` returns `None` for owned `single_branch` (primary case), so the write-dir path (IC-03) already covers #6320's headline; this concern covers the coord-topology case and must not regress the `single_branch` fallback to `feature_dir`

### IC-05 — red-first proof, p0-repro, and deliverable hygiene

- **Purpose**: Land the failing owned repro before the fix, pin it as a p0-repro, add mission_runtime unit tests (including the byte-identity of the 3 unrelated callers), and update changelog + regenerated CLI reference.
- **Relevant requirements**: C-003, SC-001, SC-002
- **Affected surfaces**: `tests/integration/`, mission_runtime unit tests, `docs/changelog/CHANGELOG.md`, regenerated CLI reference
- **Sequencing/depends-on**: woven through IC-01..IC-04 (red-first per concern), hygiene at the end
- **Risks**: test economy — one focused positive test per behavior; reuse #6023 fixtures; ratchet tests pair with same-fixture positive controls
