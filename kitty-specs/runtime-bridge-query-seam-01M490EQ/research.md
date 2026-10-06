# Research — runtime-bridge-query-seam-01M490EQ

## R-1 Live dependency map (AST, stacked base 836f890e)

Computed with an AST walk over `src/runtime/next/runtime_bridge.py` (each top-level symbol → module-level names it references). Highlights that drive the split:

| Symbol (moves to) | Bridge-owned names it needs | Also used by the advance path? |
|---|---|---|
| `query_current_state` (query) | `_materialize_decision`, `_merged_mission_short_circuit`, `_query_*`, `_wp_task_surface_error`, `MissionNotFoundError` | — |
| `_query_dispatch_decision` (query) | the four `_build_*query*` builders, `_finalized_task_board_override_step` | — |
| `answer_decision_via_runtime` (query) | `_wrap_with_decision_git_log` | wrapper: yes (`_dn_bootstrap`) |
| `_map_runtime_decision` (mapping) | `_map_wp_step_decision`, `_map_non_wp_step_decision`, `_build_decision_required_prompt_file`, `_is_wp_iteration_step`, `_materialize_decision` | yes (`_dn_decision_materialize`, engine adapter) |
| `_build_wp_iteration_decision` (mapping) | `_wp_iteration_action_and_state` → `_resolve_wp_board_action` → WP-board family, `_finalized_task_board_override_step`, `_wp_task_surface_error` | yes (`_dn_finalized_board_override`, `_dn_dependency_gate`) |
| `_merged_mission_short_circuit` (mapping) | `_materialize_decision`, `_MERGED_MISSION_DONE_REASON` | yes (`decide_next_via_runtime`) |
| `_wrap_with_decision_git_log` (decision-log) | `DecisionGitLogUnavailable`, `_mission_routes_through_coordination`, `_is_owned_coordination_unavailable`; seams identity + io | yes |

Advance-path-only names that the mapping uses: none. `_wp_task_surface_error` is used by the bridge's `_should_advance_wp_step` too (it calls it on the mapping module after the move). `TASKS_GLOB` is used by `_count_wp_endings` (mapping) and by the bridge's `_should_advance_wp_step` / `_check_requirement_mapping_ready`; mapping owns it.

## R-2 Back-edges into the bridge

- `runtime_bridge_engine.advance_run_state_after_composition`: deferred `_rb._is_wp_iteration_step`, `_rb._map_runtime_decision` → removed (engine imports mapping at top level).
- `runtime_bridge_composition` (deferred `_rb._should_advance_wp_step`): unchanged; `_should_advance_wp_step` is an advance-path guard that stays in the bridge. Recorded as a remaining back-edge (out of scope).
- Outside the package: `decision.py` (deferred `_resolve_runtime_feature_dir`, `get_mission_type`) and `coordination/coord_seed.py` (deferred `_resolve_owned_coordination_workspace`) import names that stay in the bridge. `next_cmd.py`, `decision_verbs.py`, `implement_phases.py`, `workflow_executor.py`, `mission_loader/command.py` use public names only.

## R-3 Import-cycle check for the new modules

- identity: imports only `specify_cli.mission_metadata` (leaf). io imports identity at top level. → the wrapper (which calls `_io_seam.resolve_commit_target`) cannot live in identity without an io ↔ identity cycle (plan D-2).
- cores: imports only `runtime.next.decision` (gate `test_bridge_cores_import_boundary.py`).
- `runtime.next.decision` imports the bridge only inside functions (deferred).
- engine imports retrospective + `runtime.next.decision`; adding mapping at top level is acyclic as long as mapping never imports engine/bridge/query.

## R-4 Gates that name moved code by path

`test_no_write_side_rederivation.py` (census pair + write-dir consumer list), `test_runtime_emitter_seam.py` (S8 checks `answer_decision_via_runtime` inside `runtime_bridge.py`). Details in plan D-6.

## R-5 Baseline evidence

