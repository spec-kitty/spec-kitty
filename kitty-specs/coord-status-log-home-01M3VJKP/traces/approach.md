# Approach: coord-status-log-home-01M3VJKP

Running log, with dated entries of 1–3 sentences each.

- 2026-10-01: Scope is #5440 only, from the red-first PR #5518. The operator asked for two separate remediation threads (#5518 and #5520), which supersedes the combined `coord-artifact-single-home` claim on the issue for this slice.
- 2026-10-01: Spiked the fix before specifying to confirm feasibility; a scratch CLI lifecycle run showed the target branch carries the status log from create onward on `main` and none with the fix.
- 2026-10-01: The new e2e lifecycle guard caught two more writers of COORD-partition byte-sets into the primary mission dir once the status log moved: `finalize-tasks` emitted `TasksStarted` / `WPCreated` / `TasksCompleted` into `planning_dir`, and `bootstrap_canonical_state`'s final `materialize` wrote a `status.json` there. Both are fixed in-mission as T007 / FR-007; `setup-plan` already emitted to the coord-aware feature dir.
