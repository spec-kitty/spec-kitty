# Research: Gates that work in teammate clones and ephemeral reviewers


# Findings: gates that assume local, pushed, target-anchored state

Five issues found while running real Missions on 4.0.0rc9 in cloud sessions:
#7809, #5936, #7806, #7802, #7808. #5936 already has a fix (PR #7804), which this
work treats as the baseline. This page records the code grounding, the shared root
causes, a proposed fix per issue, and the order.

## Shared root cause

Four of the five issues come from one assumption. The tool assumes the state it
needs is a **local** ref, already **pushed** where needed, and **anchored on the
target branch**. A teammate's clone, an ephemeral reviewer container, and a
default Mission's topic branch each break one part of that assumption.

| Issue | What the tool assumes | What the clone or container actually has |
|-------|------------------------|------------------------------------------|
| #5936 (PR #7804) | the coordination branch is a local head | only `refs/remotes/<r>/<coord>` |
| #7806 | the lane branch is a local head | only `refs/remotes/<r>/<lane>` |
| #7802 | the approval stamp (local lane head) reaches origin | a review-made merge that is never pushed |
| #7809 | planning-lane work is on the target branch | work on the Mission topic branch, where placement put it |
| #7808 | (unrelated) every `#NNN` with 2 to 6 digits is an issue | a CSS hex colour such as `#000000` |

## #7808: hex colour read as issue #0

- `src/specify_cli/tasks/issue_matrix.py:168`: `_GH_ISSUE_PATTERN` hash arm `#(\d{2,6})`.
  `#000000` and `#000` match and become issue `0`; `#111111` becomes `111111`.
  Reproduced through `issue_numbers_in_text`.
- **Fix:** in the one pattern definition, the hash arm no longer accepts a leading
  zero (`#([1-9]\d{1,5})`). No GitHub issue is written with a leading zero, so
  `#0`, `#000` and `#000000` never become references. On top of that, an all-digit
  3-, 4-, 6- or 8-digit literal in a colour context (a CSS colour property on the
  line: `color`, `colour`, `background`, `fill`, `stroke`, `border`, and similar) is
  filtered in `detect_issue_references`, which is the single Python-side filter
  that already drops cross-repo URLs. No ADR is needed.

## #7806: lane branch exists only as a remote-tracking ref

- `src/specify_cli/cli/commands/agent/workflow.py:2719`: the review claim
  (`workflow_executor.review_claim_transition`, `:2149-2160`) runs the lane sync
  `lanes/lifecycle_sync.py:83 sync_lane_after_coordination_commit` **before**
  `_prepare_review_workspace` (`workflow.py:2734`). That later step is the one that
  would cut the branch from origin's `CREATE_FROM` ref.
- `lifecycle_sync.py:147-158` opens the lane checkout with `create_branch_from=None`,
  so `lanes/lane_checkout.py:288-300 _refuse_detached` rejects a lane that has no
  `refs/heads/<lane>`: "is not a local branch".
