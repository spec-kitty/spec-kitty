# Design decisions — move-task-executor-seam

- 2026-10-04: Verbatim moves only (C-003); adjacent behaviour bugs (#5447, #5468, #5151, #2555) stay out of scope so the diff is reviewable as pure relocation.
- 2026-10-04: Hop builders keep their `_MoveTaskState` parameter for now; narrowing to a frozen HopFacts value is deferred (behaviour-identity first).
