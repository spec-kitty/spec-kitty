# Contract: `spec-kitty upgrade` worktree selection

```
spec-kitty upgrade [--include-worktree PATH]... [--all-worktrees] [--no-worktrees] ...
```

- Default: non-Mission worktrees under `.worktrees/` are not written or committed.
- `--include-worktree PATH` (repeatable): opt that worktree in. PATH is absolute or relative to the project root and must resolve to a direct child of `.worktrees/`; otherwise exit 2 with `UPGRADE_WORKTREE_NOT_FOUND` before any write, also when combined with `--all-worktrees`.
- `--all-worktrees`: opt every non-Mission worktree in (previous default behaviour).
- `--no-worktrees` with either opt-in flag: exit 2 (`conflicting options`) before any write.
- Mission and detached worktrees: always skipped (unchanged, #5457).

The normal preview (`--dry-run`, and the plan shown before the confirm prompt) prints what the run will do:

```
Worktrees:
  .worktrees/land-7086 (land-7086): skipped, not selected (use --include-worktree .worktrees/land-7086 or --all-worktrees)
  .worktrees/foo-lane-a (kitty/mission-foo-lane-a): skipped, Mission worktree
  .worktrees/wip-x (wip/x): will be upgraded and committed
```

A selected worktree reads `will be upgraded, not committed (auto-commit off)` when auto-commit is off, and `selected, nothing to upgrade (nothing will be written)` when no migration is pending and the version moves, so the worktree pass does not run.

After a real run the block reports what the run actually did for each worktree, from the runner's per-worktree result (`upgraded and committed`, `upgraded, not committed (auto-commit off)`, `upgraded, not committed (see warnings)` with the named no-commit reason among the warnings, `selected, nothing to upgrade (nothing written)`, `selected, migrations failed here, nothing committed (see errors)`), never the selection alone. A directory under `.worktrees/` that is not a git worktree is labelled `(not a git worktree)` and is still an opt-in target (as before this change). An entry that resolves outside `.worktrees/` (an escaping symlink) is never selectable, not even by `--all-worktrees`, and gets no `--include-worktree` hint. `--cli` with an opt-in flag, and `--no-worktrees` with an opt-in flag, exit 2 before any write.

`--plan-json`: the document stays within the frozen `upgrade-plan` schema (schema_version 1, `kitty-specs/upgrade-preview-mission-health-01M1V6E1/contracts/upgrade-plan.schema.json`); no key is added. The worktree report travels as `severity: "info"` entries of `diagnostics`: one `WORKTREE_SELECTION` (`owner: null`, message `worktree selection: none` | `worktree selection: all` | `worktree selection: named (<path>, ...)`), then one per `.worktrees/` entry in name order with `owner` = its display path and `code` one of `WORKTREE_SELECTED`, `WORKTREE_SKIPPED_MISSION`, `WORKTREE_SKIPPED_NOT_SELECTED`; the message is the preview line (`<path> (<branch>|detached|not a git worktree): <what happens>`, including the opt-in hint, or `resolves outside .worktrees/ (cannot be selected)` for an escaping symlink). A refused opt-in keeps its error diagnostic (e.g. `UPGRADE_WORKTREE_NOT_FOUND`) first and adds the `WORKTREE_SELECTION` diagnostic for the selection as requested. `commit_policy.worktrees_enabled` is true only when at least one worktree is selected.