- **Fix:** reuse PR #7804's owning-remote materialisation. Generalise
  `ensure_coord_branch_local_head` / `coord_branch_tracking_ref`
  (`coordination/surface_resolver.py`, PR #7804) into one branch-neutral helper,
  and keep the two coordination names as thin delegates. The helper resolves the
  remote with `kernel.git.remote.resolve_remote`, probes the tracking ref locally,
  and runs `git branch --track --end-of-options <b> <ref>`. The lane sync calls it
  before it opens the checkout, and still fails closed when no ref exists.
  `_create_review_worktree` (`workflow.py:2523`) gets the same explicit tracking.
  Write-side only, no remote contact. No ADR is needed: this follows #7804.
- **Dependency:** stack on PR #7804. Rebase onto `main` once #7804 lands.

## #7802: approval stamp names the reviewer's own unpushed merge

- `lanes/auto_rebase.py:1039-1042`: every review claim runs
  `git merge --no-edit --no-ff --no-commit <coord>` into the local lane and
  concludes it. Because the claim commit has just landed on the coordination
  branch, this always creates a local merge commit.
- `status/lane_head.py:211-230 _branch_head` reads the local `refs/heads/<lane>`.
  `status/transition_pipeline.py:242` stamps it as `policy_metadata.lane_head`.
  No upstream or pushed check exists anywhere.
- `consolidation/approved_bound.py:496-511 stamp_refusal` runs
  `merge-base --is-ancestor <stamp> <local lane>`. In the consolidating clone the
  stamp object does not exist, so it refuses with `APPROVAL_STAMP_NOT_ON_LANE`.
- The CLI never pushes a lane or a status commit. The only `git push` calls are
  `consolidate --push` (`phase_finalize.py:47`, `orchestrator_api/consolidation.py:814`).
  `kernel/git/remote.py:3` puts push outside the remote-contact owner (FR-015, #5858).
- **Options** (operator decision, below):
  - **A.** The approval refuses when the lane has a remote-tracking ref and the
    stamp is not reachable from it. The remedy prints the push command and a
    `git ls-remote` check. This is a local read with no remote contact. A lane
    that was never pushed (solo, no remote) passes, as in the origin gate.
  - **B.** The approval path pushes the lane fast-forward itself.
  - **C.** Stamp the commit the review merge was made on, so the stamp never
    depends on the tool's own merge.
  - **D.** Warn only.
- A and C each need an amendment to ADR `2026-10-04-5`: A adds a refusal code,
  C changes what the stamp names. B needs a ruling on the push boundary
  (FR-015, #5858) and an ADR.

## #7809: planning-artifact WP judged against the target branch

Two rules disagree about where planning work lives:

- **Writes and the review range:**
  - `mission_runtime/resolution.py:1087-1101 default_mission_primary_ref` and
    `:2071-2080 resolve_placement_only` send a default Mission's PRIMARY
    artifacts to `meta.mission_branch` (the topic branch, which is also the
    coordination branch) until it lands.
  - `review/wp_range.py:529-545` already uses that rule.
- **Evidence and consolidation:** `lanes/branch_naming.py:615` maps `lane-planning`
  to `target_branch` for every topology, and every evidence or consolidation reader
  follows it:
  - `consolidation/wp_evidence.py:144-156 lane_evidence_window`: tip = target,
    which gives `IMPLEMENTATION_MISSING` at `tasks_move_task.py:1314`.
  - `consolidation/reconciliation_authorship.py:748`, `reconciliation_claim.py:525`,
    `reconciliation_canceled.py:258/385`: the planning walk ends at the target.
    `single_branch_landing.py:247 authorship_window` covers protected
    `single_branch` only.
  - `consolidation/forecast.py:491-496`: `landing_refs` include `mission_branch`,
    so the topic-branch commits are scanned and no approved WP covers them. The
    verifier (`reconciliation_verifier.py:150`) then emits
    `UNATTRIBUTABLE_CONTENT_FORECAST`.
- **Fix:**
  - One pure helper, `planning_lane_write_branch`, in
    `mission_runtime/resolution.py`. It is defined as the placement rule
    `resolve_placement_only`'s PRIMARY ref.
  - Route the evidence window, the claim's planning walk (base =
    `merge-base(target, write branch)`, non-merge commits, bounded by the
    pre-mutation coordination tip) and the review range through it.
  - Explicit-topology Missions keep the target, because that is where placement
    writes for them.
  - `lane_branch_name` keeps its target alias: lane_head, the allocator and the
    forecast rely on it.
- Needs an amendment to ADR `2026-10-04-5` (owned-file evidence window, Amendment
  2026-10-29), and a cross-reference in ADR `2026-11-08-2`, which already names the
  planning write branch for the review range.

## #5936 (baseline, PR #7804, not redone)

PR #7804 is reviewed and approved. It conflicts with PR #7796 (#5287) in three
files, and its body lists the five changes that whichever PR lands second needs.
This work builds on its resolver (#7806) and does not reference #5936 in its
Closes lines.

## Proposed order and work packages

1. **WP01, #7808:** pattern fix. Independent and small.
2. **WP02, #7806:** branch-neutral materialisation helper (generalised from
   #7804), used by the lane sync and the review worktree cut.
3. **WP03, #7802:** depends on WP02 (same review path). Implements the option the
   operator chooses, plus the ADR `2026-10-04-5` amendment.
4. **WP04, #7809:** `planning_lane_write_branch` and its three readers, plus the
   ADR amendment.

WP02 and WP03 touch the review lane path and run in sequence. WP01 and WP04 are
independent of both.

## Squad corrections (architect-alphonso + researcher-robbie, 2026-11-22)

- **#7808:** there are three hash-number patterns, not one: `issue_matrix.py:168`, and two copies in `issue_reference_discovery.py` (`:347` and `:354`). All three need the no-leading-zero rule. Put the colour filter in `_matched_issue_number` (`issue_matrix.py:192`), because `issue_numbers_in_text` goes through it too. Match only the CSS declaration form (`prop: #hex`): a keyword anywhere on the line would drop real 4-digit references (`#RGBA` looks like `#7808`).
- **#7806:** do not create the branch in `lifecycle_sync`. It serves every sync point and bypasses the destroyed-lane guard (`worktree_allocator.py:500-523`). Create it in `_reconcile_review_lane` (`workflow.py:2485`), right after `plan_review_lane` refreshes origin. Refuse `DESTROYED_LANE` when a lane-tip ref is not an ancestor of the tracking ref. A third copy of the tracking-ref probe exists (`workspace/context.py:1228 resolve_lane_base_ref`). Put one kernel-level helper, `kernel/git/`, in charge (local ref write, no remote contact), and route all three callers through it.
- **#7802:** option A (refuse an unpushed stamp) would refuse almost every remote review, because the review claim always creates a local `--no-ff` merge. The squad recommended the dual stamp (C′): keep `lane_head`, add `lane_head_presync`, recorded from the auto-rebase report. The bound already drops merge commits (`approved_bound.py:465-478`, `write_branch_bound.py:155`), so it stays sound. `agent action review` only claims; the stamp is written at the later `move-task --to approved`. Consolidate can tell "stamp object absent" apart with `git_probes.commit_in_clone` (`:444`).
- **#7809:** open issue #7759 shows the opposite shape (planning work committed on the target). Pointing the gates only at the topic branch would break #7759 again. A topic-branch walk would also pull coordination-branch merges into the planning claim.

## Operator rulings (2026-11-22, recorded as Decision Moments)

| Slot | Ruling |
|------|--------|
| `specify.planning.evidence_home` | **Docs WPs get a lane** (my recommendation was "either branch") |
| `specify.scope.fold_7759` | **Fold #7759 in** |
| `specify.approval.stamp_7802` | **Dual stamp** |
| `specify.review.lane_materialize_7806` | **Auto-create, stack on PR #7804** |
| `specify.planning.lane_rule` | **Normalise kind**: finalize rewrites the docs WP to `code_change` in lane topologies |
| `specify.planning.mixed_wp` | **Refuse, split it** |
| `specify.planning.settlement_count` | **Count it** (my recommendation was "don't count") |

The #7809 sections above describe the pre-ruling design. The rulings above supersede them.
