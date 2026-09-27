---
title: 'ADR: Merge Publish-Layer Boundary'
description: 'Remote-state inspection moves to the publish layer, so local lane consolidation stays network-free and the `git fetch` preflight runs only under `--push`.'
status: Accepted
date: '2026-06-05'
---

## Context

`spec-kitty merge` is a local operation: it sequences WP branches onto a
target branch using the local git graph only. No push is implied by the
core merge operation unless the caller explicitly requests `--push`.

Prior to this ADR, `merge.py` called `_enforce_target_branch_sync_preflight`
unconditionally before any local mutation. That function performed a live
`git fetch origin` against the remote and raised `MergeError` when the local
target branch was ahead of, behind, or diverged from `origin`. This blocked
issue [#1706](https://github.com/Priivacy-ai/spec-kitty/issues/1706): a
repository where the local `main` was legitimately ahead of `origin/main`
(e.g., post-merge with unsynced remote) could not run `spec-kitty merge` at
all, even when no push was intended.

The root cause is a layer violation: push-safety is a publish concern and
belongs in the publish layer, not in the domain merge layer. The domain layer
should operate on the local git graph and remain entirely network-free.

## Decision

1. **All remote-state inspection lives in `push_preflight.py`** (publish layer).
   This module owns the `git fetch` call, the tracking-branch comparison, and
   the `is_safe_to_push` predicate.

2. **`preflight.py` is domain-only** — local git graph checks (worktree
   cleanliness, branch existence, conflict detection) with no network I/O.
   Legacy remote-state re-export names are exposed lazily for transition
   compatibility; importing `preflight.py` must not import `push_preflight.py`
   at runtime.

3. **`merge.py` imports `push_preflight` conditionally**, only inside
   `if push:` branches. The local merge path never touches `push_preflight`.

4. **`is_safe_to_push`** is the correct predicate for push-safety decisions.
   It returns `False` for `"behind"` and `"diverged"` states. Both indicate
   that remote commits are missing locally, so `merge --push` would perform
   local merge/bookkeeping mutations before a known non-fast-forward push
   rejection. The states `"ahead"`, `"in_sync"`, and `"no_tracking_branch"`
   are safe-to-push: ahead means the push will advance the remote normally;
   no tracking branch means there is no remote to conflict with.

5. **`is_safe`** is a deprecated alias on `TargetBranchSyncStatus` that
   always returns `True`. It existed to gate local merge operations on remote
   state, which was incorrect — local merges do not require remote sync.
   Callers making push decisions must migrate to `is_safe_to_push`.

## Consequences

- **Domain layer is network-free.** `spec-kitty merge` without `--push`
  performs no `git fetch` and does not block when the local target is ahead
  of or behind the remote.
- **Push-safety fires only when push is requested.** `check_push_safety()`
  in `push_preflight.py` is called only when `merge.py` is about to push to
  the remote.
- **Issue #1706 is resolved.** A repository with a local `main` ahead of
  `origin/main` can run `spec-kitty merge` without `--push` without error.
- **The `is_safe` predicate is deprecated.** It always returns `True` to
  unblock callers during the transition; callers making push decisions must
  switch to `is_safe_to_push`.

## Rejected Alternatives

1. **Add `"ahead"` and `"behind"` to the `is_safe` whitelist in
   `preflight.py`**: bandaid. This would suppress the specific error in
   #1706 but leaves the network call (`git fetch`) in the domain layer on
   every local merge invocation, regardless of whether push is intended.
   The coupling between local-merge and remote-state is the root cause; a
   whitelist change does not remove it.

2. **Guard the `_enforce_target_branch_sync_preflight` call with
   `if push:`** in `merge.py`, without relocating the module**: this corrects
   the call-site behavior but does not enforce the architectural boundary.
   The fetch logic remains importable from `preflight.py`, making it easy
   for future contributors to re-introduce the coupling accidentally.
   Relocating to `push_preflight.py` makes the boundary structural and
   enforced by the module's import identity.

## References

- Issue: [#1706](https://github.com/Priivacy-ai/spec-kitty/issues/1706)
- Publish-layer module: [`src/specify_cli/consolidation/push_preflight.py`](../../../src/specify_cli/consolidation/push_preflight.py)
- Domain-layer preflight: [`src/specify_cli/consolidation/preflight.py`](../../../src/specify_cli/consolidation/preflight.py)
- Publish preflight tests: [`tests/consolidation/test_push_preflight.py`](../../../tests/consolidation/test_push_preflight.py)
