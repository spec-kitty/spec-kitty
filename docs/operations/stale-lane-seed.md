---
title: 'Recovery: Stale Lane Seed After Re-Finalizing Tasks'
description: 'Recovery for a post-finalize planning commit that stale-seeds a lane, plus the related sparse-checkout false-positive and sync-fan-out hang seen at the same step.'
doc_status: active
updated: '2026-08-15'
related:
- docs/operations/recovery-index.md
- docs/operations/coord-worktree-missing.md
- docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md
---

# Recovery: Stale Lane Seed After Re-Finalizing Tasks

`spec-kitty agent action implement WP##` fails with:

```
Workspace allocation failed: cannot auto-merge the recorded planning commit
'<sha>' into lane '<lane>': the merge conflicts.
```

## Why this happens

You committed MORE planning commits (for example, a post-tasks-squad fold)
*after* `finalize-tasks` already created the coord/lane branches. `implement`
seeds the lane from finalize's OLD commit, so the new planning commit and the
lane's seed diverge.

## No shipped `--fix` for this case — and one to avoid

`spec-kitty doctor coordination --fix` looks like the obvious candidate but
is the wrong tool here: it walks and rewrites `meta.json` for **every**
mission under `kitty-specs/`, not just the one you are fixing, and it only
repairs a coord branch that was never created — not one that is valid but
stale-seeded. Reach for it only when you intend a repo-wide sweep; if you run
it by mistake, restore the unrelated missions with
`git checkout -- kitty-specs/`.

## Manual fix: flatten this mission only

(`spec-kitty doctor coordination` prints the exact
`.worktrees/<mission>-<mid8>-coord` path for your mission — use that instead
of hand-constructing it.)

```bash
git worktree remove .worktrees/<mission>-lane-a --force
git worktree remove .worktrees/<mission>-<mid8>-coord --force
git branch -D kitty/mission-<mission>-lane-a kitty/mission-<mission>
```

Edit `kitty-specs/<mission>/meta.json` to drop coordination, then commit:

```json
{
  "coordination_branch": null,
  "topology": "lanes"
}
```

Re-bootstrap status on the flattened topology and re-prepare the lanes:

```bash
spec-kitty agent mission finalize-tasks --mission <handle>
spec-kitty agent action implement WP## --mission <handle> --agent <agent>
```

Better: don't re-run `finalize-tasks` after a post-tasks fold — fold squad
findings **before** the mutating finalize call, or accept the flatten dance
above.

## Two related implement-time false positives

**False sparse-checkout guard.** `implement` refuses and points at
`spec-kitty doctor sparse-checkout --fix`, even when
`git config core.sparseCheckout` is already `false` and 100% of files are
present — a stale `.git/info/sparse-checkout` leftover. `doctor
sparse-checkout --fix` itself needs an interactive TTY and fails in a
headless/CI shell. Skip it and pass the escape hatch instead — this is a
genuine false positive, not a real sparse-checkout state:

```bash
spec-kitty agent action implement WP## --mission <handle> --agent <agent> --allow-sparse-checkout
```

**Sync-fan-out hang.** `implement` / `move-task` can hang on the SaaS sync
tail after the local claim has already persisted. Wrap the call:

```bash
SPEC_KITTY_SYNC_DISABLE=1 spec-kitty agent action implement WP## --mission <handle> --agent <agent>
```

The worktree and claim are already done by the time it hangs; disabling sync
just lets the command return.

## Related

- [Coordination branch declared but worktree missing](coord-worktree-missing.md)
- [Coord-branch bookkeeping root-cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md)
- [Recovery & Troubleshooting (agent-facing)](../guides/how-to/recovery/index.md) — implementation-crash and merge recovery
