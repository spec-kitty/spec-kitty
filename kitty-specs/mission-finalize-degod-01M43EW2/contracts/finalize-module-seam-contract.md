# Contract: finalize module family seam surface

The internal contract the `mission_finalize` decomposition (#5627) keeps for its callers and tests. `tests/specify_cli/cli/commands/agent/test_mission_finalize_phase_modules.py` enforces it.

| # | Guarantee | Enforced by |
|---|---|---|
| S-1 | `specify_cli.cli.commands.agent.mission_finalize.<name>` resolves, with object identity, to the defining module's object for every top-level name of every phase module. | `test_mission_finalize_reexports_every_phase_definition` |
| S-2 | A patch on `mission_finalize.<name>` intercepts calls from inside phase modules for every patched name and every seam function (`_emit_json`, `_read_wp_frontmatter`, `_resolve_planning_branch_via_mission`, `_bootstrap_canonical_state_via_mission`, `_validate_ownership_via_mission`). | `test_phase_modules_never_call_a_seam_function_unrouted`, `test_*_patch_intercepts_*` |
| S-3 | No phase module imports `mission_finalize` at module scope. The routing import is lazy and in-function. | `test_phase_module_never_imports_mission_finalize_at_module_scope` |
| S-4 | All finalize log records use the logger `specify_cli.cli.commands.agent.mission_finalize`. | `test_logger_name_is_pinned_to_mission_finalize` |
| S-5 | The command surface (`spec-kitty agent mission finalize-tasks` options, JSON payloads, refusal codes, exit codes) is unchanged. | the existing finalize behavioural corpus |
| S-6 | Structural pins read the module family, not a single file. | `tests/_support/finalize_source.py`, `tests/_support/test_finalize_source.py` |
