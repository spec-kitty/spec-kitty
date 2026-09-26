# Implementation Plan: CI Coverage Honesty

**Branch**: `feat/ci-coverage-honesty` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/ci-coverage-honesty-01M3CZVN/spec.md`

## Summary

Make a green `main`/nightly a truthful test signal. The per-module CI selector keys shards on source roots with no test→imported-source model, so cross-cutting and unenrolled suites are silently skipped. This plan adds two enforced architectural invariants (foreign-coverage + src-reachability), enrolls the dark suites (`live_work`, dark packages), wires the integration corpus into the nightly, makes hidden nightly reds self-surface as a deduped P0, and gates releases on a green nightly for the exact release SHA. The work is registry-row-driven and gated by the existing selection-authority tests.

## Technical Context

**Language/Version**: Python 3.11+ (guards, escalation/release helper scripts) + GitHub Actions YAML (workflow wiring)
**Primary Dependencies**: pytest + pytestarch (architectural guards), PyYAML (registry parse, already used by `gate_selection.py`), `scripts/ci/capture_shard_timings.py` (LPT sharding), `gh`/GitHub REST via Actions token (auto-P0 escalation + release nightly dispatch)
**Storage**: N/A (registry YAML + workflow YAML + JSON timing sidecars are the only persisted artifacts)
**Testing**: pytest — new guards live in `tests/architectural/`; escalation/release helpers unit-tested under `tests/ci/`; `tests/architectural/test_gate_selection_authority.py` + `test_pyproject_shape.py` are the authority gates that must stay green
**Target Platform**: GitHub Actions runners (Linux) + local `make test-*`
**Project Type**: single (CLI/infra repo)
**Performance Goals**: new guards ≤ 5 s each (join the always-on architectural battery); nightly integration lane worst shard under the `module-tests.yml` per-shard timeout
**Constraints**: registry-row-driven (no new per-module workflow file; reusable-workflow ceiling 20); shard_count measured, never guessed; no per-PR wall-clock regression beyond enrolled dirs; fork-safe/fail-closed escalation (no token leak)
**Scale/Scope**: 1 registry (`ci-module-registry.yml`, ~21 module rows + out_of_matrix), 1 selection authority (`gate_selection.py`), 5 workflow files, ~2 new guard tests, ~2 new CI helper scripts, 1 new module row, 1 nightly lane, 1 release gate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority**: the fix is expressed in the registry + `gate_selection.py` (the enforced pair), never a prose map. ✅ aligned.
- **Architectural gate discipline**: new invariants are enforced tests in `tests/architectural/`, not review-only prose. ✅
- **Campsite cleaning / boy-scout (DIRECTIVE_025)**: enrolling dark packages and fixing the phantom-mirror bug are in-scope cleanups the mission owns. ✅
- **Canonical sources**: sharding via `capture_shard_timings.py` + LPT (never guessed); no hand-rolled workflow duplication. ✅
- **Terminology**: no `feature*` aliases introduced; "Mission" preserved. ✅
- **CI honesty ADR** (`2026-07-17-1`): this mission strengthens the honest-signal posture; it must not green-wash `regression`-marked red-first tests. ✅ (C-004 keeps product-bug fixes out of scope.)

No violations to justify.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-coverage-honesty-01M3CZVN/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (guard + escalation + release-gate contracts)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
.github/
├── ci-module-registry.yml          # + live_work row; agent_utils/dark-pkg test_dirs; source of truth (FR-004/005/009)
└── workflows/
    ├── ci-nightly.yml              # + integration lane; + red→P0 escalation step (FR-006/007)
    ├── module-tests.yml           # (consumed; may need timeout note for integration shard)
    ├── ci-router.yml / ci-modules.yml  # (consumed by gate_selection; unchanged unless a group is needed)
    └── release.yml                 # + nightly precondition gate (FR-008)

scripts/ci/
├── gate_selection.py               # authority (read; may gain a reachability export helper)
├── capture_shard_timings.py        # measure live_work + integration shard_count (NFR-001)
├── nightly_escalation.py           # NEW: red→deduped-P0 helper (FR-007), unit-tested
└── release_nightly_gate.py         # NEW: dispatch+await nightly for release SHA (FR-008), unit-tested

tests/
├── architectural/
│   ├── test_gate_selection_authority.py   # fix phantom-mirror bug (FR-003)
│   ├── test_foreign_coverage_guard.py     # NEW invariant (FR-001)
│   └── test_src_reachability_guard.py     # NEW invariant (FR-002)
├── ci/
│   ├── test_nightly_escalation.py         # NEW (FR-007)
│   └── test_release_nightly_gate.py       # NEW (FR-008)
└── specify_cli/live_work/ , tests/agent_utils/ (new), tests/schemas/ (new), ...  # enrolled dirs
```

