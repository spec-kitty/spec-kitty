# Contract — the single consolidation rollback authority

```python
# consolidation/rollback.py
def capture_pre_mutation_snapshot(repo_root: Path, state: ConsolidationState, lanes_manifest: LanesManifest, *, coord_ref: str | None) -> dict[str, str]: ...
def begin_attempt(repo_root: Path, state: ConsolidationState) -> None: ...   # per-attempt restore_targets
def record_post_mutation_tips(repo_root: Path, state: ConsolidationState) -> None: ...
def rollback_to_snapshot(repo_root: Path, state: ConsolidationState, *, target_branch: str) -> RollbackReport: ...

# git/ref_advance.py (extended, default unchanged)
def restore_branch_ref(repo_root, branch, restored_sha, *, expected_current_sha, resync_checkouts: bool = False) -> None: ...
```

Guarantees:
1. Never moves a branch that is not in `state.pre_mutation_refs`.
2. Never moves a branch whose current commit ≠ this attempt's recorded post-mutation tip (D3); reports it NOT_RESTORED. A branch with no recorded post tip is UNCHANGED_BY_RUN (never restored, does not block a full restore). Each branch is restored to its per-attempt restore target: the snapshot when the attempt started from the snapshot or from consolidation's own previous post tip, otherwise the attempt-start tip (an operator's change between attempts is kept).
3. Never rolls back when `reconciliation_passed_target_sha` == current target tip, or when a snapshotted branch is missing (FR-011).
4. Resyncs every worktree with a restored branch checked out, refusing (NOT_RESTORED) when that worktree is dirty — no new raw `reset --hard` outside `git/ref_advance.py`.
5. Clears bookkeeping only after a full restore; is idempotent (a second call reports ALREADY_AT_SNAPSHOT everywhere).

Callers (exhaustive, AST-pinned): the driver wrapper around `_phase_reconcile_before_teardown` (which first resets a PASS anchor written by THIS call, so FR-011 only protects landings verified by an EARLIER attempt); `_dispatch_abort`.
