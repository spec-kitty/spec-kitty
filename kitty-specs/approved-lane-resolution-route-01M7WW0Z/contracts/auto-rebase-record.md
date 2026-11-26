# Contract: auto-rebase record

- **Ref**: `refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`. Its target is `<merge-sha>`.
- **Write**: `attempt_auto_rebase` writes it after the merge commit is created and before it returns. It is written for clean and auto-resolved merges alike. A failure to write the ref fails the auto-rebase, which is reported as a halt and undoes the merge. Residual: if that undo is itself refused (guarded reset), the merge stays without a record and is judged as a hand merge (fail closed).
- **Read (FR-004 only)**: a merge is tool-made exactly when this ref exists and resolves to the same SHA.
- **Delete**:
  - The rollback deletes it after it restores the lane from `lane_rebase_moves`.
  - Lane cleanup deletes every ref under `refs/spec-kitty/auto-rebase/<lane-branch>/` when it removes the lane branch.
- **Never**: the reconciliation gate never reads it. It never exempts a path, blob or commit from attribution.
