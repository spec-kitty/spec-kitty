# Contract: accept's residual artifact commit and non-artifact coordination dirt

**Module**: `src/specify_cli/cli/commands/accept.py`
**Introduced in**: WP01 (`issue-7091-accept-coord-residual-artifact-commit`)
**Consumes**: `mission_runtime.kind_for_mission_file` (the ONE file→kind authority),
`specify_cli.coordination.commit_router.commit_for_mission`, `git.safe_commit` (unchanged)
**Referenced by**: [spec.md FR-001..FR-007](../spec.md), [plan.md DD-01..DD-04](../plan.md)
**Issue**: [#7091](https://github.com/spec-kitty/spec-kitty/issues/7091)

---

## Rule 1 — The residual commit's two legs

`accept`'s residual artifact commit commits leftover derived artifacts from BOTH checkouts
after readiness has passed: tracked-modified paths in the PRIMARY checkout
(`_primary_dirty_paths`) and tracked-modified paths in the mission's coordination worktree
(`_coord_dirty_paths`). Each leg's paths are handed, already resolved against the checkout
they physically live in, to one `commit_for_mission` call, which groups them by PARTITION
using the file→kind authority.

## Rule 2 — A coordination-leg path with no kind is not committable

A coordination-worktree residual path for which `kind_for_mission_file` returns `None` is
not a mission artifact. No commit surface owns it:

- the commit router would route it PRIMARY (an unclassified path is primary-bound, #5697);
- `safe_commit` then refuses, correctly, to stage a path under `.worktrees/` from the
  primary checkout (#2155 / #3784);
- the refusal would fail `accept` (exit 1) for a mission whose readiness had already passed.

Therefore `_run_residual_acceptance_commit` excludes such paths from the batch. It does not
commit them to either surface and does not fail on them. Classified artifacts — on either
partition — keep flowing to the router unchanged, and a PRIMARY-classified path stranded in
the coordination worktree still resolves PRIMARY and is still refused loudly: that is real
misplaced dirt, not a keep-local log.

## Rule 3 — The deferral is reported, never silent

`_note_deferred_residuals` appends one note to the `AcceptanceResult` (rendered on both the
text and `--json` lanes) naming every deferred path and the reason it is left uncommitted.

## Rule 4 — `mission-events.jsonl` stays keep-local

The mission-root `mission-events.jsonl` is the shape Rule 2 exists for: spec-kitty's own
tracked, write-only lifecycle log, appended by `spec-kitty next`. It is deliberately NOT a
`MissionArtifactKind` (#5669), and it must stay real dirt for the destructive
consolidate/accept/merge dirty gates. This contract therefore does **not**:

- add a kind for it (that would flip `is_coord_residue_churn`, silently exempting gate rows);
- widen `is_self_bookkeeping_churn` / `is_toolchain_generated_churn` (the #5669 C-002
  boundary, guarded by `tests/review/test_mission_events_dirty_survivor_5669.py`);
- weaken readiness, the residue gates, the protected-branch policy or the `.worktrees/`
  staging refusal.

## Enforcement

- `tests/specify_cli/cli/commands/test_accept_residual_partition.py`:
  `test_residual_commit_defers_coord_worktree_mission_event_log` (red-first),
  `test_residual_commit_still_refuses_a_primary_artifact_stranded_in_the_coord_worktree`
  (narrowness), `test_residual_commit_still_lands_flat_mission_event_log_on_its_own_branch`
  (flat control), `test_nonartifact_residual_paths_uses_the_one_classifier`,
  `test_deferred_residual_note_reports_the_keep_local_log`.
- `tests/review/test_mission_events_dirty_survivor_5669.py`: the C-002 guard that keeps the
  global churn owner's answer unchanged (green, untouched).
