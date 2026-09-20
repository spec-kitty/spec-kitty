# Implementation Plan: Doctor mission-state legacy repair & report fidelity

**Branch**: `fix/doctor-mission-state-repair-fidelity` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/doctor-mission-state-repair-fidelity-01M2YGV8/spec.md`
**Investigation**: [research/durable-fix-investigation.md](./research/durable-fix-investigation.md) (DIRECTIVE_052)

## Summary

Make `spec-kitty doctor mission-state` **repair** legacy missions instead of aborting, and **honestly report** per-mission outcomes. Three cohesive changes on one seam (the mission-state audit/repair + reporting surface):

1. **Repair normalization + validator reconciliation** — the repair canonicalizer normalizes any non-`bulk_edit` `change_mode` to *absent* (recording a `normalized_change_mode` action) *before* `validate_meta`, so legacy missions repair instead of raising. `--audit` (writer-schema, key-level) and `--fix` (value-level) are reconciled so they classify a legacy `change_mode` consistently (repairable, not fatal). Vocabulary stays `{bulk_edit}`; the write-path guard is untouched.
2. **Reporting fidelity + dry-run parity** — `--fix` and `--teamspace-dry-run` surface per-mission slug + reason in both terminal and `--json`; the dry-run reaches structured shape parity with the repair report.
3. **Evidence surface** — terminal/`--json` become the authoritative record so the git-ignored manifest is no longer the sole per-error evidence.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing CLI stack — **no new dependencies**; supply-chain section N/A)
**Storage**: mission `meta.json` files + `status.events.jsonl` (repaired in place); manifest/quarantine under `.kittify/migrations/` (git-ignored, unchanged as a sidecar)
**Testing**: pytest (ATDD red-first). Blast radius: `tests/specify_cli/`, `tests/unit/migration/`, `tests/integration/migration/`, `tests/cli/commands/`, `tests/audit/`, `tests/status/`
**Target Platform**: Linux/macOS/Windows CLI (developer tooling)
**Project Type**: single (CLI package under `src/specify_cli/`)
**Performance Goals**: no material regression — repair/dry-run wall-clock stays within 10% of baseline over a fixed mission set (new reporting reuses already-collected report data; no second tree scan) — NFR-004
**Constraints**: behavior-preserving normalization at every read boundary (NFR-001); idempotent repair (NFR-002); single-invocation observability with no git-ignored read (NFR-003); vocabulary stays `{bulk_edit}` (C-001); writer-schema-sourced validation, no divergent hand-rolled lists (C-003); Python + tests only, no `packs/` template-source edits (C-005)
**Scale/Scope**: ~4 source files + focused tests; reporting repo has 124 missions, 21 legacy

## Constitution Check

*GATE: charter gates for this change.*

- **DIRECTIVE_052 (Prefer Durable Fixes)**: PASS — root cause diagnosed to a systemic seam (two validation authorities); reconciliation folded; scanner unification deferred behind #2720. Record: `research/durable-fix-investigation.md`.
- **DIRECTIVE_044 (single canonical authority)**: PASS — the fix chases unification of the audit/fix validation verdict, not parity patched twice.
- **DIRECTIVE_024/025 + RECONCILE_CHANGE_SCOPE_TENSIONS**: PASS — scope reconciled with operator (Full seam; scanner unification deferred). Blast radius stays on the one seam.
- **DIRECTIVE_034 (test-first) / C-011 ATDD-first**: PASS by construction — every FR lands red-first (see WP sequencing).
- **DIRECTIVE_010 (spec fidelity)**: PASS — plan traces to FR/NFR/C in spec.
- **`__all__` convention (C-007)**: new helpers in `_mission_state_doctor.py` stay intra-module, NOT added to `__all__` (dead-symbol gate). `migration/mission_state.py` new helpers exported only if consumed cross-module.
- **Terminology Canon**: PASS — no `feature*` alias; must NOT introduce `regular` as a canonical term.
- **ADRs**: aligned with `2026-05-10-1` (deterministic repair) and `2026-04-14-1` (bulk-edit guardrail); reporting routes through the `2026-07-14-1` canonical console seam. No amendment required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctor-mission-state-repair-fidelity-01M2YGV8/
├── plan.md              # This file
├── spec.md
├── research/
│   ├── durable-fix-investigation.md   # DIRECTIVE_052 record
│   └── research.md                    # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI output contract)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── mission_metadata.py                 # VALID_CHANGE_MODES, validate_meta, set_change_mode (write-guard) — unchanged vocabulary
├── migration/
│   └── mission_state.py                # _canonicalize_mission_meta (normalize hook), MissionRepairResult (+meta_actions), repair_repo, teamspace_dry_run
├── cli/commands/
│   ├── _mission_state_doctor.py        # _pretty_repair / _pretty_dry_run renderers (per-mission detail)
│   └── implement.py                    # :1340 reader alignment (is not None → == "bulk_edit")  [A2]
└── bulk_edit/
    └── gate.py                         # :91-95 stop propagating raw legacy change_mode; GateResult.change_mode ∈ {"bulk_edit", None}  [A2]
# audit/shape_registry.py — DELIBERATELY UNTOUCHED (FR-010 needs no registry edit)

tests/
├── specify_cli/test_mission_metadata_change_mode.py
├── unit/migration/                     # canonicalization normalization
├── integration/migration/             # repair pipeline
├── cli/commands/test_doctor_mission_state.py   # renderer + dry-run output
└── audit/                              # shape-registry parity
```

