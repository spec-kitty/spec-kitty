---
title: 'ADR: a destructive git operation discharges named proof obligations'
description: 'The eight things a command must prove before it removes a worktree or deletes a branch, and the guard entry that enforces them for doctor workspaces --prune.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-06'
---

# A destructive git operation discharges named proof obligations

**Status:** Proposed (2026-11-06). Operator rulings of 2026-11-06 on #7264 (ADR rather than a doc;
local refs only for reflog reachability; one guard entry for the prune).

**Date:** 2026-11-06

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #7264: write down the proof obligations of a safe destructive git operation.
- #7173 / #7196: `spec-kitty doctor workspaces --prune`, the first command that removes a worktree
  and deletes its branch on its own judgement.
- #7212 (PR #7239), #7211 (PR #7237), #7214 (PR #7240): three safety holes found in that prune
  within days, each fixed in its own PR. This ADR and the combined PR supersede them.
- Earlier guard decisions this builds on: the refuse-before-destroy guard (#4752 / #4753), the
  compare-and-swap ref primitives (#4996, #5570), the landed intent (#7173).

## Context and Problem Statement

`doctor workspaces --prune` removes a landed worktree and deletes its local branch. Three follow-ups
landed against it in a week: the branch delete was not compare-and-swap, commits that only a reflog
held were lost when the prune destroyed that reflog, and the landing could only be proved against
`origin`, never against the remote a fork clone actually lands on. Each was a missing proof, found
one at a time, because the contract "what must be true before this command may destroy something"
was never written down. Lane teardown and consolidate cleanup destroy the same kinds of things and
face the same questions.

## Considered Options

1. **Keep fixing holes one PR at a time.** Each fix is small; the contract stays implicit, so the next
   destructive command repeats the same mistakes.
2. **A doc that lists the obligations.** Explains the contract but binds nothing.
3. **An ADR that names the obligations, and one guard entry that enforces them** (chosen).

## Decision

A command may remove a worktree or delete a branch only after it discharges every obligation below.
`specify_cli.git.destructive_guard` is the one place that enforces them; a caller supplies the
evidence the guard cannot compute itself (a residue classifier, a process probe, an absorption
proof), so the guard stays free of application imports (C-005). For the prune this is
`guarded_landed_removal`; `workspace/landed_worktrees.py` calls nothing else destructive.

| # | Obligation | What the guard checks for the prune | Refusal |
|---|------------|-------------------------------------|---------|
| O1 | **Clean tree.** Nothing uncommitted or untracked would be destroyed. | `assert_worktree_clean(..., treat_untracked_as_dirty=True)` with the caller's residue context. | `MERGE_UNSAFE_WORKTREE_DIRTY` |
| O2 | **No live process.** No process is standing in the worktree. | The caller's probe answers for the worktree; "cannot tell" is a refusal, not a pass. | `PROCESS_IN_WORKTREE`, `PROCESS_PROOF_UNAVAILABLE` |
| O3 | **Landed against a named remote.** Every commit of the tip is on `refs/remotes/<remote>/<primary>` for a remote the repository configures: reachable from it, or absorbed by it (a `merge-tree` no-op, which covers squash landings). | The landing ref must sit under `refs/remotes/<remote>/` for a configured `<remote>` and resolve; the caller's absorption proof is re-run on that ref at the proven tip. Nothing is fetched. | `LANDING_REF_UNNAMED`, `NOT_LANDED_ON_NAMED_REMOTE` |
| O4 | **Reflog-only commits are kept.** A commit that only the worktree `HEAD` reflog or the branch reflog still reaches would be lost when those reflogs go. | Before anything is removed, each such commit that no local ref reaches (`refs/heads`, `refs/tags`, `refs/spec-kitty`; a remote-tracking ref never vouches) is recorded under `refs/spec-kitty/discarded/reflog/<sha>`, create-only. A record that cannot be written refuses the removal. | `DESTRUCTIVE_OP_ONLY_COPY` |
| O5 | **Compare-and-swap deletes.** A ref is deleted only while it still holds the commit the proof was about, and the worktree is removed only while its `HEAD` was still that commit one step earlier. | The branch delete is `git update-ref --no-deref -d <ref> <tip>`, so a branch that moves while the delete runs is kept, and a symbolic branch never takes its target with it. git has no compare-and-swap for a worktree, so its `HEAD` and branch are re-read twice: before the other checks, and again as the last step before the removal. | `WORKTREE_TIP_MOVED`, `BRANCH_TIP_MOVED`, `BRANCH_CHECKED_OUT` |
| O6 | **Rebase-merged SHAs count as landed only by proof.** The pre-rebase commits of a rebase landing are reachable from nothing, yet their content is on the primary. | A reflog-only commit is left unrecorded only when every commit that would be lost with it replays onto the landing ref as a verbatim no-op (`git merge-tree --write-tree --merge-base <c>^ <landing-ref> <c>` returns the landing ref's own tree). A merge, a root or an empty commit, an empty range and any git error are no proof. `git cherry` is not used: its patch-id ignores whitespace, which can change what a program does. | (never refuses; it records) |
| O7 | **Never `--force`.** git's own refusals (a locked worktree, one it still finds dirty) are a last net, not something to override. | The removal is `git worktree remove` without `--force`, hard-coded. | `WORKTREE_REMOVE_REFUSED_BY_GIT` |
| O8 | **A recreate hint.** Everything destroyed comes back with one printed command. | The result carries the command (`git branch <b> <tip>`, or `git worktree add [--detach] <path> <ref>`), plus the kept refs. | (always present) |

Two further rules come with the table:

- **The local branch the landing is proven against is never deleted.** The guard derives it from the
  landing ref (`refs/remotes/<remote>/<primary>` → `<primary>`) and keeps it (`BRANCH_IS_PRIMARY`).
- **Order.** O3 and O5's first re-read, then O2, then O1, then the O4 records, then O5's second
  re-read, then the removal (O7), then the branch delete (O5). git refuses to delete a branch a worktree has checked out, so the
  branch delete must follow the removal; a refusal after the removal is reported, never raised, so the
  caller still prints what was removed and how to get it back.

### Why not the others

Option 1 is how we got three PRs. Option 2 would describe the contract, but the next destructive
command would still have to re-implement it, and the review that misses an obligation would not be
caught by anything.

### Scope

This ADR binds `doctor workspaces --prune` now. Lane teardown (`DESTROYED_LANE`,
`LANE_WORK_TIP_UNKNOWN`) and consolidate cleanup already discharge several obligations through their
own guards; moving them onto the same entry is follow-up work (listed as deferred in the PR that
introduced this ADR; no issue is filed yet).

## Consequences

**Positive.**
- One table answers "may this command destroy that?"; a review checks a change against it.
- Each obligation has a red-first test against the guard entry, so a regression names the obligation
  it broke.
- A fork clone can prune: `--remote upstream` names the proving remote (#7214).

**Negative.**
- The guard re-runs the process probe and the absorption proof right before it destroys, after the
  prune's own re-assessment did the same: one extra `/proc` scan and one `merge-tree` per removed
  worktree.
- O4 counts only local refs, so a reflog-only commit that only a remote-tracking ref reaches, and that
  the O6 proof cannot show on the landing ref, gets a kept ref of its own. That errs toward keeping.
- `refs/spec-kitty/discarded/` grows by one ref per kept commit; nothing prunes it yet.
- Two ref sets count as "keeping" a commit. O4 counts local branches, tags and `refs/spec-kitty/*`; the
  older tip records (the detached tip and the deleted branch's tip) count local branches and tags only,
  as they did before this ADR. Both leave out remote-tracking refs; the narrower set only records more.

**Residuals.**
- A commit made in the worktree between O5's second re-read and `git worktree remove` (one git call)
  is not caught when the worktree is detached; with a branch checked out, the compare-and-swap delete
  keeps it.
- The process probe sees only same-uid processes whose cwd it can read (#7173 WP06).
- A remote-tracking ref is read as a local cache: a landing ref that is stale may still vouch for a
  tip since force-pushed off the remote. O4 and the discarded-tip record keep such a tip reachable
  locally, so nothing is lost, but the verdict can be wrong.
