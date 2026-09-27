# Contract — `spec-kitty consolidate` command surface

## Command
- **Primary**: `spec-kitty consolidate` — lane-consolidation operation (folds approved lanes into the Target Ref).
- **Removed**: `spec-kitty merge` — hidden stub; exits non-zero with a message naming `consolidate`. Not a working alias (C-004).

## Flags (carried over verbatim from the former `merge` command)
| Flag | Behavior | Change |
|---|---|---|
| `--mission <handle>` / `--feature` | select mission | unchanged |
| `--resume` | resume from persisted `state.json` | unchanged (same file) |
| `--abort` | abort + teardown per retention | unchanged |
| `--dry-run` | conflict/retention forecast | unchanged |
| `--keep-branch` / `--keep-worktree` | retention overrides | unchanged |
| `--target <branch>` | target ref | unchanged |

## Invariants
- Exit codes and forecast/`--json` payload keys are preserved (consumer/orchestrator-api contract).
- `state.json` schema, filename, and directory are unchanged.
- `MergeStrategy` values (`"merge"`/`"squash"`/`"rebase"`) are unchanged serialized values.
- `baseline_merge_commit` continues to be written/read exactly as before.

## Machine-contract surfaces to update together (review focus, pr-landing.md §7)
- `src/specify_cli/core/upstream_contract.json` (if it enumerates the command)
- CLI reference docs (`docs/api/cli-commands.md`) regenerated
- `command_installer.py` command list/description/command-map
