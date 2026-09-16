# Implementation Plan: CI Pipeline Honesty — Actionable Fixes

**Branch**: `fix/ci-honesty-actionable-fixes` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/ci-honesty-actionable-fixes-01M2JAXX/spec.md`

## Summary

Close four independent, settled CI-honesty holes (epic #4437) so CI verdicts are honest for the agent fleet: (1) #4360-B the aggregate stops false-failing diff-scoped PRs whose selected shards all pass; (2) #4454 a tests-only change runs its own tests; (3) #4208 a timeout-kill is distinguishable from an external cancel at the gate; (4) #4212 the nightly fails loud on a red suite. Design is settled by the 4-lens research in `work/ci-honesty-4437/` (`SYNTHESIS.md`, `lenses/A..D.md`); this plan consolidates it. Binding invariant: **no fix widens the green path** (NFR-001).

## Technical Context

**Language/Version**: Python 3.11+ (helper modules under `scripts/ci/`); GitHub Actions workflow YAML.
**Primary Dependencies**: Existing repo tooling only — `pytest`, `ruamel.yaml`/`PyYAML` (already used by the workflow-lint tests). **No new runtime or dev dependency is added** (supply-chain check: N/A — see research.md).
**Storage**: N/A — operates on CI coverage/xunit artifacts on disk and workflow config; no persistent store.
**Testing**: `pytest` — `tests/ci/` (reconciler unit) and `tests/architectural/` (workflow-lint + gate-selection authority + router-gate contract).
**Target Platform**: GitHub Actions (ubuntu runners) + local dev (`.venv`).
**Project Type**: single (CLI/tooling monorepo).
**Performance Goals**: extracted helpers run < 1s; no added CI wall-clock beyond existing shard runs.
**Constraints**: no fix widens the green path (NFR-001); preserve the aggregate fail-closed guard (`ci-aggregate.yml:376-381`), the `must_be_fresh` seam (`:347`), the router two-authority contract (`contracts/router-two-authority.md`), and nightly run-all (`if:always()`/`fail-fast:false`); `mypy --strict` + `ruff` clean, no new suppressions.
**Scale/Scope**: 3 workflow files + 2 new `scripts/ci/` helper modules + ~4 test files; blast radius bounded to the CI subsystem. Red-first base commit: `36d866d4fa`.

## Constitution Check (Charter)

*GATE: must pass before Phase 0 and re-checked after design.*

- **ATDD-first (C-011)**: PASS — every WP lands a RED-first test (red on `36d866d4fa`, green on the fix) before implementation. Reviewer verifies red→green.
- **Architectural gate discipline (DIRECTIVE_043)**: PASS — #4360-B and #4208 extract inline logic into importable, unit-tested `scripts/ci/` helpers (non-vacuous tests over real inputs), rather than leaving untested inline YAML.
- **Red-main & release discipline (Standing Order #9, ADR 2026-07-17-1)**: PASS — this mission *serves* the invariant; NFR-001 forbids widening the green path and is pinned by regression tests (SELECTED-absent stays fatal; #4208 blocking policy byte-identical).
- **Canonical sources (DIRECTIVE_044)**: PASS — #4454 uses the two-authority router (Option 1, no second map); no improvised substitute.
- **Locality of change (DIRECTIVE_024)**: PASS — each fix is scoped to its own surface; cleanup limited to the touched files.
- **Supply-chain safety (051)**: N/A — no dependency added/upgraded/removed.
- **Terminology canon**: N/A — CI-internal identifiers, no Mission/Feature surface.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-honesty-actionable-fixes-01M2JAXX/
├── plan.md              # This file
├── research.md          # Phase 0 — settled decisions (consolidated from work/ci-honesty-4437/)
├── data-model.md        # Phase 1 — the shard-completeness model + classifier model
├── quickstart.md        # Phase 1 — how to run each RED-first test locally
└── contracts/           # Phase 1 — reconcile_shards + router_gate helper contracts
```

### Source Code (repository root)

```
scripts/ci/
├── reconcile_shards.py      # NEW (#4360-B) — extracted completeness reconciler
└── router_gate.py           # NEW (#4208) — timed_out-aware blocking classifier

.github/workflows/
├── ci-aggregate.yml         # #4360-B — call extracted reconciler; selected-shard completeness
├── ci-router.yml            # #4454 (filter-group globs) + #4208 (router-gate step)  ← SHARED FILE
└── ci-nightly.yml           # #4212 — capture exit codes + terminal fail-loud

tests/
├── ci/
│   └── test_reconcile_shards.py            # NEW (#4360-B) RED-first
└── architectural/
    ├── test_gate_selection_authority.py    # #4454 RED-first (extend existing)
    ├── test_dual_mode_contract.py          # #4208 RED-first (extend existing)
    └── test_performance_marker_guard.py    # #4212 RED-first (extend existing)
```

**Structure Decision**: Single tooling repo. Inline YAML logic that needs a real RED-first pin is extracted to `scripts/ci/` (matching the existing `gate_selection.py` / `fleet_verdict.py` two-authority pattern); pure-config changes (#4454 globs, #4212 shell) stay in YAML and are pinned by the existing workflow-lint tests.

## Parallel Work Analysis

### Dependency graph

All four fixes are **behaviourally independent** — none depends on another's output. The only coupling is a **shared write-surface**:

```
WP01 (#4360-B)  ── ci-aggregate.yml + scripts/ci/reconcile_shards.py + tests/ci/         [own lane]
WP04 (#4212)    ── ci-nightly.yml + tests/architectural/test_performance_marker_guard.py [own lane]
WP02 (#4454) ─┐
WP03 (#4208) ─┴ BOTH edit .github/workflows/ci-router.yml (different regions)            [SAME lane]
```

### Work distribution

- **WP01 #4360-B** — reconciler extraction + selected-shard completeness. Disjoint surface (`ci-aggregate.yml`, new `reconcile_shards.py`, `tests/ci/`). Independent lane.
- **WP02 #4454** — router filter-group globs (`ci-router.yml` dorny filters) + `test_gate_selection_authority.py`.
- **WP03 #4208** — router-gate classifier (`ci-router.yml` router-gate step ~568-572) + new `scripts/ci/router_gate.py` + `test_dual_mode_contract.py`.
- **WP04 #4212** — nightly fail-loud (`ci-nightly.yml`) + `test_performance_marker_guard.py`. Independent lane.

### Coordination points (the load-bearing note)

- **WP02 and WP03 both edit `ci-router.yml`** (filter globs vs. the router-gate step — different regions, no logic overlap). `finalize-tasks` unions WPs by `owned_files` overlap, so **WP02 + WP03 will collapse into one lane/worktree** — which is desirable: it serialises the two `ci-router.yml` edits in a single working tree and eliminates the merge collision (C-004). Declare `ci-router.yml` as an owned file for BOTH so the union is intentional, not accidental.
- **Self-referential CI verification (C-004)**: a workflow-topology change can only be fully proven on the merged `main` tip. Each WP's review verifies the RED-first test red→green on `36d866d4fa`→fix; the *workflow-level* behaviour (matrix selection, aggregate verdict, nightly failing) is additionally asserted by the workflow-lint / gate-selection tests so it does not depend on a live CI run to prove.
- **No cross-lane integration test needed** — the four fixes touch disjoint runtime behaviours; the per-WP RED-first tests + the existing arch battery are the integration guard.
