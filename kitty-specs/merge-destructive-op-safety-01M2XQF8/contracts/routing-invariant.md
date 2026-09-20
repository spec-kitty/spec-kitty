# Contract — Unification Routing Invariant (NFR-006 / IC-5)

A non-vacuous architectural gate (DIRECTIVE_043) proving the defect class is closed
by construction, not by reviewer goodwill.

## Assertions

1. **Destructive commands route through the guarded seam.** Outside an
   explicitly-rationalized allowlist, every `git reset --hard`,
   `git worktree remove ... --force` (user-facing), and `git merge --abort` on
   `repo_root` must go through the WP01 guard / `guarded_worktree_remove`.
   `guarded_worktree_remove` is the removal chokepoint — NOT `core/vcs/git.py
   remove_workspace` (a dead adapter, allowlisted as unused).
2. **No new parallel dirty predicate.** The guard reuses
   `ref_advance._dirty_entries`; the test asserts no additional module-level
   `git status --porcelain`-parsing "is dirty" predicate was added by this mission.
3. **Self-mutation test.** A companion test deliberately routes a destructive op
   around the seam and asserts the gate goes RED (non-vacuity).

## Allowlist (built from a LIVE census — see WP05 T018)

Do NOT hand-copy a baseline; the census adjudicates every site with an inline
rationale. Provisional classification (verify at implement time):

- `reset --hard` allow: `git/ref_advance.py` (ref-advance resync),
  `merge/git_probes.py` (guarded by WP03), `doctrine/sources/git_source.py`
  (doctrine clone dir, not repo_root), `lanes/worktree_allocator.py` (alloc
  rollback to a pre-loop ref).
- `worktree remove --force` routed (in-scope): `merge/executor.py` lane cleanup,
  `coordination/workspace.py` teardown + stale-prune, `orchestrator_api/commands.py`.
- `worktree remove --force` allow: `merge/ordering.py`, `lanes/merge.py`,
  `review/baseline.py` (detached temp), `merge/workspace.py` (scratch, C-006),
  `mission_type.py --discard` (intentional), `core/vcs/git.py remove_workspace`
  (unused adapter), `lanes/worktree_allocator.py` fresh-worktree removal (adjudicate:
  tree known-clean → allow, or route).
- `merge --abort` on `repo_root`: gated by WP04.

The allowlist may only shrink after the census freezes it.

## Rationale

The surface lens found ~9 forked dirty predicates and 3 unguarded force-remove
sites (executor, coord teardown, orchestrator mirror). Without this gate a future
change re-forks the authority; with it, a new ungated destructive op fails CI.
