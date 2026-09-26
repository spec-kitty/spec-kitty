# Research: Squash Merge Target Safety

## Scope

GitHub issue #4892 demonstrates that the default mission-to-target branch
integration runs `git merge --squash -X theirs`. When both the target and the
mission modify an ordinary source path, Git silently selects the mission hunk,
the command exits successfully, and later lifecycle cleanup makes the loss hard
to notice. This mission covers the default squash strategy and its dry-run
forecast. Lane consolidation and the explicit `merge` and `rebase` strategies
are controls, not change targets.

## Evidence

### E-001: the destructive choice is localised

`src/specify_cli/lanes/merge.py::_merge_branch_into` supplies `-X theirs` only
for `MergeStrategy.SQUASH`. The target ref is advanced only after the isolated
worktree merge and commit succeed. Therefore normal Git conflict failure already
has the required atomicity: the temporary worktree can be discarded while the
target ref and primary checkout remain unchanged.

### E-002: blanket removal must preserve governed reconciliation

The same module activates custom merge drivers for event logs, metadata, traces,
and gate artifacts through `_ephemeral_merge_driver_activation`. Those drivers
are path-specific and should remain authoritative. Target-newer PRIMARY-partition
planning artifacts have a separate history-aware reconciliation seam in
`src/specify_cli/merge/planning_recency.py` and
`_preserve_target_newer_planning_artifacts`. A safe implementation must not
replace either mechanism with a new global favour-ours/favour-theirs policy.

### E-003: dry-run currently omits Git integration readiness

`src/specify_cli/merge/forecast.py::run_dry_run_forecast` checks lane state,
review artifacts, retention, and mission numbering, but never exercises the
mission-to-target Git operation. Its successful payload key set is frozen by
`tests/merge/test_forecast_seam.py`; a conflict should therefore use the existing
blocked/error channel rather than add keys to the clean-success payload.

### E-004: the ticket reproduction establishes the regression oracle

The issue fixture starts from one shared source file, changes the same line on
the mission and target branches, and observes exit 0 plus the mission value on
the target. The explicit merge and rebase strategies instead report a conflict
and preserve the target SHA. The regression test should reduce this to the
lowest public seam while retaining assertions for bytes, refs, exit status, and
dry-run parity.

## Decisions

### D-001: fail closed for ungoverned content conflicts

The default squash command will use normal three-way merge semantics, without
`-X theirs`. Any unresolved ordinary path blocks integration. Diagnostics may
name paths and branches but must not claim that cleanup occurred.

### D-002: keep reconciliation path-scoped

Registered custom merge drivers continue to reconcile their governed artifact
classes. Target-newer planning artifacts may be reconciled only through the
existing history-aware planning authority. A conflict outside those authorities
is never auto-resolved.

### D-003: preview and execution share one simulation primitive

Both dry-run and execution should call the same isolated squash-merge primitive.
Preview discards the temporary worktree before any commit or ref advancement.
Execution commits and advances the target only after that primitive reports no
unresolved conflicts. This prevents forecast/execution drift.

### D-004: preserve the successful dry-run schema

Clean dry-run output remains byte-contract compatible. A predicted conflict uses
a non-zero blocked response with a stable diagnostic code, mission branch,
target branch, conflicting paths, and remediation.

## Risks and open questions

- Git merge-driver availability must be identical in preview and execution; the
  existing ephemeral activation context is the single authority.
- The existing planning-recency tests constrain whether overlapping planning
  edits are target-preferred or blocked. Implementation must keep those tests
  green while ordinary source conflicts fail.
- Dry-run may create and remove a temporary Git worktree and loose objects. It
  must not change branch refs, tracked files, lifecycle state, or retention.
- Conflict-path diagnostics must be deterministic and repo-relative.
