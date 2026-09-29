# Implementation Plan: Nightly census re-pin and timeout headroom

**Branch**: `issue-5367-nightly-census-and-timeout-headroom` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/nightly-census-and-timeout-headroom-01M3PM2S/spec.md`

Planned under the loaded `planner-priti` profile. Root-cause evidence is in the phase-1 comments on
#5367 (issuecomment-5890787701) and #5378 (issuecomment-5890811644).

## Summary

Two independent defects keep `ci-nightly.yml` red on `main`:

1. **#5367 (doctrine drift, not a stale test).** PR #5324 (`3e09226f`) shipped three new supply-chain
   toolguides with bare-id `references: [DIRECTIVE_051, supply-chain-install-safety]`. The extractor
   resolves only file paths (`extractor.py:183-226`) and silently skips bare ids, so the entries mint no
   edge; ADR `2026-07-26-1` forbids inline references on new artefacts; the relationship already exists as
   authored edges (`tactic.graph.yaml:1207-1218`, `directive.graph.yaml:423`). Remove them. The seventh new
   entry (`common-docs` → `docs_structural_lint.config.yaml`) is legitimate raw material (a non-artefact
   data file whose artefact-level relation is the `styleguide:common-docs --requires--> asset:…` edge), so
   re-pin the census 19 → 20 with provenance.
2. **#5378 (budget tuning).** Shard caps were `~1.9 × one sample`; the same populations measure ~2× apart
   across nights (runner variance), test counts grew only +1–2%. Re-derive caps from the max over five runs.

## Technical Context

**Language/Version**: Python 3.11 (tests), GitHub Actions YAML
**Primary Dependencies**: pytest, ruamel/PyYAML, `spec-kitty doctrine regenerate-graph`
**Storage**: N/A (doctrine YAML + workflow YAML)
**Testing**: red-first targeted tests; `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py`, new `tests/ci/test_nightly_timeout_headroom.py`, gate files `tests/architectural/test_interpreter_shard_coverage.py`, `tests/architectural/test_module_shard_registry.py`, `tests/ci/test_nightly_exit_code_honesty.py`, `tests/ci/test_interpreter_matrix_env_pinning.py`, `tests/doctrine/test_supply_chain_single_owner.py`
**Target Platform**: GitHub-hosted `ubuntu-24.04` runners
**Project Type**: single
**Performance Goals**: every capped leg ≥ 1.5× measured max (suite + 0:30 overhead)
**Constraints**: no retry-to-green, no re-shard, no full heavy suites, don't touch in-flight slices
**Scale/Scope**: 3 toolguide YAMLs + pack manifest, 1 test file re-pin, 1 workflow, 1 new CI test, roster docstring, changelog

## Charter Check

- Single canonical authority / DRG edges canonical (ADR 2026-07-26-1): FR-001 removes a parallel inline form. PASS.
- DIRECTIVE_041 judge the test: census is valid; 6 entries are product drift (fix product), 1 is legitimate (re-pin with provenance). PASS.
- Red-first: census test RED on `main`; new headroom test RED against current caps before the edit. PASS.
- Tune budget gates, never retry-to-green (testing-flakiness.md): caps from measurements. PASS.
- NO_FULL_HEAVY_SUITES_IN_MISSION: only named gate files. PASS.
- Pack edit → `spec-kitty doctrine regenerate-graph` (manifest hashes). PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-census-and-timeout-headroom-01M3PM2S/
├── spec.md
├── plan.md
├── tasks.md
└── tasks/
```

### Source Code (repository root)

```
packs/built-in/toolguides/{java,javascript,python}-supply-chain.toolguide.yaml
packs/built-in/pack-manifest.yaml                       (regenerated)
tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py
.github/workflows/ci-nightly.yml
tests/ci/test_nightly_timeout_headroom.py               (new)
docs/changelog/CHANGELOG.md
```

**Structure Decision**: existing layout; no new modules.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Census honesty

- **Purpose**: Make the SC-011 RAW_MATERIAL census count only genuine raw material and pin it with provenance.
- **Relevant requirements**: FR-001, FR-002, NFR-001
- **Affected surfaces**: the three supply-chain toolguide YAMLs, `pack-manifest.yaml`, `test_occurrence_map_field_paths.py` (docstring + `len(raw)`, `raw_files`, `raw_files & migrate_files`)
- **Sequencing/depends-on**: none
- **Risks**: a regenerated `*.graph.yaml` diff would mean the refs were not inert — stop and re-plan if so.

### IC-02 — Nightly timeout headroom

- **Purpose**: Re-derive capped nightly legs' `timeout-minutes` from measured maxima and pin the rule.
- **Relevant requirements**: FR-003, FR-004
- **Affected surfaces**: `.github/workflows/ci-nightly.yml` (caps + structured `# headroom:` comments), new `tests/ci/test_nightly_timeout_headroom.py` (parses the workflow only — no committed duration list, per LAND-PAT-005/SK-247), `tests/architectural/_interpreter_shard_roster.py` docstring (point at the new derivation), `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: none
- **Risks**: workflow-shape tests (`test_nightly_exit_code_honesty.py`, `test_interpreter_matrix_env_pinning.py`) parse this file — keep run lines untouched. Derived caps: shard 1 → 20, shard 2 → 31, shard 3 → 35, shard 4 25 (kept), shard 5 → 35, shard 6 25 (kept), out-of-matrix → 69.
