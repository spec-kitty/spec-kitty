---
title: 'Recovery: Coordination Branch Created Off main (Add/Add Conflict)'
description: 'Recovery when a coord-topology mission''s coordination branch was created off main instead of the target branch, causing an add/add merge conflict.'
doc_status: active
updated: '2026-08-15'
related:
- docs/operations/recovery-index.md
- docs/operations/start-branch-coord-divergence.md
- docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md
---

# Recovery: Coordination Branch Created Off main (Add/Add Conflict)

`spec-kitty agent action implement WP##` fails with:

```
Workspace allocation failed: cannot auto-merge the recorded planning commit
'<sha>' into lane '<lane>': the merge conflicts.
```

## Why this happens

The mission's coordination branch (`kitty/mission-<slug>`) was created off
`main` instead of off the mission's target/planning branch. `git merge-base
<coord> <target>` resolves to `main`, not to the target branch tip. Lanes
fork from coord, so when `implement` merges the recorded
`planning_commit_sha` (which lives on the target strand) into a fresh lane,
both strands have independently added `kitty-specs/<mission>/` — an add/add
conflict even when file *content* is identical. See [Coord-branch
bookkeeping: read/write split-brain
root-cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md) for why
the write-placement seam allows this drift.

## No shipped `--fix` for this case

`spec-kitty agent mission repair --mission <handle>` detects the state and
correctly REFUSES: coord and target have diverged (neither is an ancestor of
the other), so a fast-forward repair is not safe, and the command mutates
nothing. `spec-kitty doctor coordination --fix` does not apply either — it
targets stale `coordination_branch` keys and simple Gap-1 staleness, not a
coord branch built on the wrong base.

Run the diagnostic first, to confirm the diagnosis:

```bash
spec-kitty agent mission repair --mission <handle>
```

It prints a scoped diff and refuses to touch anything. Proceed to the manual
fix below.

## Manual fix (operator-approved, needs an explicit grant)

Safe when nothing has been implemented yet and the coord branch is
local-only (fully reversible). Record the old coord tip first, then reset
coord onto the target and restore the coord-owned lifecycle files.
(`spec-kitty doctor coordination` prints the exact
`.worktrees/<slug>-<mid8>-coord` path for your mission — use that instead of
hand-constructing it.)

```bash
# from the coordination worktree
git -C .worktrees/<slug>-<mid8>-coord reset --hard <target-branch>
git -C .worktrees/<slug>-<mid8>-coord checkout <old-coord-tip> -- \
  kitty-specs/<mission>/acceptance-matrix.json \
  kitty-specs/<mission>/issue-matrix.json \
  kitty-specs/<mission>/status.events.jsonl \
  kitty-specs/<mission>/status.json
git -C .worktrees/<slug>-<mid8>-coord commit -m "chore(coord): re-base coordination strand onto <target-branch> + restore lifecycle"
```

Then remove the stale lane worktree and branch, and re-run `implement`:

```bash
git worktree remove --force .worktrees/<slug>-lane-a
git branch -D kitty/mission-<slug>-lane-a
spec-kitty agent action implement WP## --mission <handle> --agent <agent>
```

Verify coord now descends from target:

```bash
git merge-base --is-ancestor <target-branch> kitty/mission-<slug>
```

`git reset --hard` and `git merge` on the coordination branch are
destructive — get explicit operator sign-off before running them, exactly as
you would for a force-push.

## Related

- [`--start-branch` coordination divergence](start-branch-coord-divergence.md) — the pr-bound sibling of this failure
- [Coordination branch stranded after a base rebase](coord-branch-base-strand.md)
- [Coord-branch bookkeeping root-cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md)
- [Recovery & Troubleshooting (agent-facing)](../guides/how-to/recovery/index.md) — implementation-crash and merge recovery
