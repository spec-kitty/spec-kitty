---
title: 'Recovery: Coordination Branch Stranded After a Base Rebase'
description: 'Recovery when a coord-topology mission was created on an old base and the working branch was later rebased, leaving lanes forking from a stale coord branch.'
doc_status: active
updated: '2026-08-15'
related:
- docs/operations/recovery-index.md
- docs/operations/coord-off-main-addadd.md
- docs/plans/engineering-notes/coord-splitbrain-rootcause.md
---

# Recovery: Coordination Branch Stranded After a Base Rebase

`spec-kitty agent action implement WP##` creates a lane worktree whose HEAD is
on the wrong (old) base — a load-bearing invariant (for example a golden
count) differs from what the target base expects, and
`git merge-base --is-ancestor <intended-base> <lane-HEAD>` answers no.

## Why this happens

The mission was created (per `meta.json` `created_at`) on an old base, which
established the coordination branch (`kitty/mission-<slug>`) there. The
working/planning branch (`target_branch`) was later rebased onto a newer
base, but the coordination branch is **never** rebased along with it — it
stays stranded on the creation-time base. Lanes fork from coord, so every new
lane inherits the stale code.

## Lead with the diagnostic — the shipped `--fix` only auto-heals the simple case

```bash
spec-kitty doctor coordination --check-staleness
```

This reports Gap-1 coord-branch-vs-`target_branch` staleness. `--fix`
attempts a fast-forward, but only when the coord branch is a strict ancestor
of the target, the coord worktree is clean, and that worktree has the
coordination branch of this repository checked out:

```bash
spec-kitty doctor coordination --fix
```

A genuine post-rebase strand is a **divergence**, not simple staleness — the
coord tip is not an ancestor of the new base at all, so `--fix` correctly
fails loud with a unified diff and mutates nothing rather than guessing
which side wins. Manual reset is required.

A coord worktree on some other branch, on a detached HEAD, or belonging to a
different repository is refused the same way (`COORDINATION_BRANCH_STALE_FIX_BLOCKED`),
before anything is touched. If a fast-forward runs but the coordination branch
still does not match the target afterwards, `--fix` reports
`COORDINATION_BRANCH_STALE_FIX_POSTCONDITION_FAILED` instead of claiming success.

`--fix` also sweeps every mission under `kitty-specs/`; scope your review to
the mission you care about, or restore unrelated missions with
`git checkout -- kitty-specs/` if you run it broadly by mistake.

## Manual fix (operator-approved)

Safe when the divergence is a clean base-rebase (the working/planning branch
moved to a newer base, nothing has published off the stale coord tip) and the
discarded coord commits are re-bootstrappable status-seed events — step 4
below re-creates them. Not safe if the coord branch carries commits that
exist nowhere else.

1. Clean the failed-claim residue on the working checkout:

   ```bash
   git checkout -- kitty-specs/<mission>/meta.json kitty-specs/<mission>/status.events.jsonl kitty-specs/<mission>/tasks/WP##*.md
   rm -f kitty-specs/<mission>/status.json
   ```

2. Remove the stale lane worktree and branch:

   ```bash
   git worktree remove --force .worktrees/<slug>-lane-a
   git branch -D kitty/mission-<slug>-lane-a
   ```

3. Reset the coordination branch onto the (now-rebased) target branch, from
   inside the coord worktree using an absolute path. (`spec-kitty doctor
   coordination` prints the exact `.worktrees/<slug>-<mid8>-coord` path for
   your mission — use that instead of hand-constructing it.)

   ```bash
   git -C <repo-root>/.worktrees/<slug>-<mid8>-coord reset --hard <target_branch>
   ```

   `git reset --hard` is a destructive operation — get explicit operator
   sign-off before running it, the same as a force-push.

4. Re-seed status. The WP-`planned` seed events live only on the stale coord
   branch (as `chore: status transition WP##` commits), and the reset in
   step 3 discards them. Re-run finalize to re-bootstrap:

   ```bash
   spec-kitty agent mission finalize-tasks --mission <handle> --json
   ```

   Verify the board shows the expected number of `planned` WPs.

5. Re-claim and verify the lane HEAD is on the intended base:

   ```bash
   spec-kitty agent action implement WP## --mission <handle> --agent <agent>
   git merge-base --is-ancestor <intended-base> <lane-HEAD>
   ```

## Consequence for parity/golden checks

The lane HEAD is `<intended-base> + planning/status commits` — source-identical
for `src/` but not byte-identical to the intended base. A harness that
asserts `HEAD == base` must pin to the lane HEAD via `git rev-parse HEAD`, not
the literal intended-base SHA.

## Related

- [Coordination branch created off main (add/add)](coord-off-main-addadd.md)
- [Coord-branch bookkeeping root-cause](../plans/engineering-notes/coord-splitbrain-rootcause.md)
- [Recovery & Troubleshooting (agent-facing)](../guides/how-to/recovery/index.md) — implementation-crash and merge recovery