**Structure Decision**: single-project CLI; changes confined to `src/specify_cli/` + mirrored tests. No new modules; no packaging/pyproject changes (so `tests/architectural/` is not in the blast radius unless a new symbol trips a gate).

## Implementation Concern Map (→ work packages)

| Concern | Files | Requirements | Notes |
|---------|-------|--------------|-------|
| **A. Repair normalization + report field + non-fatal reconciliation** | `mission_metadata.py`, `migration/mission_state.py` (canonicalizer + new `meta_actions` on `MissionRepairResult` + `to_dict`) | FR-001..004, FR-010, FR-011, FR-013, NFR-002, C-001..003 | Normalize non-`bulk_edit`→absent before `validate_meta`; record `normalized_change_mode` **conditionally** (only when field present, mirroring `removed_meta_key:*`) in the NEW `meta_actions` report field (today canonicalizer actions are a discarded write-gate boolean). FR-010 reconciliation = `--fix` no longer fatal ⇒ audit+fix agree; **do NOT edit `audit/shape_registry.py`** (change_mode is a known key; editing adds a finding-code + #2720 drift). Red-first. |
| **A2. Reader alignment (durable fix, folded)** | `cli/commands/implement.py:1340` (`is not None`→`== "bulk_edit"`), `bulk_edit/gate.py:91-95` (stop propagating raw legacy value) | FR-012, NFR-001 | Post-plan squad [BLOCKER]: `implement.py:1340` distinguishes legacy-value from absent, so normalization flips bulk-edit inference skip→run. Align the implicit reader to the single canonical `== "bulk_edit"` check + pin `GateResult.change_mode ∈ {"bulk_edit", None}`. Red-first test enumerating EVERY reader (legacy≡absent). |
| **B. Reporting fidelity + dry-run parity + evidence** | `cli/commands/_mission_state_doctor.py` (`_pretty_repair`/`_pretty_dry_run`), `migration/mission_state.py` (dry-run report render only) | FR-005..009, NFR-003, NFR-004, C-006 | Render per-mission slug+reason (incl. `meta_actions`) in terminal+json; dry-run parity. **Additive only** — must NOT touch `valid`/`fatal_errors`/`Exit(1)` refusal semantics. Red-first. |
| **C. Integration verification + docs/changelog** | tests (full blast radius), `CHANGELOG.md` | SC-001..006, NFR-001/003 | Behavior-preservation cross-check; full `tests/architectural/` only if a gate is tripped; CHANGELOG entry. |

## Parallel Work Analysis

### Dependency Graph

```
Concern A (repair+reconcile)  ─┐
                               ├─► Concern C (integration verify + CHANGELOG)
Concern B (reporting+dry-run) ─┘
```

- **A and B** both touch `migration/mission_state.py` (A: canonicalizer; B: dry-run report shape) → by write-scope-overlap they will **collapse into one lane** at finalize (they are not file-disjoint). Expect a single lane with sequential WPs, not parallel lanes. This is intended — a shared-file mission.
- **C** depends on A and B being present (integration surface).

### Work Distribution

- **Sequential**: A → B → C (single lane most likely). A establishes the normalization + report data; B renders it; C verifies the whole.
- **Agent assignment**: python-pedro for A and B (Python-specialist, ATDD); reviewer-renata for review; integration handled in C.

### Coordination Points

- After A: unit + integration migration tests green; behavior-preservation test for every read boundary of `change_mode`.
- After B: CLI renderer + dry-run output tests green (terminal + `--json`).
- After C: blast-radius suite green; `tests/architectural/` run only if a new symbol/count gate fires; CHANGELOG updated.

## Complexity Tracking

*No charter violations requiring justification.* The one genuine tension (DIRECTIVE_052 licensing a larger structural change vs DIRECTIVE_024/025 locality) was reconciled with the operator: the structural reconciliation (audit/fix agreement) is folded; the larger structural item (scanner unification) is deferred behind #2720. No unbounded scope.
