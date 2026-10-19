# Implementation Plan: Deep ROI pass over the large tests/charter suites

**Branch**: `feat/6485-charter-tests-deep-roi-pass` (stacked on PR #6483) | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

## Summary

Review the in-scope `tests/charter/` files function by function against the issue #6485
rubric, and delete or consolidate tests that do not guard a live contract. Work is sliced
into six work packages by file cluster, with disjoint file sets so they run as parallel
lanes. Each work package writes its own ROI ledger. No product code changes.

## Technical Context

**Language/Version**: Python 3.11+ (test code only)
**Primary Dependencies**: pytest, pytest-xdist, pytest-cov (existing dev group; no dependency change)
**Storage**: N/A
**Testing**: `pytest tests/charter tests/charter_offering -n auto --dist loadfile`; coverage via `--cov=src/charter`
**Target Platform**: Linux/macOS/Windows CI (unchanged)
**Project Type**: single project — test-suite remediation
**Performance Goals**: `tests/charter/` wall-clock does not increase (NFR-003)
**Constraints**: no `src/` edits (C-001); no `tests/architectural/` edits (C-002); ≤ 1.0 pp `src/charter` coverage drop (NFR-002)
**Scale/Scope**: ≈ 20k lines across ~45 files in `tests/charter/`

Supply chain: no dependency is added, upgraded or removed, so `DIRECTIVE_051` has no
control to evaluate.

## Charter Check

- **Test remediation (Standing Order #4, `DIRECTIVE_041`)**: judge the test, not git-blame; stub/change-detector → delete. This mission applies it. PASS.
- **Red-first / ATDD (C-011)**: no behaviour is added or fixed, so no failing-first test exists to write. The acceptance evidence is instead the ledger plus a green suite and a coverage delta. Recorded as a justified deviation in Complexity Tracking.
- **No full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`)**: WPs run only their own files plus the covering tests they name; the orchestrator runs `tests/charter` + `tests/charter_offering` for the before/after coverage. PASS.
- **Tiered rigour / reviewer ≠ implementer**: review by an opus `reviewer-renata`, implement by sonnet `python-pedro`. PASS.
- **Terminology canon**: no user-facing prose beyond the changelog. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-tests-deep-roi-pass-01M5AN9J/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── roi-ledger/WP0N.md   # one per WP, written during implement
└── tasks.md / tasks/    # /spec-kitty.tasks
```

### Source Code (repository root)

```
tests/charter/            # edited (deletions / consolidations only)
tests/charter_offering/   # read-only: covering tests
tests/architectural/      # read-only: covering tests
```

## Complexity Tracking

| Deviation | Why needed | Simpler alternative rejected because |
|-----------|------------|--------------------------------------|
| No red-first test per WP | Pure test removal adds no behaviour to pin | A synthetic failing test would itself be a tautology this mission deletes |

## Implementation Concern Map

The baseline coverage and test count before the mission are recorded in `research.md`.

### IC-01 — Context family
`test_context.py`, `test_context_selection_render.py`, `test_context_render_seams.py`,
`test_context_service_seams.py`, `test_context_leaf_seams.py`,
`test_context_profile_lineage_parity.py`; cluster 2 (`activation/test_context_identity_reuse.py`
↔ `activation/test_context_org_root_identity.py`).

### IC-02 — Synthesizer
`synthesizer/test_synthesize_reconcile.py`, `test_orchestrator_resynthesize.py`,
`test_bundle_validate_extension.py`, `test_manifest.py`; cluster 1
(`test_synthesize_path_parity.py` ↔ `test_orchestrator_synthesize.py`).

### IC-03 — Packs and org
`packs/test_pack_validator.py`, `activation/test_org_charter.py`,
`activation/test_org_charter_merge_parity.py`, `test_org_drg_loader.py`,
`test_pack_manager.py`; cluster 6 (`test_retired_pack_fields.py` ↔
`test_retired_accompanies_doctrine_pack.py`).

### IC-04 — Resolver, activation, compiler
`test_resolver.py`, `test_resolver_activation_parity.py`, `test_cascade.py`,
`test_compiler.py`, `test_mission_type_profiles.py`,
`test_mission_type_activations_seed_read_parity.py`; cluster 3
(`activation/test_effective_set.py` ↔ `activation/test_effective_set_chain.py`).

### IC-05 — Remaining parity, schemas, cwd, sync
`test_config_stem_parity.py`, `test_charter_generate_scoped_reference_parity.py`,
`test_spdd_reasons_activation_parity.py`, `test_kind_vocabulary_recursion_parity.py`,
`test_check_graph_kind_parity.py`, `test_direct_write_kinds_parity.py`; clusters 4
(cwd), 5 (`test_schemas*.py`) and 7 (`test_sync_paths.py` ↔ `test_sync.py`).

### IC-06 — Heavy tests (operator-added)
`test_compiler_charter_yaml.py`, `test_context_unknown_language.py`,
`test_regenerate_rederives_languages.py`, `test_progressive_disclosure.py`,
`test_every_load_delivery.py`, `test_active_languages_idempotency.py`,
`test_retrospective_governance_emit.py`, `test_activation_preserves_effective_4253.py`.
Same rubric, plus cost reduction that keeps the contract (FR-007).

Each IC owns a disjoint file set; a merge target named in a ledger must be inside the
same IC's file set.
