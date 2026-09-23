# Branch Integration Conflict Contract

This contract defines the observable behavior of default squash integration and
its dry-run forecast for ordinary source conflicts.

## Execution

- Default squash integration does not apply a repository-wide conflict-side
  preference.
- A same-hunk conflict in ordinary source content returns failure and reports
  deterministic, repository-relative conflict paths.
- Failure occurs before the target ref advances or lifecycle cleanup begins.
- The target checkout, target ref, mission ref, work-package states, branches,
  and worktrees remain unchanged by the rejected integration.
- Disjoint changes to the same ordinary file are combined losslessly.

## Governed artifacts

- Registered custom merge drivers remain authoritative for their paths.
- PRIMARY planning artifacts continue to use the existing history-aware policy:
  the newer side wins, with the target winning equal-recency ties.
- Those governed policies do not extend to ordinary source paths.

## Dry-run

- Squash dry-run exercises the same isolated integration primitive as execution,
  scoped to the **current mission-branch tip**: it forecasts conflicts already
  present on the mission branch against the target. It does NOT first consolidate
  the lane branches the way a real merge does, so a conflict that lives only in an
  un-consolidated lane commit is not visible to the forecast. The real merge still
  stops safely on it — the forecast is a readiness signal, not a completeness
  guarantee.
- A predicted source conflict exits non-zero with
  `TARGET_BRANCH_CONTENT_CONFLICT` and includes the mission branch, target
  branch, sorted conflict paths, and remediation guidance.
- Forecasting does not advance refs, change tracked checkout bytes, emit
  lifecycle completion, or clean up branches/worktrees.
- A clean JSON forecast preserves the established successful payload key set.

## Compatibility

Explicit `merge` and `rebase` strategies are outside this change and retain
their existing behavior.
