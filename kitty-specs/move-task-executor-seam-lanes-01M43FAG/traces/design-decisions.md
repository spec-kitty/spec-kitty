# Design decisions — move-task-executor-seam

- 2026-10-04: Verbatim moves only (C-003); adjacent behaviour bugs (#5447, #5468, #5151, #2555) stay out of scope so the diff is reviewable as pure relocation.
- 2026-10-04: Hop builders keep their `_MoveTaskState` parameter for now; narrowing to a frozen HopFacts value is deferred (behaviour-identity first).

- 2026-10-04 WP02: `emit_runtime_annotation` lives in coordination/status_transition.py; plain emitter lazy-imported from `specify_cli.status` so existing patches intercept (no test repointing needed). mark-status passes auto_commit=False and still appends applied ids only when owned is set.

- 2026-10-04 WP04: Retired `test_fixture_provenance_is_machine_emitted_base_commit` (pinned a base-commit hash, not behaviour; decision coverage kept in the replay + non-empty-scope guard tests) and the spent capture harness `tests/review/fixtures/parity/_capture.py` (no importers). Added `test_move_task_patch_targets_live.py`: AST gate that every `patch`/`monkeypatch` target on the four move-task modules is called as a bare Name by that module (the `_tasks.` bridge does not count for them). Baseline: 129 targets scanned, 0 dead, 0 unresolvable.

## SC-004 follow-up ticket (draft, orchestrator files at closeout)

**Title:** Extend seam-pin and patch-liveness gate to the other `tasks_*` seams (#2561)

**Body:** The move-task de-god slices (#5629) split `tasks_move_task` into gates/hops/executor modules and added (a) contract-worded seam pins in `test_tasks_move_task_seams.py` and (b) `test_move_task_patch_targets_live.py`, an AST gate failing when a `patch.object`/`monkeypatch.setattr`/string `patch(...)` targets a name its module never calls as a bare Name (a dead intercept: green test, real function runs). The other `tasks_*` seams (the remaining `agent/tasks_*.py` modules reached through the `_tasks.` bridge, and `tasks` itself) have no equivalent gate, so a verbatim move there can silently strand patches the same way. Scope: generalise the gate's module set (including the `_tasks.<name>` rule for patches on `tasks`), add a negative control per seam, record an unresolvable-target baseline, and add contract-worded seam pins where missing. Acceptance: a deliberately mis-pointed patch on any `tasks_*` module fails the gate; no allowlist entries without a reason. Refs #2561, #5629.
