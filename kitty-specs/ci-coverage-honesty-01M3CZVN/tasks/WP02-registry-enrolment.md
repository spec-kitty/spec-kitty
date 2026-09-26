---
work_package_id: WP02
title: Registry enrolment (greens the guards)
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-009
- NFR-001
- NFR-003
planning_base_branch: feat/ci-coverage-honesty
merge_target_branch: feat/ci-coverage-honesty
branch_strategy: Planning artifacts for this mission were generated on feat/ci-coverage-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/ci-coverage-honesty unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-coverage-honesty-01M3CZVN
base_commit: 39c7d5b16998dbbfc5c064d3f4376e8a62294a34
created_at: '2026-09-25T21:17:57.003666+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T012
phase: Phase 2 - Registry remediation
history:
- at: '2026-09-25T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/ci-module-registry.yml
- .github/ci-shard-timings.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Use `/ad-hoc-profile-load` to load `python-pedro` (implementer, claude) before anything else.

---

## Objectives & Success Criteria
SHRINK the WP01 guard baselines by remediating the registry — all registry edits in one owner to avoid parallel collisions. WP01 guards are already GREEN at baseline; this WP removes {live_work, config, calibration, tasks_authoring, diagnostics, bootstrap} from the in-matrix-dark baseline and ratchets agent's ratio up, then **updates `.github/ci-foreign-coverage-baseline.json` to the new (smaller) baseline** so the guards assert the shrink. After this WP: `pytest tests/architectural/test_foreign_coverage_guard.py test_src_reachability_guard.py test_gate_selection_authority.py test_module_shard_registry.py test_pyproject_shape.py` all GREEN with the shrunk baseline.

Read `research.md` (D3/D4/D5-tier), `data-model.md`, `contracts/guards-contract.md`.

## Subtasks

### T007 — agent row own-root ratchet (FR-004)
Add `test_dirs` to the `agent` row including the REAL own-root dir **`tests/specify_cli/agent_utils`** (exists; imports agent_utils) alongside `tests/agent`. Remove `tests/specify_cli/agent_utils` from `out_of_matrix_test_dirs` in the same edit (no double-claim). This ratchets agent's own-root ratio up (the per-root floor was already met per F17).

### T008 — enrol live_work test dir for per-PR execution (FR-005, REVISED — no dedicated row)
Enrol `tests/specify_cli/live_work` into an EXISTING in-matrix module row's `test_dirs` whose `cov_targets` legitimately cover it (`core_misc` — cov_targets include `specify_cli`) and remove `tests/specify_cli/live_work` from `out_of_matrix_test_dirs` in the SAME change (claimed-once guard). This runs its 149 tests per-PR. Do NOT mint a dedicated `live_work` row — that needs coordinated scrub-JSON + ci-router edits guarded by transcription/bijection checks (deferred follow-up); enrolment achieves the per-PR-execution intent in-scope. Verify no double-claim.

### T009 — re-measure the enrolled row's shard timings (NFR-001)
After T008/T010 add test dirs to the host row(s) (e.g. `core_misc`), run `<mainvenv>/python scripts/ci/capture_shard_timings.py --module core_misc --write` (and any other host row) so the added tests' durations are measured and the shard-skew stays honest (avoids the stale-timings caveat). Document provenance.

### T010 — enrol dark packages (FR-009, 4 packages)
For `config, calibration, tasks_authoring, bootstrap`: their tests exist in out-of-matrix dirs — enrol each dir into an appropriate in-matrix row's `test_dirs`, removing the matching `out_of_matrix_test_dirs` entries. `schemas` excluded (data dir). **`diagnostics` is NOT enrolled** — it is imported only by `tests/e2e` (per-PR path-routed, so covered but not a module shard); it stays in the recorded in-matrix-dark baseline as honest debt. Verify the 4 (+live_work subpkgs) leave in_matrix_dark.

### T011 — MOVED TO WP03
The dead-tier retirement (`special_tiers.integration_tests_next`) + repointing `test_module_shard_registry.py::test_special_tiers_encode_heavy_pole_deserialization` now lands in WP03 alongside the replacement nightly lane, so the guard is repointed (not left red). Do NOT touch the tier here.

### T012 — update baseline + verify green together
Update `.github/ci-foreign-coverage-baseline.json`: remove the 5 enrolled packages (`live_work`(+subpkgs), `config`, `calibration`, `tasks_authoring`, `bootstrap`) from the in_matrix_dark set (27→~22), and re-measure agent's own_root_ratio (higher with `tests/specify_cli/agent_utils` added). Keep `diagnostics` in the baseline. This sidecar is WP01-owned — editing it here is an intentional sequential out-of-map edit (record the rationale in the commit). Run the full guard + registry test set; confirm all green with the shrunk baseline, no double-claim, and that the guard would FAIL if the baseline still listed an enrolled package (shrink is asserted).

## Branch Strategy
Planning base `feat/ci-coverage-honesty` → main via squashed PR. Lane worktree per `lanes.json`. Depends on WP01.

## Definition of Done
- All WP01 guards + shard-registry + authority tests GREEN together.
- shard_count measured (NFR-001); no double-claim; no per-PR wall-clock beyond enrolled dirs (NFR-003).
- No `kitty-specs/` paths touched (registry/timings only).

## Reviewer guidance
Verify: each enrolment removes the matching out_of_matrix entry (no double-claim); live_work shard_count traces to ci-shard-timings.json; dark packages truly become reachable; dead tier fully removed; agent per-root floor satisfied by the real dir (not the phantom).

## Activity Log

- 2026-09-25T21:31:44Z – claude – shell_pid=2932038 – Blocked: 3 cross-cutting scope conflicts. (1) diagnostics only imported by tests/e2e (path-routed, not enrollable into a module row) -> cannot leave in_matrix_dark in-scope. (2) live_work NEW row (T008/T009) requires edits to tests/release/ci_retirement_scrub.json + .github/workflows/ci-router.yml (bijection/verbatim/transcription guards) — outside owned files. (3) T011 removing special_tiers.integration_tests_next breaks tests/architectural/test_module_shard_registry.py::test_special_tiers_encode_heavy_pole_deserialization (no in-mission WP restores it). In-scope subset (T007 agent ratchet + enrol config/calibration/tasks_authoring/bootstrap+live_work.adapters via existing rows) shrinks in_matrix_dark 27->22 green, but only 5/6 and adds untimed dirs to core_misc/agent (NFR-001 timing smell). Needs operator/plan decision — see subagent report.
