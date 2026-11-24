---
title: 'ADR: a destructive git operation discharges named proof obligations'
description: 'The eight things a command must prove before it removes a worktree or deletes a branch, and the guard entry that enforces them for doctor workspaces --prune.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-11-06'
updated: '2026-11-23T00:00:00Z'
---

# A destructive git operation discharges named proof obligations

**Status:** Accepted (2026-11-06, accepted by the operator on PR #7275). Operator rulings of 2026-11-06 on #7264 (ADR rather than a doc;
local refs only for reflog reachability; one guard entry for the prune).

**Date:** 2026-11-06

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #7264: write down the proof obligations of a safe destructive git operation. Slice S4 of epic #7276
  (lane and worktree model hardening), whose operator rulings 5, 6 and 7 (2026-11-06) set this ADR's scope.
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
| O1 | **Clean tree.** Nothing uncommitted or untracked would be destroyed. Ignored files are not protected: they are listed and go with the worktree. | `assert_worktree_clean(..., treat_untracked_as_dirty=True)` with the caller's residue context. | `MERGE_UNSAFE_WORKTREE_DIRTY` |
| O2 | **No live process.** No process is standing in the worktree. | The caller's probe answers for the worktree; "cannot tell" is a refusal, not a pass. | `PROCESS_IN_WORKTREE`, `PROCESS_PROOF_UNAVAILABLE` |
| O3 | **Landed against a named remote.** Every commit of the tip is on `refs/remotes/<remote>/<primary>` for a remote the repository configures: reachable from it, or absorbed by it (a `merge-tree` no-op, which covers squash landings). For a Mission lane the absorption proof sets aside Mission bookkeeping the lane never authored (Amendment 2026-11-23). | The landing ref must sit under `refs/remotes/<remote>/` for a configured `<remote>` and resolve; the caller's absorption proof is re-run on that ref at the proven tip. Nothing is fetched. | `LANDING_REF_UNNAMED`, `NOT_LANDED_ON_NAMED_REMOTE` |
| O4 | **Reflog-only commits are kept.** A commit that only the worktree `HEAD` reflog or the branch reflog still reaches would be lost when those reflogs go. | Before anything is removed, each such commit that no local ref reaches (`refs/heads`, `refs/tags`, `refs/spec-kitty`; a remote-tracking ref never vouches) is recorded under `refs/spec-kitty/discarded/reflog/<sha>`, create-only. A record that cannot be written refuses the removal. | `DESTRUCTIVE_OP_ONLY_COPY` |
| O5 | **Compare-and-swap deletes.** A ref is deleted only while it still holds the commit the proof was about, and the worktree is removed only while its `HEAD` was still that commit one step earlier. | The branch delete is `git update-ref --no-deref -d <ref> <tip>`, so a branch that moves while the delete runs is kept, and a symbolic branch never takes its target with it. git has no compare-and-swap for a worktree, so its `HEAD` and branch are re-read twice: before the other checks, and again as the last step before the removal. | `WORKTREE_TIP_MOVED`, `BRANCH_TIP_MOVED`, `BRANCH_CHECKED_OUT` |
| O6 | **Rebase-merged SHAs count as landed only by proof.** The pre-rebase commits of a rebase landing are reachable from nothing, yet their content is on the primary. | A reflog-only commit is left unrecorded only when every commit that would be lost with it replays onto the landing ref as a verbatim no-op (`git merge-tree --write-tree --merge-base <c>^ <landing-ref> <c>` returns the landing ref's own tree). A merge, a root or an empty commit, an empty range and any git error are no proof. `git cherry` is not used: its patch-id ignores whitespace, which can change what a program does. | (never refuses; it records) |
| O7 | **Never `--force`.** git's own refusals (a locked worktree, one it still finds dirty) are a last net, not something to override. | The removal is `git worktree remove` without `--force`, hard-coded. | `WORKTREE_REMOVE_REFUSED_BY_GIT` |
| O8 | **A recreate hint.** The branch or worktree comes back with one printed command, and a kept reflog commit with its own ref. Ignored files do not come back. | The result carries the command (`git branch <b> <tip>`, or `git worktree add [--detach] <path> <ref>`), plus the kept refs. | (always present) |

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

This list is the single authority for every destructive git operation (epic #7276, ruling 7). It binds
`doctor workspaces --prune` now, through `guarded_landed_removal`. The other callers adopt it in
their own slices, each through `destructive_guard.py`, never with a check of their own:

- **Consolidate cleanup** (S5, #7280). Removing lane worktrees and branches becomes the final step of
  the consolidation phase and does not wait for the pull request to merge (ruling 6). The prune stays
  the proof-based backstop for what that step leaves.
- **The consolidate teardown's late window** (S10, #7265).
- **Releasing a short-lived lane checkout** (S3, #7279, ruling 5). A release either commits or
  refuses. It is destructive, so O1 (nothing uncommitted is lost: it is committed, or the release is
  refused), O2, O5, O7 and O8 apply to it as written; O3, O4 and O6 apply whenever the release also
  deletes a branch.
- **Lane teardown** (`DESTROYED_LANE`, `LANE_WORK_TIP_UNKNOWN`), which already discharges several
  obligations through its own guards.

`LandedRemoval` names the proven tip, the branch and the ref that proves the landing, so those callers
can reuse the entry; a caller whose proof is not a remote-tracking ref (consolidation lands on the
local target) needs an amendment to O3 first, not a parallel check.

Evidence is read from git refs and the resolved status surface only. A lane worktree's own status
files never count as evidence for any obligation (epic #7276; #6466, #6884).

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
- Open gaps in the guard, to close before another caller adopts it, are in #7302: O1's stronger checks live only in the prune, per-worktree refs aren't kept, and the no-op proof can be false under a merge driver.
- A remote-tracking ref is read as a local cache: a landing ref that is stale may still vouch for a
  tip since force-pushed off the remote. The discarded-tip record keeps such a tip reachable locally,
  but the verdict can be wrong, and a reflog-only commit proven against that ref is not recorded.

## Amendment 2026-11-23: Mission bookkeeping in the O3 absorption proof

**Rulings.** Operator rulings 2026-11-22 ("Ancestor blob + keep-code") and 2026-11-23 (Option A),
Mission `lane-cleanup-landing-proof-01M81KHJ`, issues #7747 and #7325.

**Problem.** A `lanes_with_coord` lane syncs with the coordination branch while it is implemented
(`implement` merges it in). It therefore carries older copies of Mission files the tool rewrites after
the sync: the status log, `status.json`, `meta.json`, and each work package prompt's claim frontmatter.
A squash landing collapses the coordination history into one commit, and consolidate deletes the
coordination branch before lane cleanup. The plain O3 proof (an exact `merge-tree` no-op) could
therefore never pass such a lane. Consolidate kept every lane of an ordinary squash landing with
`NOT_LANDED_ON_NAMED_REMOTE`, and `doctor workspaces --prune`, the printed remedy, refused the same
lanes with `CONTENT_NOT_ON_PRIMARY` (#7747).

**Decision.** O3's absorption evidence for a Mission lane is
`specify_cli.lanes.lane_tip.is_absorbed_but_for_mission_bookkeeping`. Consolidate's lane cleanup and
the `accept --mode pr` lane cleanup use it (the latter by operator ruling 2026-11-23, 3A: it matters
when the pushed head does not carry the coordination history a lane merged). `doctor workspaces` uses
it for the lanes of a released Mission only (consolidated or pr-accepted, no active consolidation
record, no retention). Every other worktree keeps the plain proof.
A lane is landed when its tip is an ancestor of the landing ref, or when every difference is accounted
for:

1. **Outside `kitty-specs/`**, merging the tip into the landing ref has no conflict and changes nothing.
2. **The lane's own Mission status log**: every lane event line is in the landing's log. The log is
   append-only. This set-aside shipped with #6736 (lane cleanup on a coordination topology) and was
   not recorded here before; this amendment records it.
3. **`status.json`, `meta.json` and `tasks/WP*.md` of the lane's own Mission** (#7747): both sides
   have the file, and the lane never authored its copy. The lane's own commits are its first-parent
   commits that neither the landing ref nor any branch it merged in reaches. A path is authored when
   one of those commits changed it. A merge counts as authoring a path only when its result for that
   path is none of its merged-in parents' versions, so a merge-driver or conflict resolution counts as
   authored. Separately, a version the landing ref's own history holds also passes.
4. **A `kitty-specs/` file the lane did not author** whose lane copy is the merge base's copy (only
   the landing ref moved it), or that the lane has no copy of: nothing to lose. This is a blob
   comparison, not a merge result.

No merge or merge-driver result is evidence for a `kitty-specs/` path (#7302 item 3). Everything else
fails closed: any other `kitty-specs/` change the lane made, a deletion the lane made, an unknown ref,
or any git error. One deletion is the exception: the lane's own Mission status log, because the log is
append-only and rule 2 judges it by its events, so a lane without a copy has none to lose. "Set aside"
applies to the lane's own changes only: the matrices (`issue-matrix.json`, `acceptance-matrix.json`)
and every other Mission file are never set aside when the lane changed them, while a file the lane
left untouched (rule 4) is no lane change at all.

**The kept legs (#7325).** `GuardedLaneRemover` no longer hands a lane with a branch leg to the older
remover. A lane is kept with `LANDING_PROOF_UNAVAILABLE`, its branch untouched, in each of these cases:

- there is no landing proof;
- a local proof has an empty reconciliation PASS anchor;
- the worktree is gone while the branch remains;
- no tip can be named.

A lane whose worktree and branch are both gone is reported removed. The retained-branch leg (worktree
removed, branch kept by policy) stays on the guarded worktree removal: it deletes no branch (plan
decision PD-1, decided by the operator on 2026-11-23, ruling 4A). The guard itself is unchanged.

**Residual (amended 2026-11-24, below).** A version that a lane merged in from a branch other than the coordination branch, for
example a dependency lane, counts as not authored on this lane. That branch's own lane is judged on its
own, and only the bookkeeping kinds above can be set aside.


## Amendment 2026-11-24: the lane's own changes only, the snapshot as a projection, and the Mission-branch proof

**Ruling.** Operator ruling 2026-11-24, after the Mission's own landing kept all three of its lanes
(dogfood run on `lane-cleanup-landing-proof-01M81KHJ`). It amends rules 3 and 4 above and adds one
proof.

**Problem.** Three shapes of an ordinary Mission still kept its lanes:

- **A.** A dependent lane rewrote lines an earlier lane wrote. The squash's merge base is the
  pre-Mission tip, so the earlier lane's exact version conflicts with the landing in `merge-tree`,
  although approved work superseded it.
- **B.** A planning file (`spec.md`, `analysis-report.md`, `acceptance-matrix.json`) changed on the
  coordination branch after a lane's last sync. The lane never wrote its copy, but rule 4 above only
  set aside a copy equal to the merge base's.
- **C.** Consolidate's own auto-rebase merged the coordination branch into a stale lane, and the
  status-snapshot merge driver produced a `status.json` equal to neither parent, which rule 3 counted
  as the lane's authoring.

**Decision.**

- **B.** A file under the lane's own `kitty-specs/<mission>/` that the lane never authored does not
  keep it, whatever the target did with it. Authorship is read as in rule 3 (merge results are still
  distrusted). Rule 4 stays for other Missions' files, which still fail closed otherwise.
- **C.** `status.json` is a projection of the status log. It is accounted for when the lane's
  `status.events.jsonl` is contained in the landing's log (rule 2); its authorship is never read.
- **A.** Before the coordination teardown deletes the Mission branch, `consolidate` records, per
  lane, whether
  `lane_tip.is_landed_through_mission_branch` holds: the lane tip is an ancestor of the Mission branch
  tip, every path outside `kitty-specs/` the lane changed since its merge base with the anchor (read
  from the tree diff, so a fast-forwarded lane is judged too) either has the lane's own final blob on
  the anchor or was changed again by later approved work: an own non-merge commit of another
  approved lane (a lane whose every work package is in the run's approved claim; the same
  first-parent walk as authorship, less the Mission branch's own first-parent line) that is on the
  Mission branch and descends from the lane's last commit changing that path (operator ruling
  2026-11-24 on Tier R B1, option (b), and the Tier R confirm passes). A revert or rewrite made on the
  Mission branch outside any lane, including one an approved lane forked from, a parallel lane's
  edit of the same file, and work another lane only merged in (a resync) keep the lane; any probe or
  attribution error keeps it too,
  every path outside `kitty-specs/` the Mission branch changed since its merge base with the
  reconciliation PASS anchor has the Mission branch's blob on the anchor (the target keeps its own
  content elsewhere), and every `kitty-specs/` difference between the lane and the anchor is accounted for by the rules above (a
  `meta.json` or `tasks/WP*.md` version the lane authored may also be in the Mission branch's history,
  since a squash keeps only that branch's last version). The proven tips and the anchor reach the
  guard as `MissionBranchProjection` on the `LocalTargetAtPass` proof; the guard's O3 evidence
  accepts a proven tip, besides the content proof, only for a landing whose PASS anchor is the proven
  anchor or descends from it. A descendant is accepted because consolidate carries the PASS anchor
  over its own post-landing commits (`_carry_pass_anchor_over_own_commit`, FR-035), and the
  projection lives only in memory within that one cleanup phase, so nothing else can advance it.
  The check is ancestry only, not that the commits in between are consolidate's own: if the
  projection is ever persisted (the `--resume` residual below), this becomes a gap, to be closed by
  recording the carried SHAs or requiring the commits in between to touch only bookkeeping paths.
  Building the projection never aborts cleanup: any error yields no projection, and the lanes are
  judged by the content proof alone.
- **Authorship** (R24 squad): a lane's own commits are its first-parent commits that no merged-in
  branch's own first-parent line holds, so a lane commit the coordination branch merged back (and the
  lane then resynced) stays the lane's; changed names are read NUL-separated, so a name git quotes is
  still matched.

**Residuals.**

- `doctor workspaces` after a push has no Mission branch to read, so a lane in shape A is still
  rated `not_landed` there. A per-path rule (a lane path is superseded when an approved lane that
  depends on it changed that path later) is tracked as follow-up #7838.
- Supersession is judged per path, not per line (operator ruling 2026-11-24 on Tier R confirm 2
  N1, option (a); line attribution is not used). An approved lane that edits another line of the
  same file therefore supersedes an out-of-workflow revert or rewrite of this lane's line, and the lane is
  removed. Such a removal is recoverable: a lane that only the Mission-branch proof discharged (the
  content proof runs first and failed) keeps `refs/spec-kitty/lane-tip/<branch>` at the removed tip
  instead of having it cleared, and its `Removed` line names it
  (`(recoverable: refs/spec-kitty/lane-tip/<branch>)`; operator ruling 2026-11-24). A lane the
  content proof discharged still has its ref cleared: its work is on the target. The ref is written
  at the tip before the guard may delete the branch and cleared afterwards only on the content-proof
  leg, so a failed write keeps the lane and an interruption after the delete still leaves the tip
  named; a lane the guard keeps gets its earlier ref back (Tier R confirm 4). The kept ref reads
  like any lane whose branch is gone (FR-034): a cleanup re-run reports the lane removed and leaves
  the ref, `git branch <branch> refs/spec-kitty/lane-tip/<branch>` recreates the lane, and a work
  package reopened on it is refused `DESTROYED_LANE` naming the tip (its work is not on the target),
  not `LANE_WORK_TIP_UNKNOWN`; `git update-ref -d` on the ref abandons it. The JSON cleanup report is
  unchanged. Tracked in #7838.
- A `--resume` whose earlier attempt already tore down the Mission branch runs without the
  projection; the projection is not persisted.
- `orchestrator-api consolidate-mission` has no reconciliation PASS anchor, so it does not use the
  Mission-branch proof: a lane in shape A is kept there.
- A lane commit that a branch other than the coordination branch carries on its own first-parent
  line (for example a dependency lane forked from it, merged back into the lane) counts as not
  authored on this lane.
- A lane fast-forwarded to a coordination merge that contains its own commit loses that commit's
  authorship: the commit then sits behind a second parent, off the lane's first-parent chain. Spec
  Kitty's own syncs merge with `--no-ff`, so only a hand fast-forward reaches this. The Mission-branch
  proof reads the lane's product paths from the tree diff, so it still judges such a lane path by
  path; the authorship loss affects only the `kitty-specs/` rules, where a lane-written Mission file
  of a fast-forwarded lane is treated as not authored (set aside).
