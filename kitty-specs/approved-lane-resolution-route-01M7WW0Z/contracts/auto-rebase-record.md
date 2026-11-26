# Contract: auto-rebase record

- **Ref**: `refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`. Its target is `<merge-sha>`.
- **Write**: `attempt_auto_rebase` writes it after the merge commit is created and before it returns. It is written for clean and auto-resolved merges alike. A failure to write the ref fails the auto-rebase, which is reported as a halt and undoes the merge. Residual: if that undo is itself refused (guarded reset), the merge stays without a record and is judged as a hand merge (fail closed).
- **Read (FR-004 only)**: a merge is tool-made exactly when this ref exists and resolves to the same SHA. The claim skips a tool-made merge only when its merge attributes match the pre-run target tip's and each of its own non-bookkeeping paths kept a parent's or the pre-run target tip's `(mode, oid)` entry (review fold, PR #7886, finding A2). Any other recorded resolution is refused at claim time, and a probe error refuses.
- **Merge guard (before write)**: `attempt_auto_rebase` runs the merge attribute guard in the lane checkout, with the target branch tip as the committed attributes source, before it merges. A refusal halts with `nothing was merged` and writes no record (review fold, finding I1).
- **Delete**:
  - The rollback deletes it after it restores the lane from `lane_rebase_moves`.
  - Lane cleanup deletes every ref under `refs/spec-kitty/auto-rebase/<lane-branch>/` when it removes the lane branch.
- **Never**: the reconciliation gate never reads it. It never exempts a path, blob or commit from attribution.
