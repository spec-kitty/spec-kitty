---
title: 'Recovery: consolidate, review or implement refuses after an upgrade mid-Mission'
description: "Recovery when spec-kitty consolidate, review or implement refuses on .kittify/metadata.yaml after an upgrade run while a Mission had live lanes."
doc_status: active
type: how-to
audience: docs/context/audience/internal/maintainer.md
updated: '2026-10-04'
related:
- docs/operations/recovery-index.md
- docs/operations/stale-lane-seed.md
- docs/adr/4.x/2026-10-04-2-upgrade-writes-project-global-state-once.md
---

# Recovery: consolidate, review or implement refuses after an upgrade mid-Mission

You ran `spec-kitty upgrade` on 4.0.0rc5 or earlier while a Mission had live lanes or a
coordination worktree. Now `consolidate`, a review start or an implement resume refuses on
`.kittify/metadata.yaml` (or `.gitattributes`), a file you never edited. This page gets the
Mission moving again. It is tracked as [#5457](https://github.com/spec-kitty/spec-kitty/issues/5457).

## Symptoms

Any one of these three refusals:

- `spec-kitty consolidate` exits 1:
  `Lane lane-b is stale: overlapping files ['.gitattributes', '.kittify/metadata.yaml']`.
  The printed `git merge kitty/mission-<slug>` remedy reports "Already up to date" and the
  next run refuses again.
- `spec-kitty consolidate` (and `--resume`) exits 1 with `TARGET_BRANCH_CONTENT_CONFLICT`
  and `conflicting_path: .kittify/metadata.yaml` when squashing into the target branch.
- `spec-kitty agent action review WP02` (or an implement resume) exits 1 with
  `LANE_AUTO_REBASE_FAILED: no classifier rule matched .../.worktrees/<slug>-lane-b/.kittify/metadata.yaml`.

## Fix

1. Install the fixed CLI (the release that carries #5457, or a checkout of it).
2. Re-run the command that refused, for example:

   ```bash
   spec-kitty consolidate --mission <slug>
   ```

   or the review or implement command that failed. No other step is needed.

The lanes and the coordination branch still carry the divergent upgrade commits from the
earlier run. The fixed CLI resolves them at the next integration without your help:

- the stale check no longer counts `.kittify/metadata.yaml`, nor any overlap whose content is
  identical on the lane and the Mission branch (the duplicated `.gitattributes` line);
- the merges that `consolidate` and implement perform resolve a conflict confined to
  `.kittify/metadata.yaml` to the receiving side (the Mission branch, the target, or the
  dependent lane);
- the lane sync after a coordination commit takes the incoming coordination or Mission copy
  (rule `R-PRIMARY-OWNED-BOOKKEEPING`).

Going forward, `spec-kitty upgrade` writes project-global state once, in the repository root
checkout, and skips lane, Mission and coordination worktrees. A lane keeps its pre-upgrade
`.gitignore` and `.gitattributes` until it integrates.

## What not to do

- Do not run `git reset --hard` on a lane or the Mission branch. It discards committed work.
- Do not rewrite history (rebase, amend or filter the upgrade commits). The fixed CLI does not
  need it, and a rewrite can strand lane work tips.
- Do not hand-edit `.kittify/metadata.yaml`. It is generated, and its records are written by
  `spec-kitty upgrade`.
- Do not follow the printed `git merge kitty/mission-<slug>` remedy for this refusal. It is a
  no-op here.

## When you will still see a refusal

The fix covers generated bookkeeping only. A genuine overlap on a file a work package edits,
such as `.gitattributes` content that differs between lanes, `.gitignore`, `.kittify/config.yaml`
or source files, still stops `consolidate`, and resolving it by hand is correct. For that
case the printed stale remedy can be a no-op after the in-run rollback. Follow-up
[#5711](https://github.com/spec-kitty/spec-kitty/issues/5711) tracks the remedy wording.

## See also

- [Recovery guides](recovery-index.md)
- [Stale lane seed after re-finalizing tasks](stale-lane-seed.md)
- [ADR 2026-10-04-2: upgrade writes project-global state once](../adr/4.x/2026-10-04-2-upgrade-writes-project-global-state-once.md)
- [Branch-target routing](../architecture/branch-target-routing.md)
