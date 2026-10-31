# Contract: the status read root

**Mission**: lane-worktree-status-shadow-authority-01M68JFG (#6466)
**Applies to**: `specify_cli.missions._read_path_resolver.resolve_handle_to_read_path`

## Invariant

A mission's work-package lane state has exactly one authority: the **resolved status surface**.

| Mission shape | Authoritative copy |
| --- | --- |
| coordination-routed (`coord`, `lanes_with_coord`) | the coordination worktree husk (`<repo>/.worktrees/<mission>-coord/kitty-specs/<mission>/`) |
| branch-flat (`lanes`, `single_branch`) | the primary / mission-branch copy (`<repo>/kitty-specs/<mission>/`) |

A lane worktree's `kitty-specs/<mission>/` is a fork-time copy. It is never a status surface.

## Rule

`resolve_handle_to_read_path(repo_root, handle)` normalises a `repo_root` that the git worktree
registry classifies as a **lane worktree** to the repository's main worktree root before composing
any surface. Everything else is used as handed in:

| `repo_root` | Behaviour |
| --- | --- |
| primary checkout, bare repository, independent clone | unchanged (no git subprocess) |
| linked checkout outside `.worktrees/` | unchanged (no git subprocess) |
| lane worktree (registered, not `-coord`) | re-anchored to the main worktree root |
| coordination worktree (registered, `-coord`) | unchanged — it *is* the authority on a coordination-routed mission |
| husk (under `.worktrees/`, unregistered) | unchanged |
| worktree registry unreadable | unchanged; the existing surfaces keep failing closed |

Classification is `coordination/surface_resolver.classify_worktree_topology` (C-SEAM-1): the
registry disposes, path shape never decides. A relative root is judged on its resolved path.

## Non-goals

- No newest-timestamp-wins rule, and no copying of `status.json` between checkouts: `status.json`
  stays a derived snapshot regenerated from the event log (`status/rematerialize.py`).
- No transition guard is relaxed. The `--force` demand this contract removes was caused by a stale
  read, not by a genuine guard.

## Proof

`tests/specify_cli/missions/test_lane_worktree_status_shadow.py` — nine tests covering the
authoritative read, the lane-rooted read (both the action-context resolver and the seam), the
coordination boundary, the independent clone, the husk, an unreadable registry, the relative root,
and the no-registry-call common path. Red-first: the lane-rooted legs fail without the rule.
