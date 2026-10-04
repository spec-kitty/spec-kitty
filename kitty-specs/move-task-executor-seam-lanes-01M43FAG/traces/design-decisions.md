# Design decisions — move-task-executor-seam

- 2026-10-04: Verbatim moves only (C-003); adjacent behaviour bugs (#5447, #5468, #5151, #2555) stay out of scope so the diff is reviewable as pure relocation.
- 2026-10-04: Hop builders keep their `_MoveTaskState` parameter for now; narrowing to a frozen HopFacts value is deferred (behaviour-identity first).

- 2026-10-04 WP02: `emit_runtime_annotation` lives in coordination/status_transition.py; plain emitter lazy-imported from `specify_cli.status` so existing patches intercept (no test repointing needed). mark-status passes auto_commit=False and still appends applied ids only when owned is set.
