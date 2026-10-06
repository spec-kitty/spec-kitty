# Symbol Ownership Map

The mission's only "data" is the ownership of 36 names. Each row says which seam owns the
name after the mission and what the bridge delegate did on `main` (1458e92e).

| # | Owning seam | Name | Delegate kind on `main` |
|---|-------------|------|-------------------------|
| 1 | `runtime_bridge_identity` | `_primary_runtime_feature_dir` | pure forward |
| 2 | `runtime_bridge_identity` | `_resolve_coordination_branch` | pure forward |
| 3 | `runtime_bridge_identity` | `_resolve_mission_ulid` | pure forward |
| 4 | `runtime_bridge_cores` | `_parse_wp_sections_from_tasks_md` | pure forward |
| 5 | `runtime_bridge_cores` | `_parse_requirement_refs_from_tasks_md` | ADAPTER: injects grammar= (specify_cli.requirement_mapping.grammar), composes through the bridge's own section parser |
| 6 | `runtime_bridge_retrospective` | `_BufferingRuntimeEmitter` | subclass alias (no override) |
| 7 | `runtime_bridge_retrospective` | `_rich_hic_prompt` | pure forward |
| 8 | `runtime_bridge_retrospective` | `_resolve_mission_id_for_terminus` | pure forward |
| 9 | `runtime_bridge_retrospective` | `_build_retrospective_facilitator_callback` | pure forward |
| 10 | `runtime_bridge_retrospective` | `_resolve_retrospective_policy_for_runtime` | pure forward |
| 11 | `runtime_bridge_retrospective` | `_run_retrospective_learning_capture` | pure forward |
| 12 | `runtime_bridge_retrospective` | `_classify_exc` | pure forward |
| 13 | `runtime_bridge_retrospective` | `_remediation_hint` | pure forward |
| 14 | `runtime_bridge_retrospective` | `_classify_and_emit_failure` | pure forward |
| 15 | `runtime_bridge_io` | `_load_feature_runs` | ADAPTER: load_feature_runs(_feature_runs_path(repo_root)); name differs from owner |
| 16 | `runtime_bridge_io` | `_mission_key_for_run_ref` | pure forward |
| 17 | `runtime_bridge_io` | `_build_run_ref` | ADAPTER: threads run_ref_cls=runtime_bridge.MissionRunRef |
| 18 | `runtime_bridge_io` | `_build_discovery_context` | pure forward |
| 19 | `runtime_bridge_io` | `_resolve_runtime_template_in_root` | pure forward |
| 20 | `runtime_bridge_io` | `_runtime_template_key` | pure forward |
| 21 | `runtime_bridge_io` | `_existing_run_ref` | pure forward |
| 22 | `runtime_bridge_io` | `_start_ephemeral_query_run` | pure forward |
| 23 | `runtime_bridge_io` | `get_or_start_run` | pure forward -> becomes PUBLIC RE-EXPORT |
| 24 | `runtime_bridge_io` | `_resolve_run_dir_for_mission` | pure forward |
| 25 | `runtime_bridge_io` | `_resolve_tech_stack_for_profile` | pure forward |
| 26 | `runtime_bridge_io` | `build_operational_context_for_claim` | pure forward -> becomes PUBLIC RE-EXPORT |
| 27 | `runtime_bridge_io` | `_build_operational_context_for_decision` | pure forward |
| 28 | `runtime_bridge_composition` | `_normalize_action_for_composition` | pure forward |
| 29 | `runtime_bridge_composition` | `_should_dispatch_via_composition` | pure forward |
| 30 | `runtime_bridge_composition` | `_resolve_step_agent_profile` | pure forward |
| 31 | `runtime_bridge_composition` | `_resolve_runtime_contract_for_step` | pure forward |
| 32 | `runtime_bridge_composition` | `_count_source_documented_events` | pure forward |
| 33 | `runtime_bridge_composition` | `_publication_approved` | pure forward |
| 34 | `runtime_bridge_composition` | `_check_composed_action_guard` | pure forward |
| 35 | `runtime_bridge_composition` | `_dispatch_via_composition` | pure forward |
| 36 | `runtime_bridge_engine` | `_advance_run_state_after_composition` | pure forward to runtime_bridge_engine.advance_run_state_after_composition (name differs) |

Counts: identity 3, cores 2, retrospective 9, io 13, composition 8, engine 1 = **36**.

## Names that stay on the bridge

- `_check_cli_guards`: real composition logic mislabelled "Thin compat delegate"; kept, docstring fixed.
- Back-edge targets the bridge still owns (not delegates): `_should_advance_wp_step`, `_is_wp_iteration_step`,
  `_map_runtime_decision`, `_resolve_runtime_feature_dir`, `_has_raw_dependencies_field`,
  `_check_requirement_mapping_ready`, `_check_bare_prose_requirements_ready`, `_occurrence_gate_failures`.
  These are #2560's concern.

## Invariants

- After the mission, none of the 36 names is defined at the bridge's top level (as a `def`, `class` or assignment),
  except the two public re-exports, which are bound by `from runtime.next.runtime_bridge_io import ...` and are the
  very same objects (`is`).
- No seam reads any of the 36 names off the bridge.

