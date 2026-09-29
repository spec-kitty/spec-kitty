# Contract — the single consolidation rollback authority

```python
# consolidation/rollback.py
def capture_pre_mutation_snapshot(repo_root: Path, state: ConsolidationState, lanes_manifest: LanesManifest, *, coord_ref: str | None, is_resume: bool = False) -> dict[str, str]: ...
def begin_attempt(repo_root: Path, state: ConsolidationState) -> None: ...   # per-attempt restore_targets
def movable_branch_tips(repo_root: Path, state: ConsolidationState) -> dict[str, str | None]: ...   # a phase's entry tips
def record_post_mutation_tips(repo_root: Path, state: ConsolidationState, *, entry_tips: Mapping[str, str | None] | None = None) -> None: ...
def rollback_to_snapshot(repo_root: Path, state: ConsolidationState, *, target_branch: str) -> RollbackReport: ...

# git/ref_advance.py (extended, default unchanged)
def restore_branch_ref(repo_root, branch, restored_sha, *, expected_current_sha, resync_checkouts: bool = False) -> None: ...
class RefResyncError(RefAdvanceError): ...   # the CAS write succeeded; a checkout resync failed
```

Guarantees:
1. Never moves a branch that is not in `state.pre_mutation_refs`.
2. Never moves a branch whose current commit ≠ this attempt's recorded post-mutation tip (D3); reports it NOT_RESTORED. A target/mission/coordination branch that moved with no recorded post tip (interrupted phase) is NOT_RESTORED too (never reported untouched; `--abort` keeps the record). Each branch is restored to its per-attempt restore target: the snapshot when the attempt started from the snapshot or from consolidation's own previous post tip, otherwise the attempt-start tip (an operator's change between attempts is kept).
2a. Lane branches (`state.snapshot_lane_branches`) are report-only: never recorded, never restored (UNCHANGED_BY_RUN / ALREADY_AT_SNAPSHOT); they never block a full restore.
2b. A phase records a post tip only for a target/mission/coordination branch whose tip changed during that phase; a CAS refusal records nothing, a `RefResyncError` (our write succeeded) is recorded. Residual: a foreign commit inside the same phase, after our own advance of that branch, is recorded as ours.
3. Never rolls back when `reconciliation_passed_target_sha` == current target tip (FR-011). A missing snapshotted branch does not block the rest: a missing lane is LANE_MISSING with a `git branch <b> <sha>` hint; a missing target/mission/coordination branch is NOT_RESTORED with the same hint.
4. Resyncs every worktree with a restored branch checked out, refusing (NOT_RESTORED) when that worktree is dirty — no new raw `reset --hard` outside `git/ref_advance.py`.
5. Clears bookkeeping only after a full restore; is idempotent (a second call reports ALREADY_AT_SNAPSHOT everywhere).
6. Entries captured live when an older record was resumed (`state.resume_seeded_refs`) are reported as "snapshot taken when this record was resumed", not pre-consolidation.

Callers (exhaustive, AST-pinned): the driver wrapper around `_phase_reconcile_before_teardown` (which first resets a PASS anchor written by THIS call, so FR-011 only protects landings verified by an EARLIER attempt); `_dispatch_abort`.
