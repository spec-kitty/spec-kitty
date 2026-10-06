# Data model — module ownership

No persisted data changes. The "model" here is which module owns which name; the authoritative table is `REMOVED` in `tests/runtime/test_bridge_no_compat_delegates.py`.

| Module | Owns (#2560) | Imports (`runtime.next` seams) | Imported by |
|---|---|---|---|
| `runtime_bridge.py` | `decide_next_via_runtime`, `_dn_*`, `DecideNextContext`, `_check_cli_guards`, `_resolve_planned_wp_workspace`, `_resolve_owned_coordination_workspace`, `_owned_coordination_unavailable_decision`; re-exports the public names | query, decision_log, decision_mapping, guards, engine, io, identity, cores, composition, retrospective | CLI (`next_cmd`, `decision_verbs`, …), `decision.py` (deferred, `get_mission_type`), `coord_seed.py` (deferred, `_resolve_owned_coordination_workspace`) |
| `runtime_bridge_query.py` | read path: `query_current_state` + builders + `_query_*` + `_is_read_path_error`, `answer_decision_via_runtime`, `QueryModeValidationError`, `MissionNotFoundError` | decision_mapping, decision_log, engine, io, cores | bridge (re-export) |
| `runtime_bridge_decision_mapping.py` | `_materialize_decision`, `_map_*`, WP-board + WP-iteration family, merged/finalized short-circuits, `_wp_task_surface_error`, `TASKS_GLOB` | cores | bridge, query, engine, guards |
| `runtime_bridge_decision_log.py` | `DecisionGitLogUnavailable`, `_mission_routes_through_coordination`, `_is_owned_coordination_unavailable`, `_wrap_with_decision_git_log` | identity, io | bridge, query, io (deferred, the exception) |
| `runtime_bridge_guards.py` | guard facts (`_check_requirement_mapping_ready`, `_check_bare_prose_requirements_ready`, `_occurrence_gate_failures`, `_has_raw_dependencies_field` + helpers, `SPEC_ARTIFACT`, `TASKS_ARTIFACT`), `_should_advance_wp_step`, `_wp_blocks_step` | cores, decision_mapping | bridge, io, composition |
| `runtime_bridge_identity.py` | + `_resolve_runtime_feature_dir` | — (leaf) | io, decision_log, bridge, `decision.py` |
