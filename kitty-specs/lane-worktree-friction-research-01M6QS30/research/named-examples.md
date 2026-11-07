# Named examples: lane / worktree execution-model friction

Evidence file for mission `lane-worktree-friction-research-01M6QS30`. Read-only forensics, gathered 2026-11-06 from the GitHub REST API (issue bodies, all comments, linked PRs and their merge state). Lens: root cause, mechanism, reproduction.

**Option key** (used in every "Removed by" line):

- **(a)** Tighten the current model: one status-surface resolver, lifecycle ownership of worktrees, prune only with a proof.
- **(b)** Lanes stay branches, with no persistent checkouts: an ephemeral worktree per command.
- **(c)** `single_branch` becomes the default and lanes are opt-in.
- **(d)** Drop lane worktrees entirely.

Verdicts: **Yes** = the mechanism cannot occur. **Partial** = it gets rarer or narrower. **No** = it is unaffected. **Worse** = the option makes it more common.

Operator ruling 2026-11-06 (on #6466 and #6884): "the resolved status surface is the only source of truth. A lane worktree's own status files never count."

---

## #7173 Landed worktrees and branches are never cleaned up, and upgrade commits into all of them

<https://github.com/spec-kitty/spec-kitty/issues/7173>. Closed. Opened 2026-11-04. Fixed by PR #7196 (merged 2026-11-05). Its `.gitattributes` part was split out to #7217 (open).

- **Symptom.** One maintainer clone held 54 worktrees and 55 local branches. 48 of them had already landed and used about 36 GB. A plain `spec-kitty upgrade` would have "written and committed across 53 extra checkouts, including the landing branches of six PRs that were still open" (`upgrade.py:836-847` auto-commits on each worktree's own branch). The preview names this only in `--plan-json`.
- **Mechanism.** Persistent checkouts outlive the session that made them. In the issue's words: "No step owns removal", and "The merge outlives the session ... Nobody is left to clean up." `consolidate` tears down Mission lanes only. Upgrade fans out into every registered checkout. Proving a branch landed is non-trivial: "Rebase merges also rewrite SHAs, so `git branch -d` refuses every one of these ... Any automation needs a proof, not the merge flag."
- **Severity.** Wasted disk and time. There was also a latent risk of unwanted commits on open PR branches; one worktree held commits that were on no remote.
- **Removed by.** (a) Yes; that is what #7196 shipped. (b) Yes for Mission lanes, but landing worktrees are a maintainer habit outside the Mission model. (c) Partial, because there are fewer worktrees. (d) Mission side only. Landing worktrees are not Mission lanes, so no option removes them unless landing also moves to ephemeral checkouts.
- **Decisions the issue asked for.** Where cleanup belongs:
  1. a provable prune command;
  2. runbook and skill steps;
  3. a post-consolidation or pre-PR report;
  4. a safe `upgrade`.

## #7196 [PR] Report and prune landed worktrees; upgrade stops committing into non-Mission worktrees

<https://github.com/spec-kitty/spec-kitty/issues/7196>. Merged 2026-11-05 (`7940ff7f37`).

- **What it does.** Adds `doctor workspaces` with `--prune`. Landing is proven offline against `origin/<primary>` through `lane_tip.is_absorbed`. A worktree is removed only when it is clean, idle (checked through `/proc`), unlocked, not Mission-owned and has no git operation in progress. Removal goes through the destructive guard, which gains a new `LANDED_INTENT` mode with no `--force`. A tip that no other branch reaches is kept under `refs/spec-kitty/discarded/`. `upgrade` now skips non-Mission worktrees unless the operator opts in.
- **Why it is evidence.** The cost of option (a) shows in the record:
  - The landing review found that a lane in the middle of a rebase is detached, so "a Mission lane mid-rebase was judged `landed` and pruned (reproduced)".
  - The fix needed eight deferred follow-ups: #7211–#7218.
  - Removal is Linux-only (#7216).
  - Ignored files (`.venv`, `.env`) are deleted along with the worktree.
- **Takeaway.** Making persistent checkouts safely disposable takes a long list of proof obligations. #7264 now asks for that list to be written down.

## #7211 doctor workspaces --prune drops commits reachable only from the worktree's HEAD reflog or the branch reflog

<https://github.com/spec-kitty/spec-kitty/issues/7211>. Open. Opened 2026-11-05. Fix PR #7237 is open (ready for review).

- **Symptom.** A commit made while detached and then left behind ends up with no ref and no reflog after the prune, so `git gc` can collect it. In the reviewer's reproduction, `git fsck --unreachable --no-reflogs` lists the commit.
- **Mechanism.** Destroying a persistent checkout also destroys its private history. `git worktree remove` deletes `.git/worktrees/<id>/logs/HEAD`, and `git branch -D` deletes the branch reflog. Rebase landings leave pre-rebase commits that only the reflog still reaches.
- **Severity.** Data loss: silent and latent.
- **Fix taken in #7237.** Option (b) from the issue, "keep refs", narrowed by a patch-id check (`git cherry`). It also needs a "no merge" clause, because "`git cherry` omits merges".
- **Removed by.** (a) Yes, through the obligation list in #7264. (b) Partial: an ephemeral checkout is destroyed every command, so the same obligation applies on every teardown, unless commands only ever commit onto a named ref. (c) Partial, because fewer worktrees are destroyed. (d) Mission side only.

## #7212 doctor workspaces --prune: branch delete after the tip check is not compare-and-swap

<https://github.com/spec-kitty/spec-kitty/issues/7212>. Open. Fix PR #7239 is open.

- **Symptom.** A branch that moves between the tip check and `git branch -D` is deleted, new commit included.
- **Mechanism.** A check-then-act race during teardown (TOCTOU). The CAS primitive already existed in `ref_advance.delete_branch_ref`. The landed prune "is the third site and reintroduced the pattern". The fix also found that `update-ref -d` dereferences symbolic refs, so it now deletes with `--no-deref`.
- **Severity.** Data loss, in a window of milliseconds.
- **Removed by.** No option. Any model that deletes branches needs CAS. (c) and (d) narrow the exposure only by deleting fewer branches.

## #7214 doctor workspaces reads only origin/<primary>, so a fork clone never sees a landed worktree

<https://github.com/spec-kitty/spec-kitty/issues/7214>. Open. Fix PR #7240 is open (`--remote <name>`).

- **Symptom.** In a fork clone, every landing worktree reports as not landed forever, so `--prune` never removes anything.
- **Mechanism.** The landing proof is bound to one remote-tracking ref. The runbook itself fetches from `upstream` but says `git fetch origin`.
- **Severity.** Wasted time. The prune silently does nothing.
- **Removed by.** No option; this is about the ref proof, not the worktree model. Under (b) or (d) the prune is not needed for Mission lanes in the first place.
- **Side note from the #7240 comment.** "The workspace for this mission was removed mid-run by the batch-11 clone cleanup ... the mission was rebuilt on current `main`." That is worktree lifecycle friction in the fleet itself.

## #6466 Lane-worktree vs root/mission-branch status.json divergence forces unnecessary --force on routine transitions

<https://github.com/spec-kitty/spec-kitty/issues/6466>. Open. Opened 2026-10-19 on 3.2.7. Fix PR #6884 is open; its hold was lifted 2026-11-06.

- **Symptom.** A WP implemented in its lane worktree reads as `planned` when a status read is anchored at that lane worktree. `planned -> for_review` is not a legal edge, so the operator has to use `--force`, and that pollutes the audit trail.
- **Mechanism.** Each checkout carries its own copy of the status files, and the read is anchored at the checkout instead of the resolved surface. Reproduction on main (comment of 2026-10-31):
  - `lanes_with_coord`: the divergence "cannot occur". Lane worktrees carry no status files.
  - `lanes` (branch-flat): "the lane worktree keeps a stale tracked copy of `kitty-specs/<slug>/status.events.jsonl` (the fork-time log: 1 event, lane `planned`) while the authoritative copy already holds 3 events".
- **Severity.** A forced override, which degrades the signal value of `--force`.
- **Removed by.** (a) Yes; #6884 normalises a lane-worktree root to the main root. (b) Partial: an ephemeral checkout still contains the fork-time copy, and the read must still go through the resolver. (c) Yes for the default, since there is one checkout. (d) Yes.
- **Operator ruling 2026-11-06.** "a lane worktree's own status files are never a source of truth."

## #6884 [PR] [#6466] A lane worktree root is never a status surface

<https://github.com/spec-kitty/spec-kitty/issues/6884>. Open. Opened 2026-10-31.

- **Change.** `_canonical_status_read_root` in `_read_path_resolver.py` maps a `repo_root` that the worktree registry classifies as a lane worktree back to the main worktree root. It leaves four cases alone: the coordination worktree (which *is* the authority), an independent clone, a husk, and an unreadable registry (which fails closed).
- **Root cause, as the PR states it.** The seam "documented its `repo_root` as 'the primary checkout' but never enforced it".
- **Deferred.** #4955 (merge drivers). `candidate_feature_dir_for_mission`, the diagnostic resolver, still composes from the root it is handed.
- **Operator instruction on landing.** "make sure every status read and write path resolves through the canonical surface resolver, with no fallback to the open worktree, and add a regression test that a divergent lane-worktree `status.json` / `status.events.jsonl` is ignored."

## #7198 consolidate: a late coordination commit touching only status or meta.json is approved without being landed

<https://github.com/spec-kitty/spec-kitty/issues/7198>. Open. Fix PR #7228 is open.

- **Symptom.** A late commit on the coordination branch that touches only `status.events.jsonl` or `meta.json` is dropped at exit 0 on a first `consolidate`. Before PR #7124 the same run refused.
- **Mechanism.** The coordination branch is a second home for shared state, and the gate reads a checkout instead of a ref. The quote: "the union stage merges the coordination worktree's working-tree event log, not branch commits." So a status append committed on the coordination branch *from another checkout* is invisible to the union stage. `assert_late_window_landed` exempts these files, and #7124 advances the approved tip past them.
- **Severity.** Data loss at exit 0 (`[INFERENCE]` on how often it is reachable).
- **Removed by.** (a) Yes; #7228 proves every change in the late window. (b) Partial, only if the union reads the branch ref. (c) Yes for the default, since there is no coordination branch. (d) Partial: the coordination worktree and branch can survive dropping lane worktrees.

## #7199 consolidate --resume: a coordination commit after the resume's own capture is refused although its window landed it

<https://github.com/spec-kitty/spec-kitty/issues/7199>. Open. Fix PR #7226 is open, and it conflicts with #7228 in the same function.

- **Symptom.** `--resume` refuses at the projection teardown gate ("compare-and-swap failed") even though the content already landed.
- **Mechanism.** The coordination branch can move while a multi-phase run is between its capture and its teardown. The anchor advance runs only when `not run.is_resume`.
- **Severity.** Wasted time. It fails closed, and the operator has to run `--resume` again.
- **Removed by.** (a) Yes; see #7265. (b) No. (c) Yes for the default. (d) Partial.

## #6791 consolidate --resume after COORD_TEARDOWN_KEPT_ONLY_COPY projects only part of the coordination commits, then deletes the coordination branch

<https://github.com/spec-kitty/spec-kitty/issues/6791>. Closed. Fixed by PR #6857 (merged 2026-10-31). First-run follow-up #6871 was fixed by PR #7124 (merged 2026-11-05).

- **Symptom.** With auto-commit disabled, untracked review-cycle files in the coordination worktree triggered `COORD_TEARDOWN_KEPT_ONLY_COPY`. The operator then:
  1. committed those files on the coordination branch, as the refusal said to (commit A);
  2. recorded an issue verdict (commit B, `surface=kitty/mission-<slug>`);
  3. ran `--resume`.

  The resume projected only A and deleted the branch, leaving B dangling (`git fsck --lost-found`). The Mission landed `done` with the row still `in-mission`.
- **Mechanism.** State is split between the coordination branch and the target, and a late window has to be projected before teardown. The cause was an exclusion that is right for one window and wrong for another: gate matrices were excluded, which is correct mid-merge and wrong after teardown. The refusal's own remedy sent the operator to write onto the branch that was about to be deleted.
- **Severity.** Data loss at exit 0, and a wrong verdict.
- **Removed by.** (a) Yes; that is what #6857 and #7124 shipped. (b) No. (c) Yes for the default. (d) Partial.

## #6770 consolidate re-run after a failed reconciliation reuses attempt 1's pre_mutation_target_sha

<https://github.com/spec-kitty/spec-kitty/issues/6770>. Closed. Fixed by PR #6867 (merged 2026-10-31). It is a recurrence of #5667.

- **Symptom.** After a reconciliation FAIL and its rollback, the next plain `consolidate` reused attempt 1's target base. The operator's fix commits were flagged "un-attributable", and the rollback reset the target to the stale tip. A plain `--abort` then refused, so the operator needed `--abort --release-branch`.
- **Mechanism.** The transaction record outlives the attempt: `_resolve_pre_mutation_target_sha` reads the persisted value first. This comes from multi-lane consolidation, not from checkouts.
- **Severity.** A wrong verdict, a forced override (`--release-branch`), and wasted time.
- **Removed by.** (a) Yes; that is what #6867 shipped. (b) and (d) No. (c) Partial: `single_branch` still consolidates and reconciles, with fewer moving branches.

## #5550 implement: WRITE_CHECKOUT_OCCUPIED counts single_branch missions that target a different branch

<https://github.com/spec-kitty/spec-kitty/issues/5550>. Closed. Fixed by PR #5696 (merged 2026-10-04). It absorbed #5680 and #5685.

- **Symptom.** A fresh `single_branch` Mission was refused because an unrelated, committed Mission had a WP left `in_progress`. The printed remedy, `move-task ... --to blocked --force`, also failed, with `DESTINATION_REF_NOT_FOUND`, because that Mission's branch had been deleted on origin. The quote: "the occupant is a WP that no supported command can move: the suggested remedy is a dead end".
- **Mechanism.** One shared write checkout used as a mutex across Missions, with occupancy computed from committed status logs regardless of branch.
- **Severity.** Wasted time, and a forced workaround: `move-task WP01 --to in_progress` on the operator's own Mission.
- **Removed by.** (a) Yes; that is what #5696 shipped. (b) No. (c) **Worse**: this is `single_branch` friction, and defaulting to that topology makes it more common. (d) No.
- **Sibling, open.** #5676: `agent mission create` switches an occupied root checkout, so "the implementer's next commit lands on the new mission's branch, exit 0".

## #6715 lanes/coord topology: a claimed but never-implemented WP can be self-approved, accepted and consolidated as done

<https://github.com/spec-kitty/spec-kitty/issues/6715>. Closed. Fixed by PR #6781 (merged 2026-10-29). Follow-up #6780 was fixed by PR #6860.

- **Symptom.** The same agent claimed and approved an empty WP. Accept and consolidate both exited 0, and consolidate printed "Reconciliation verified". The owned file was absent on the target.
- **Mechanism.** Guards are implemented per topology:
  - `_mt_require_single_branch_implementation` "returns early for any topology other than `single_branch`".
  - `approved_bound` treats a lane with no commits beyond its base as having "nothing to bound".

  Follow-up #6780: the evidence window used the live lane branch, so once lane branches were pruned after a PR merge, every WP refused with `IMPLEMENTATION_UNREADABLE`. That ties evidence to the branch's lifetime.
- **Severity.** A wrong verdict at exit 0, with the deliverable missing.
- **Removed by.** (a) Yes; that is what #6781 shipped. (b) No; the evidence is still the lane branch. (c) Partial: with fewer topologies there is less room for guards to drift. (d) No; lane branches remain.

## #7264 Design: the proof obligations of a safe destructive git operation

<https://github.com/spec-kitty/spec-kitty/issues/7264>. Open. Opened 2026-11-06 (PR triage).

- **Problem.** The prune drew three safety PRs within days (#7239, #7237, #7240) because the contract "was never written down".
- **Proposal.** One ADR listing the proof obligations:
  - a clean tree;
  - no live process;
  - every commit reachable from a named remote ref, or an identical tree with an empty `git cherry`;
  - reflog-only commits kept;
  - CAS deletes;
  - rebase-merged SHAs handled;
  - never `--force`;
  - a recreate hint.

  `git/destructive_guard.py` enforces it for *every* destructive command: prune, lane teardown and consolidate cleanup.
- **Decisions asked.** Adopt the contract, and land in the order #7239 → #7237 → #7240.

## #7265 Design: one pass over the consolidate late teardown window

<https://github.com/spec-kitty/spec-kitty/issues/7265>. Open. Opened 2026-11-06.

- **Problem.** #6791 led to #7198 and #7199. #7228 and #7226 edit the same function (`_land_late_coordination_commits`) with conflicting hunks. #7233 (for #7201) touches the same file.
- **Proposal.** "one design pass that states what the late window must prove and on which tip, covering resume". Then land #7228 absorbing #7226, then #7233.
- **Decision asked.** Design before patching, plus that landing order.

## #7266 Fleet PR hygiene: keep Mission artefacts and Op records out of fix PRs

<https://github.com/spec-kitty/spec-kitty/issues/7266>. Open. Opened 2026-11-06.

- **Problem.** Every fleet PR committed 20–38 `kitty-specs/` files, plus `kitty-ops/*.jsonl` in some, around a source change of 1–8 files. In the triage, 33 of 58 PRs were `dirty` and 18 were `blocked`. Shared generated files are hand-merged on every rebase.
- **Decision asked.** Either (a) Mission artefacts go in a separate PR or "stay on the coordination branch", or (b) a slim artefact set is kept. In both cases `kitty-ops` records never go into a fix PR, `_completion_manifest.json` is regenerated rather than merged, and a CI check enforces the rule.
- **Relevance.** This is the multi-branch copy problem at PR scale. It makes the coordination branch a candidate home for artefacts, which cuts against options (c) and (d).

---

## Same-mechanism issues followed

- **#6871** (closed; PR #7124 merged 2026-11-05). On a first run, a coordination commit made between the gate and teardown was deleted silently at exit 0. This is the first-run twin of #6791. <https://github.com/spec-kitty/spec-kitty/issues/6871>
- **#5457** (closed). `upgrade` with a live lane wrote `.kittify/metadata.yaml` "separately in the main checkout and in every lane worktree ... and commits each copy on its own branch". Consolidate then refused with `TARGET_BRANCH_CONTENT_CONFLICT`, and the printed remedy did not clear it. That is upgrade fanning out into every checkout, with per-branch copies of shared state. <https://github.com/spec-kitty/spec-kitty/issues/5457>
- **#4955** (open). `status.json`, `lifecycle.jsonl`, `mission-events.jsonl` and `decisions/index.json` fail closed on divergence on both sides, because they have no reconciling merge driver. This is per-branch copies of state that is really shared. <https://github.com/spec-kitty/spec-kitty/issues/4955>
- **#5676** (open). On protected main, `single_branch` create switches an occupied root checkout, so the implementer's commits land on another Mission's branch at exit 0. This is friction of the shared-single-checkout model, relevant to option (c). <https://github.com/spec-kitty/spec-kitty/issues/5676>
- **#6780** (closed; PR #6860). Evidence read from a live lane branch fails once the branch is pruned. <https://github.com/spec-kitty/spec-kitty/issues/6780>
- **#5667** (closed). The original form of #6770. <https://github.com/spec-kitty/spec-kitty/issues/5667>
- **#1619** (open epic). "Every command boundary works out its own mission context ... When one boundary derives it differently from another, authority splits." Adoption of the single `MissionExecutionContext` "is thin". <https://github.com/spec-kitty/spec-kitty/issues/1619>
- Open follow-ups of #7196: #7213, #7215, #7216, #7217, #7218.

## Recurring mechanisms

| # | Mechanism | Issues |
|---|---|---|
| M1 | Each checkout or branch holds its own copy of shared Mission state, and reads anchor at a checkout instead of the resolved surface | #6466, #6884, #5457, #4955, #7198 |
| M2 | The coordination branch is a second home that must be projected onto the target before teardown, so a late-window race appears | #6791, #6871, #7198, #7199, #7265, (#7201) |
| M3 | Persistent checkouts outlive the session and the merge, nobody owns removal, and safe removal needs a growing proof list | #7173, #7196, #7211, #7212, #7214, #7216, #7264 |
| M4 | Operations fan out into every checkout and commit on every branch | #7173, #5457 |
| M5 | Multi-phase transaction anchors outlive their attempt (CAS bases, persisted window base) | #6770, #5667, #7199 |
| M6 | Topology multiplicity: guards are written per topology and drift, and the `single_branch` shared checkout has its own mutex problems | #6715, #6780, #5550, #5676 |
