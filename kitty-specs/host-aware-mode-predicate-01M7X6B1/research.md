# Research: Host-aware mode predicate

All findings were verified on `main` 996f5d6a / 873ca367. Reproductions use the NTFS emulation described in plan.md.

## R-1 Root cause of the 253 phantom effects (#4927)
- **Finding**: `runtime/asset_preparation.py::_action` returns `"chmod"` when `before.mode != after.mode`. `_prepare_skill_tree` stamps every skill directory 0o755, and NTFS reports 0o777, so the startup sync (`ensure_global_agent_skills`) plans 252 directory chmods (63 dirs x 4 roots) and 1 file chmod. It re-plans them identically after apply.
- **Evidence**: an emulated run gave `Counter({('chmod','directory','0o777','0o755'): 252, ('chmod','file','0o666','0o644'): 1})`, and 253 again after one sync. The POSIX twin gives 0.
- **Decision**: route the action decision through one host-aware predicate.

## R-2 Existing relaxation and its reach
- **Finding**: `windows_dir_mode_only_divergence` (`skills/command_installer.py`) already ignores Windows file and symlink modes wholesale (the #4927 "T005" change in 6269777dc). It is consulted only by `skills/installer.py` (2 sites) and `tool_surface/providers/managed_skills.py`. 6269777dc touched `kernel/no_follow.py`, `skills/command_installer.py`, `skills/installer.py` and tests, not `operations.py` or `projection.py` as the 2026-09-22 mission comment claimed.
- **Decision**: delete it and re-point its callers. Operator ruling 2 replaces "ignore file mode" with "compare the write bit".
- **Alternatives**: keep it as an alias. Rejected, because it would be a second authority (DIRECTIVE_044).

## R-3 The validator is a second raw authority
- **Finding**: `PhysicalEffect.__post_init__` refuses any effect whose action differs from `operations._action(before, after)`, which compares raw modes.
- **Decision**: make `operations.effect_action` host-aware and the single action function. Every ladder delegates to it, so planner and validator agree by construction.
- **Risk / alternative**: a missed raw planner then raises on Windows instead of phantom-repairing. The alternative, a validator that accepts chmod or None when modes are equivalent, was rejected: it would leave the defect class silently alive. The gate (IC-04) makes a missed site a CI failure.

## R-4 Site adjudication
Comparisons of an observed state against a planned stamp. These move to the predicate:
- `asset_preparation._action`;
- `operations._action`;
- `command_installer.effect` (immune today because it plans `before.mode` for files and only creates dirs);
- `installer` project ladder;
- `installer._command_parent_receipts`;
- `managed_skills._recheck_command_completion`;
- `projection._stage_effect`;
- the `projection._recheck_selected` stamp substitutions;
- the `projection` finalize postcondition (`same_observation(final, replace(created, state=effect.after))`);
- `agent_profiles._sibling_created_planned_dir`;
- `native_config._directory_postcondition_holds`;
- `installer._apply_project_skill_write` symlink chmod;
- `manifest.save` chmod.

Comparisons that stay exact:
- observed vs observed (guards):
  - `projection.same_observation` generic;
  - `projection` finalize fstat identity triple;
  - `installer` `current != effect.before`;
  - `agent_profiles` `observed != effect.before`;
  - `asset_preparation.check_assets`;
  - `projection` staged destination precondition;
- planned vs planned (conflicts): `operations` merge of identical effects, `asset_preparation` conflicting outputs, `projection` conflicting staged members.

## R-5 Windows semantics (operator ruling 2)
- Directories: kind only. Symlinks: mode ignored. Files: `bool(mode & 0o200)` must match (NTFS synthesizes 0o666 or 0o444, and `chmod` toggles exactly that).
- POSIX: exact equality, unchanged.

## R-6 Emulation fidelity
- Planners observe through `Path.lstat`/`os.lstat`/`os.stat`/`os.fstat`, and writers through `Path.chmod`/`os.chmod`/`os.fchmod`. The fixture patches those `os` functions. `pathlib` calls them at call time on 3.11. `os.DirEntry.stat` is not used for modes.

## R-7 No dependency changes
No dependency is added, upgraded or removed, so the supply-chain controls are not applicable.
