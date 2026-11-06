# Draft: amendment to ADR 2026-11-06-1 (destructive proof obligations) for Mission lane cleanup

**For:** the owner of PR [#7275](https://github.com/spec-kitty/spec-kitty/pull/7275) (branch `issue-7211-safe-landed-prune`), which carries `docs/adr/4.x/2026-11-06-1-a-destructive-git-operation-discharges-named-proof-obligations.md`. That ADR is not on `main` and not on this Mission's branch, so the amendment is drafted here (Mission constraint C-016, FR-038).

**Who lands it:** the operator, or the #7275 owner at the operator's request, by appending the section below verbatim to the end of ADR 2026-11-06-1.

**When:** with #7275 or after it merges, and **before** the S5 binding pull request (Mission `lane-worktree-model-hardening-01M6QY1M`, WP16, FR-037) merges, because that pull request binds the lane remover to the amended O3.

**Binding target.** The lane-cleanup module's remover port (`consolidation/lane_cleanup.py`, `LaneRemover`, Mission WP15) binds to the existing guard entry, unchanged in shape:

```python
guarded_landed_removal(
    repo_root,
    LandedRemoval(worktree=..., branch=..., tip=..., remote=..., landing_ref=...),
    context=...,       # the lane residue classifier (ResidueClassifier)
    processes_in=...,  # the process probe (ProcessProbe)
    absorbed=...,      # the absorption proof (AbsorptionProof)
)
```

The local landing proof below needs one more field on `LandedRemoval` (a recommendation; the owner may shape it differently): `passed_sha: str | None = None`, set only for the local form. The Mission's `LandingProof` values map onto it at the port: `LocalTargetAtPass(target_ref, passed_sha)` becomes `remote=""`, `landing_ref=target_ref`, `passed_sha=passed_sha`; `RemoteRef(remote, ref)` becomes `remote=remote`, `landing_ref=ref`.

**Status:** the section is written as Proposed; the operator accepts it by merging it. It cites the S5 operator ruling (DM `01M6QY4B7P4T68TE7JE30FRJV6`, "seam now, amend later") and the answers the S4 session gave on O2, O3 and O7.

---

## Amendment 2026-11-06: consolidation cleanup, pr-mode cleanup and the Mission-lane prune backstop

**Status:** Proposed. Operator rulings 6 and 7 of epic #7276 (2026-11-06) and the S5 escalation answer (DM `01M6QY4B7P4T68TE7JE30FRJV6` in Mission `lane-worktree-model-hardening-01M6QY1M`): "Seam now, amend later: extract one lane-cleanup module behind a remover port; kept lanes are reported, never a traceback after a verified landing; [...] draft the ADR 2026-11-06-1 amendment (local target at the gate-passed tip as landing proof; probe unavailable means keep and report). Bind the port to destructive_guard once #7275 merges." Slice S5, [#7280](https://github.com/spec-kitty/spec-kitty/issues/7280).

### Scope extended

`guarded_landed_removal` now also binds, through the one lane-cleanup module (`consolidation/lane_cleanup.py`) and its remover port:

- **Consolidation cleanup**: the final step of the consolidation phase (ruling 6), after the reconciliation gate, the late window and the coordination teardown ([ADR 2026-09-19-1](../3.x/2026-09-19-1-terminus-safety-invariant.md) Amendment 2026-11-06). The same module serves `spec-kitty consolidate`, `orchestrator-api consolidate-mission` and `mission close --discard`.
- **pr-mode cleanup**: a committed `spec-kitty accept --mode pr` removes each lane whose tip the pushed pull request head absorbs, without waiting for the pull request to merge.
- **The prune backstop for Mission lanes**: `spec-kitty doctor workspaces --prune` treats a lane of a consolidated or pr-accepted Mission as a candidate when no consolidation record is active and no retention is declared.

After a verified landing (consolidate) or a committed acceptance (pr mode), a refusal from the guard is a **kept** lane: reported with its code, remedy and command, and the command still exits 0. It is never raised as a failure of the landing.

### O3: a local landing proof for consolidation

Consolidation lands on the **local** target branch, not on a remote-tracking ref, so O3's "landed against a named remote" cannot be met by it. O3 gains a second form; `_assert_named_landing_ref` is relaxed to accept either:

- **Remote form** (unchanged): `refs/remotes/<remote>/<branch>` for a configured `<remote>`. pr-mode cleanup uses it with the pushed pull request head's tracking ref; the prune uses it as today.
- **Local form (new)**: `refs/heads/<target>`, accepted only when it resolves to exactly the tip the reconciliation gate passed in this run (`ConsolidationState.reconciliation_passed_target_sha`, carried as `passed_sha`). The caller's absorption proof is then re-run on that ref at the proven lane tip, as for the remote form.
- A ref of neither form refuses with `LANDING_REF_UNNAMED`. A local target that moved off the gate-passed tip, or does not absorb the lane tip, refuses with `NOT_LANDED_ON_NAMED_REMOTE` (reused; the message names the local target). No new code.
- **The branch the landing is proven against is never deleted**, in either form: the target for the local form, the pull request head branch (the Mission branch) for pr mode (`BRANCH_IS_PRIMARY`). Consolidation cleanup therefore never deletes the Mission branch of a pull-request-bound Mission.

### O2: probe unavailable means keep and report

For every caller this amendment adds, `PROCESS_PROOF_UNAVAILABLE` keeps the lane worktree and reports it (exit 0 after a verified landing). It is never a pass and never a failure of the command. On a platform where the process probe cannot answer (macOS and Windows today), consolidation therefore keeps lane worktrees and reports them. Lane branches that no kept worktree checks out are deleted as usual; a kept worktree keeps its branch, since git refuses to delete a branch a worktree has checked out (the Order rule).

### O7: residue versus never `--force`

O7 stands: `git worktree remove` never runs with `--force`. A lane checkout that holds **only residue** is still removable: O1 passes with the caller's residue classifier, the guard then deletes exactly the untracked entries that classifier names as residue (nothing else), and runs plain `git worktree remove`. git removes ignored files itself. Anything else still in the tree makes git refuse (`WORKTREE_REMOVE_REFUSED_BY_GIT`), and the lane is kept and reported. Callers that pass `force=True` to `guarded_worktree_remove` today move to this rule when they bind.

### A named tool-owned scratch exemption

The consolidation merge scratch worktree, at exactly `.kittify/runtime/merge/<mission_id>/workspace` (`consolidation/workspace.py::cleanup_merge_workspace`), is tool-owned scratch: it holds no work of its own (every commit made in it is on a ref the run advanced by compare-and-swap) and is not a retained resource. It is exempt from O1 to O8 and is cleaned up unconditionally, as today. The exemption is by that exact path and that function only; the routing gate (`tests/architectural/test_destructive_op_routing.py`) pins it, and no other path may claim it.

### Lane-tip and tombstone refs are guarded operations

- Deleting a lane-tip ref (`refs/spec-kitty/lane-tip/<branch>`, `lanes/lane_tip.py::clear_tip`) is a ref deletion under this ADR: compare-and-swap on the value it held, and only after the lane branch's delete is confirmed, so the last reference to an unabsorbed lane survives a missing or kept branch. The data-loss fix in `clear_tip` (clear only after a confirmed delete) is S5's (Mission WP15, FR-034), not this amendment's.
- Tombstones (`refs/spec-kitty/discarded/*`, O4's records and the discarded-tip records) are created create-only. Deleting one is a destructive operation that must discharge O4 for the commit it keeps; nothing prunes them yet (see Consequences, Negative).
- `delete_bookkeeping_ref` (`git/ref_advance.py`) deletes without compare-and-swap today; a caller that uses it on these namespaces moves to the compare-and-swap delete when it binds.

### Deferred sites (named, not bound by this amendment)

- **Allocation recut**: the removal of a leftover lane worktree after a planning-commit merge conflict (`lanes/worktree_allocator.py`, `guarded_worktree_remove(retain=True)` with its `--force` default).
- **Resume recovery's raw `git reset --hard HEAD`** on the repository root checkout, the coordination worktree, a Mission worktree and a lane worktree (`consolidation/resume_recovery.py`).
- **The coordination teardown's worktree removal and branch delete** (already compare-and-swap; S10 left its routing to S5, and S5 keeps S10's codes and exits). Core ADR 2026-11-06-4 (C-1) removes its worktree leg when the coordination worktree is retired.
- **Releasing a short-lived lane checkout** (S3, already in this ADR's Scope): bound by the lease follow-up Mission.

### Consequences

**Positive.** One proof list covers every Mission lane removal; a kept lane is a report, not a traceback; pull-request landings clean up without waiting for the merge.

**Negative.** Off Linux, consolidation keeps every lane worktree until the prune runs where a probe can answer, or the operator removes it. The local form trusts a gate-passed tip recorded by the same run, so a resumed run must re-read it from the consolidation record, never recompute it.

**Residuals.** Those of the original record stand. A lane whose tip the pushed pull request head absorbs, but whose pull request is later closed unmerged, has been removed; its tip survives under the kept refs (O4, O8).

### Confirmation

- `tests/consolidation/test_lane_remover_guard_binding.py` (Mission WP16): the local form accepts the gate-passed tip and refuses a moved target; `PROCESS_PROOF_UNAVAILABLE` keeps and reports with exit 0; a residue-only lane is removed without `--force`; the target and the pull request head branch are never deleted.
- `tests/acceptance/test_pr_mode_lane_cleanup.py` (WP16): lanes absorbed by the pushed head are removed before the merge; unpushed lanes are kept and reported.
- `tests/specify_cli/workspace/test_landed_worktrees_mission_lane_prune.py` (WP16): the prune backstop removes consolidated Mission lanes and keeps them while a consolidation record is active.
- `tests/consolidation/test_lane_cleanup_module.py` and `tests/consolidation/test_lane_cleanup_kept_report.py` (WP15): the order, the kept report, and the lane-tip ref cleared only after a confirmed delete.
- `tests/architectural/test_destructive_op_routing.py`: the routing pins name the lane-cleanup module and the scratch exemption.
