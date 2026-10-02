# Contract amendment: router two-authority — `ci_config` group and the partitioned battery

**Amends**: `kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/router-two-authority.md` (that file is byte-frozen by `tests/architectural/test_archive_root_byte_identical.py`; this mission records the amendment here instead of editing it).
**Mission**: `ci-runtime-stabilisation-01M3TZH6` (issue #5510) · **Decision Moments**: 01M3TZHTVXWTFYPW8TD73F3FZJ, 01M3V02DWR56AAPTF06J46YXH0, 01M3V1FAQV07WJF3RYAFN9J7GC

## Unchanged invariants

1. The two CI path routing authorities remain the router filter block and the job `if:` gates in `.github/workflows/ci-router.yml`, kept in lockstep.
2. `scripts/ci/gate_selection.py` remains a derived parser of those authorities; it is never given a parallel encoding of a group.
3. A `src/**` path matching no named group still sets `unmatched=true` and fans out to run-all (#3463 class).
4. The path-scoped battery stays a non-required check (ADR 2026-09-23-1).

## Amendments

A1. **New non-src group `ci_config`.** Paths: `.github/workflows/**`, `.github/actions/**`, `scripts/ci/**`, `pytest.ini`, `pyproject.toml`, `Makefile`, `.github/ci-module-registry.yml`, `.github/ci-shard-timings.json`. It gates **only** the architectural battery. It reverses, for the battery alone, the "CI-config changes gate no router job" rulings of #4386 and #5302; the existing `ci` group, its "gates no router job" pin and its registry scrub mirror are untouched. `_ci_integrity_oracle.HEAVY_BATTERY_NON_SRC_GROUPS` becomes `{"architectural", "ci_config"}`.

A2. **Battery shape.** The battery is an always-on `architectural-fast` job (registry-held roster) plus `architectural-heavy` as a single job key with a 2-leg `include:` matrix (`--battery-part 1/2`, `2/2`). The heavy job's `if:` remains the code-scoped expression (src-backed groups ∪ `HEAVY_BATTERY_NON_SRC_GROUPS`) ∧ ¬prose_only. `architectural-fast` joins `MUST_RUN_ALWAYS_ON_GATES` and router-gate `needs`.

A3. **Removed per-group router shards.** `tests (cli)`, `tests (status)`, `tests (consolidation)` and `tests (corpus)` are deleted; their module rows (and the Packs corpus lane) are the sole homes. Router-gate `needs` shrinks accordingly.

A4. **Ready-for-review short-circuit.** On a `pull_request` `ready_for_review` event, the `changes` selection job may skip its path-filter step when `scripts/ci/green_match.py` finds a successful run for the same tested key (see `green-match.md`); every path-gated job then skips and the router gate reports success. Push, dispatch, re-run attempts and other `pull_request` actions are never short-circuited.

## Verification

- `tests/architectural/test_gate_selection_authority.py` and `test_ci_quality_path_filters.py` pass with no `gate_selection.py` edit.
- Gate selection for a CI-config-only changed-path set selects `architectural-heavy`; for a prose-only set it does not.
- `test_ci_module_wiring.py::test_ci_group_gates_no_router_job_and_stays_out_of_the_catch_all` stays green unchanged.