Stacked base `836f890e`; targeted surface = 111 paths (every non-architectural test file referencing `runtime_bridge`, plus `tests/runtime`, `tests/next`, `tests/specify_cli/next`). Baseline: **2804 passed, 4 skipped, 0 failed** (13m45s, `-n 8 --dist loadfile`, probe + coverage loaded). Probe: 660 recorded patches on `runtime.next.runtime_bridge*` modules (372 on the bridge itself); 86 bridge patches are never invoked on the base. Most are intentional "must not be called" fakes, and the rest are pre-existing dead patches (top: `runtime_emitter_for_mission` 33, `runtime_next_step` 11, `get_mission_type` 9, `get_or_start_run` 6). Coverage of the moved code is high; 8 functions have missed lines (plan IC-01 targets).

The red-first layout test `tests/runtime/test_bridge_query_seam_layout.py` gives **56 failed, 7 passed** on the base. The 7 passes are the planted-edge self-mutation cases, which are independent of the move.

## R-6 Go-silent patch dispositions

Static cross-check on the final layout (WP05 T020). S = module-level names one of the four new seams reads that the slimmed bridge still binds: `get_mission_type`, `_compute_wp_progress`, `_state_to_action`, `_build_prompt_or_error`, `now_utc_iso`, `runtime_emitter_for_mission`, `seed_runtime_emitter`, `logger`, the shared seam module objects (`_cores`, `_io_seam`, `_engine_adapter`, `_identity_seam`, `_mapping`, `_decision_log`), and types/constants. A scan of `tests/**` for `runtime_bridge.<n in S>` patches (string targets, `patch.object` / `monkeypatch.setattr` on a bridge alias, multi-line forms included) finds **45 sites**. Every one of them steers code that stayed in the bridge, so each is **live via a kept bridge caller** wherever its test reaches that code. A few are dormant in some tests, unchanged from the base: the composition-suite autouse emitter fixture (`test_runtime_bridge_composition.py:58`) records 0 calls in the tests that never reach `_dn_bootstrap`, and the raising "must not be called" fakes record 0 by design:

| Sites | Names | Code under test (bridge-resident reader) |
|---|---|---|
| `tests/next/test_runtime_bridge_blocked_paths.py:206–375` (4 tests) | `get_mission_type`, `runtime_emitter_for_mission`, `_compute_wp_progress`, `_state_to_action`, `_build_prompt_or_error` | `decide_next_via_runtime` → `_dn_bootstrap` (mission type, emitter, progress) and the guard branch of `_dn_dependency_gate` (action, prompt) |
| `tests/runtime/test_bridge_decide_next.py:259–495` (6 tests) | `get_mission_type`, `runtime_emitter_for_mission` | `_dn_bootstrap` |
| `tests/runtime/test_bridge_decide_next.py:607–723` (6 tests) | `_state_to_action`, `_build_prompt_or_error` | `_dn_dependency_gate`, `_dn_composition_blocked_decision` |
| `tests/next/test_runtime_bridge_unit.py:251, 896, 2283` | `runtime_emitter_for_mission` | `decide_next_via_runtime` (`_dn_bootstrap`); the two full-loop autouse fixtures patch the query module too (WP04) |
| `tests/next/test_next_command_integration.py:551` | `_compute_wp_progress` | `_dn_bootstrap` |
| `tests/specify_cli/next/test_runtime_bridge_composition.py:58` | `runtime_emitter_for_mission` | `_dn_bootstrap` (composition-dispatch tests drive the advance path only) |

Dynamic confirmation: each per-WP reviewer ran an independent call-count probe (a pytest plugin that wraps `MonkeyPatch.setattr` / `mock._patch.__enter__` for `runtime.next.runtime_bridge*` targets) before and after its commit. WP02: 92 pairs moved from the bridge to the mapping module with the same counts, none dropped. WP03: 306/306 pairs identical. WP04: no pair dropped except the 9 `get_mission_type` patches removed on purpose, which had 0 calls on the base. WP06: 683/683 keys identical apart from a concurrency-race count. End-to-end (WP05, baseline 836f890e against the final tree): 656 → 649 unique (test, name) pairs; no steering patch lost calls; the 10 removed patches all had 0 calls on the base.

Patches that were already dead on the base and that this mission fixed (in files it touched): the 9 `get_mission_type` patches in `test_query_mode_unit.py` (removed), and an `_is_wp_iteration_step` fake in `test_runtime_bridge_blocked_paths.py` that was never invoked (removed). Never-invoked fakes that are deliberate ("must not be called" raisers) were left as they are.
