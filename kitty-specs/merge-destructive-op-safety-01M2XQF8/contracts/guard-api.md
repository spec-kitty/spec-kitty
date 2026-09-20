# Contract — Refuse-Before-Destroy Guard API

Frozen shared contract for IC-1 (must be stable before IC-2–IC-4 branch).

## Module: `src/specify_cli/git/destructive_guard.py` (proposed)

git-plumbing purity: no `specify_cli` import; the caller injects the churn
classifier. Names are indicative; the brownfield scout confirms final placement.

```python
class DestructiveOpRefused(Exception):
    error_code: str            # MERGE_UNSAFE_PRIMARY_OFF_TARGET | *_PRIMARY_DIRTY | *_WORKTREE_DIRTY
    worktree_path: Path | None
    current_branch: str | None
    expected_branch: str | None
    dirty_entries: list[str]
    remediation: str           # actionable, includes the --resume note

def assert_checkout_on_target(repo_root: Path, expected_branch: str, *, env=None) -> None:
    """Raise DestructiveOpRefused(MERGE_UNSAFE_PRIMARY_OFF_TARGET) if HEAD != expected_branch.
    Reuses the rev-parse logic of merge/preflight._enforce_planning_artifact_target_branch."""

def assert_worktree_clean(
    worktree: Path, *, new_sha: str | None = None,
    is_residue,                # injected: coordination.coherence.is_toolchain_generated_churn (partial w/ mission_slug)
    env=None,
    error_code: str = MERGE_UNSAFE_WORKTREE_DIRTY,  # caller picks the refusal vocabulary
) -> None:
    """Raise DestructiveOpRefused(error_code) if ref_advance._dirty_entries(...) is non-empty.
    Default MERGE_UNSAFE_WORKTREE_DIRTY (lane/coord); the merge preflight passes
    MERGE_UNSAFE_PRIMARY_DIRTY for the primary checkout (US1 AC2 / FR-002)."""

def guarded_worktree_remove(
    worktree: Path, *, retain: bool, is_residue, env=None,
) -> "RemoveResult":            # removed | retained_dirty
    """The SHARED removal chokepoint every live destroy site routes through.
    Runs assert_worktree_clean unless `retain`; on clean (or retained-and-kept)
    performs the inline `git worktree remove --force`; on retain+dirty KEEPS the
    worktree and reports retained_dirty. NOT the dead core/vcs/git.py remove_workspace."""
```

## Consumption

- **IC-2 (#4752)**: the merge preflight (in the OUTER `_run_lane_based_merge`, BEFORE
  `_phase_merge_lanes` — before any mutation) calls `assert_checkout_on_target(main_repo, target)`
  then `assert_worktree_clean(main_repo, ...)`. On the safe path
  `_refresh_primary_checkout_after_merge` runs unchanged; on refusal nothing mutates.
- **IC-3 (#4753)**: the merge preflight pre-checks every lane + coord worktree
  (`assert_worktree_clean`, retention-aware) so refusal is pre-mutation; the live
  destroy sites (executor lane cleanup, coordination teardown + stale-prune,
  orchestrator cleanup) all route through `guarded_worktree_remove`. The dead
  `core/vcs/git.py remove_workspace` is NOT touched.
- **IC-4 (#4754)**: `abort_git_merge` gates on active spec-kitty merge state
  (`has_active_merge`) + scopes to the merge workspace (`get_merge_workspace_path`),
  never `repo_root` (does not need the guard).

## Guarantees

- Idempotent, side-effect-free on the safe path.
- Raises only `DestructiveOpRefused` for unsafe conditions (never overloads
  `SafeCommitHeadMismatch` — C-002).
- Residue recognized by the injected classifier never triggers a raise (NFR-003).