**Structure Decision**: Single-project infra layout. The registry (`.github/ci-module-registry.yml`) + `scripts/ci/gate_selection.py` are the enforced authority pair (CLAUDE.md Modularity SSOT); every coverage fix is a registry row or a guard, never a new workflow file (C-001). New guards go in `tests/architectural/`; new CI helper scripts in `scripts/ci/` with unit tests in `tests/ci/` (mirroring `sonar_project_version.py` / `test_sonar_project_version.py`).

## Parallel Work Analysis

### Dependency Graph

```
Foundation (WP-A: authority + guards scaffolding)
   ├─ fix phantom-mirror bug (FR-003)               ─┐
   └─ author foreign-coverage + src-reachability     │ guards land RED first (they fail on
      guards as RED-first tests (FR-001/002)          │ the current dark set) → then remediation greens them
                                                       ▼
Remediation wave (parallel, each greens a guard slice)
   ├─ WP-B: agent_utils real test dir + foreign-row remediation (FR-004)  → greens foreign-coverage guard
   ├─ WP-C: mint live_work row + measured shard_count (FR-005)            → greens src-reachability for live_work
   └─ WP-D: enrol dark pkgs schemas/config/... (FR-009)                   → greens src-reachability for the rest
                                                       ▼
Nightly + escalation wave (parallel)
   ├─ WP-E: wire integration into nightly, measured shards (FR-006)
   └─ WP-F: nightly red→deduped-P0 escalation helper + step (FR-007)
                                                       ▼
Release gate (WP-G: release.yml depends on green nightly for SHA (FR-008)) — depends on WP-E/WP-F existing
```

### Work Distribution

- **Sequential first**: WP-A (guards + phantom-mirror fix) must land the RED-first invariants before remediation, so each remediation WP has an objective green target.
- **Parallel streams**: WP-B/C/D (remediation) are file-disjoint (agent test dir vs live_work row vs dark-pkg dirs) and can run concurrently. WP-E/F (nightly) are disjoint from remediation.
- **Agent assignments**: python-pedro for guards/helpers/tests (WP-A/F/G Python); implementer-ivan or python-pedro for registry rows + test-dir enrolment (WP-B/C/D); WP-E/F/G touch workflow YAML + Python.

### Coordination Points

- **Sync**: the registry file (`ci-module-registry.yml`) is touched by WP-B/C/D/E — serialize registry edits or assign one owner for registry rows to avoid churn; `ci-nightly.yml` owned by WP-E then WP-F in sequence.
- **Integration test**: after remediation, `pytest tests/architectural/test_foreign_coverage_guard.py test_src_reachability_guard.py test_gate_selection_authority.py test_pyproject_shape.py` must be green together (C-002).

## Complexity Tracking

No Constitution violations. The one notable design tension — whether the foreign-coverage guard needs an allow-list — is resolved in research.md (yes: a recorded, dated allow-list for justified aggregate modules like `execution_context`/`core_misc`, not a silent pass).
