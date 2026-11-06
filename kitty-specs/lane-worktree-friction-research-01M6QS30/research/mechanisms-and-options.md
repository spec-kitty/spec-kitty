# Mechanisms and options: the lane / worktree execution model

Analyst lens: architect (mechanisms, seams, trade-offs, migration cost). Read-only.
Evidence date: 2026-11-06, `HEAD` of the `docs/lane-worktree-friction-research` checkout (shallow
clone; history reaches 2026-08-06, so the churn window is complete).

Fixed constraint (operator ruling 2026-11-06): the resolved status surface is the only source of
truth; a lane worktree's own status files never count (#6466, #6884).

---

## 1. Mechanisms

### 1(i) Copies of the same state and who reads which copy

**Checkouts that can hold Mission state at the same time** (one Mission of topology
`lanes_with_coord` with N code lanes):

| # | Checkout | What it holds | How it is created |
|---|----------|---------------|-------------------|
| 1 | Repository root checkout | `kitty-specs/<slug>/` (meta.json, lanes.json, tasks/, and `status.events.jsonl` for non-coord topologies), `.kittify/` (config, `workspaces/*.json` lane contexts, `runtime/merge/<id>/state.json`, migration ledger) | the clone |
| 2 | Coordination worktree `.worktrees/<slug>-<mid8>-coord` | the COORD-partition copy of `status.events.jsonl` / `status.json` and other lifecycle artifacts | `CoordinationWorkspace.resolve` (`src/specify_cli/coordination/workspace.py:303-343`, `git worktree add` at :332) via `materialize_coord_surface_for_write` (`coordination/surface_resolver.py:96`, callers `coord_seed.py:933-942`, `implement_recover.py:124-131`, `_coordination_doctor.py:1490-1504`) |
| 3..N+2 | Lane worktrees `.worktrees/<slug>-lane-<id>` | a FULL checkout of the lane branch: its own committed `kitty-specs/<slug>/` (meta, lanes.json, tasks, and the status log as it was at the lane's cut, unless sparse-excluded), its own committed `.kittify/` | `allocate_lane_worktree` (`lanes/worktree_allocator.py:1051`; `_create_lane_worktree` :2102-2112, `_recover_lane_worktree` :2121-2138), `lanes/lifecycle_sync.py:135-139`, the review path `_create_review_worktree` (`cli/commands/agent/workflow.py:2298-2322`) |
| + | Merge scratch worktree `.kittify/runtime/merge/<id>/workspace` | detached checkout of the target | `consolidation/workspace.py:180` |
| + | Temporary detached worktrees | lane consolidation, mission-number bake, review baseline | `lanes/consolidation.py:1279,1358`, `consolidation/mission_number/bake.py:209,562`, `review/baseline.py:291` |

So a single Mission's status log can exist as: the coord worktree's working-tree file, the coord
branch's committed blob, the repository root checkout's file (primary topologies, and the
create-to-first-write window), and one stale committed copy per lane branch/worktree. Only the
coord-topology lane worktrees exclude it, via sparse checkout
(`register_lane_sparse_checkout`, `coordination/workspace.py:416`, called from
`worktree_allocator.py:1850-1873`); a `lanes` mission's lane worktrees carry the file. The copies
flow back together on integration, which is why lane auto-rebase carries a dedicated
`status.events.jsonl` conflict merger (`lanes/auto_rebase.py:357-391` →
`status/event_log_merge.py:187 merge_event_log_texts`) and a coordination-artifact take-theirs
rule (`auto_rebase.py:235, 394`). Under the operator ruling, every one of these lane copies is
noise that the code still has to carry, merge and guard.

**Shared through the git common dir** (one copy, not a divergence risk): refs (`refs/heads/*`,
`refs/spec-kitty/lane-tip/*`, `refs/spec-kitty/discarded/*`), hooks
(`policy/lane_tip_recorder.py:90-112 _resolve_hooks_dir/_hooks_path_scope`), and the write locks
(`<git-common-dir>/spec-kitty-locks/`, ADR 2026-10-22-1 D-2).

**Readers by medium.**

Working-tree readers (read a file in some checkout):
- `MissionStatus.load` → `_resolve_read_dir` (`status/aggregate.py:194-263, 291-330`) → the
  coord worktree's file, or the repository root checkout's file until the coord worktree exists.
  Used by `agent status` (`cli/commands/agent/status.py:139-188, 227-243`) and every
  `MissionStatus` consumer.
- `resolve_status_surface[_with_anchor]` (`coordination/surface_resolver.py:1209-1300`) returns a
  filesystem path; on an EMPTY coord root it quietly falls back to the PRIMARY checkout file for
  `coord` and warns for `lanes_with_coord` (docstring :1265-1285).
- `runtime/next/committed_authority.py:1-25`: deliberately reads the PRIMARY working tree, "NOT
  a git-ref-level read (no commit SHA, no `git show`)", "because coordination checkouts are torn
  down after".
- lanes.json / meta.json: `placement_seam(...).read_dir(LANE_STATE|PRIMARY_METADATA)` on the
  repository root checkout (`workspace/context.py:1191-1196`; `status/aggregate.py:507, 726`).
- `.kittify/workspaces/*.json` lane contexts (`workspace/context.py:307-427`), which can shadow
  `lanes.json`; the resolver orders arms specifically "so a stale context record can never
  shadow" the repo-root lane (`workspace/context.py:1164-1172`).
- write-checkout occupancy for `single_branch` (`lanes/checkout_occupancy.py:1-40`).

Git-ref readers (read a committed blob or a ref):
- `consolidation/done_bookkeeping.py:610` (`git show <target>:<events>`), `:692
  _durable_done_wps_on_coordination_ref`; `coordination/coherence.py:630`.
- `coordination/status_surface_guard.py:45-65` compares the coord worktree file against its own
  `HEAD` blob (`kernel.git.blob_at`), i.e. a guard that exists because the two can diverge
  (`COORD_STATUS_SURFACE_DIVERGED` / `_UNREADABLE`).
- `consolidation/run_state.py:427-438 _status_surface_ref` uses `resolve_placement_only(...,
  STATUS_STATE).ref`, a ref-oriented answer.
- Every consolidation gate (section 1(iv)) and the lane-head probe
  (`status/lane_head.py:103-108`, `refs/heads/<branch>`), lane tips (`lanes/lane_tip.py:66-140`).

**How many status-surface resolution paths?** One *body* exists —
`resolve_status_surface_with_anchor` (`coordination/surface_resolver.py:1256`), with
`resolve_status_surface_dir_or_typed_error` (`missions/_read_path_resolver.py:1242`) as the
shared delegator — but there are at least **eight adapters with different semantics on the same
coord states** (EMPTY / UNMATERIALIZED / DELETED / meta-missing):

1. `resolve_status_surface` itself: EMPTY → primary fallback (warn only for lanes_with_coord).
2. `mission_runtime/resolution.py:1626 _resolve_status_surface_dir`: meta missing → primary
   fallback via `candidate_feature_dir_for_mission`.
3. `mission_runtime/resolution.py:1539 _resolve_status_surface_dir_owned`: a separate owned arm
   that re-derives via `coord_feature_dir` + `probe_coord_state` and fails closed on EMPTY,
   UNMATERIALIZED and NONE.
4. `PlacementSeam.read_dir` vs `PlacementSeam.write_dir` (`resolution.py:2460, 2527`): read
   degrades to primary; write materializes/seeds (the #5113 single-home fix; `accept.py:194-215`
   documents a write that leaked into the primary via the read projection).
5. `MissionStatus._resolve_read_dir` (`status/aggregate.py:291`): keeps primary authoritative
   until the coord worktree exists on disk (a shape-only check).
6. `committed_authority` (`runtime/next/committed_authority.py`): PRIMARY working tree by design.
7. Consolidation's per-run authorities: `entry_preflight.py:733 _resolve_run_status_dir` (write
   accessor), `phase_advance.py:286 _resolve_run_status_surface`, `coord_strand.py:68`
   (WORK_PACKAGE_TASK read), `run_state.py:427` (ref).
8. Command-local helpers: `accept.py:194 _coord_status_feature_dir`,
   `agent/mission_finalize_lanes.py:68`, `agent/finalize_status_surface.py`,
   `migration/wp_status_backfill.py:79 coordination_surface_is_live`,
   `migration/backfill_runtime_state.py:1547`.

Counts: 62 call sites of `resolve_status_surface*` across 26 files; 12 direct
`coord_feature_dir(` compositions across 7 files; 17 `candidate_feature_dir_for_mission(` calls;
285 calls of `get_main_repo_root` / `resolve_canonical_root` (the "which checkout am I in"
normalisation tax). Conclusion: there is one resolver body, but no single resolver *contract*:
the meaning of "the status surface" depends on the caller's fallback rule, and three of the
adapters return a different file than the others in the EMPTY / pre-materialisation window.

### 1(ii) Lifecycle ownership

- **Lane worktree creation/reuse:** `allocate_lane_worktree` with a closed route set
  `FRESH_COORD | FRESH_LEGACY | REUSE | CRASH_RECOVERY` (`worktree_allocator.py:80-86`); it also
  merges the recorded planning commit (`:1517`) and each dependency lane's tip
  (`_merge_dependency_lane_tips`, `:1745-1760`) *inside the worktree*. Other creators:
  `lifecycle_sync.py:135-139` (re-adds a missing lane worktree at a sync point), the review path
  (`agent/workflow.py:2298-2322`), and the legacy `core/worktree.py:94 create_wp_workspace`.
  Contexts are persisted to the repository root (`worktree_allocator.py:906
  persist_lane_context`). ADR 2026-01-26-9 fixed cleanup "at merge, not eager".
- **Coordination worktree:** created lazily on first COORD write
  (`CoordinationWorkspace.resolve`), reused with an ancestry check, torn down via
  `CoordinationWorkspace.teardown` (`coordination/workspace.py:344-376`).
- **Destruction:** only these paths remove Mission worktrees:
  `consolidation/phase_teardown.py:868-898 _remove_lane_worktrees` and `:739
  _teardown_coordination_triple` (gated on retention, `core/paths.py:1006-1134`
  `teardown_coordination = delete_branch and remove_worktree`);
  `orchestrator_api/consolidation.py:426`; Mission discard
  (`cli/commands/mission_type.py:622, 700 → :1285`); the allocator's own conflict rollback
  (`worktree_allocator.py:1441`). All go through `guarded_worktree_remove`
  (`git/destructive_guard.py:334`).
- **"The merge outlives the session."** When the Mission lands through a pull request merge,
  `consolidate` never runs, so none of the destroyers above fire. `accept --mode pr
  --merge-commit` (`cli/commands/accept.py:448-481`) validates evidence but does not tear down.
  The new landed-worktree prune (#7173, `workspace/landed_worktrees.py:1-80`) explicitly refuses
  Mission branches: rule 5 → `mission_owned`, "consolidate owns its worktree" (`:20, :375, :463`).
  Result: after an out-of-CLI landing, lane worktrees, lane branches, the coord worktree and
  branch, the `.kittify/workspaces` contexts and the lane-tip refs have **no owner that will run**.
  They linger until an operator runs `consolidate` against an already-landed Mission, discards
  the Mission, or deletes by hand — and deleting by hand is exactly what trips `DESTROYED_LANE` /
  `LANE_WORK_TIP_UNKNOWN` on any later `implement` (topology glossary,
  `docs/context/topology.md`, "Lane work tip").
- `spec-kitty upgrade` writes only the repository root; Mission worktrees "receive it by
  integration" and are skipped (`upgrade/worktree_selection.py:1-15, 164`;
  `upgrade/autocommit.py:1-25`, #5457). So a long-lived lane worktree runs on stale committed
  `.kittify/` and stale charter content until its branch integrates `main`; 114 of 136 migration
  modules still default `runs_on_worktrees = True` (`upgrade/migrations/base.py:225-227`; 22 set
  False).

### 1(iii) Machinery that exists because branches/checkouts can be deleted or rewritten under a live checkout

- `refs/spec-kitty/lane-tip/<branch>` (`lanes/lane_tip.py:1-16`): "so a destroyed lane's
  committed work stays detectable... after its branch, worktree and WorkspaceContext record are
  all gone"; written by `record_tip` (`:66`) at spec-kitty record points and by POSIX
  `post-commit` / `post-rewrite` hooks (`policy/lane_tip_recorder.py:253-296`, active check
  `:214`), with hook-path scope rules (`:112-172`). Squash-absorption via `git merge-tree
  --write-tree` (`lane_tip.py:180-270`).
- The destroyed-lane decision table (`worktree_allocator.py:417-520`) and its two error types
  `DestroyedLaneError` (`:197`) and `LaneWorkTipUnknownError` (`:280`).
- `CRASH_RECOVERY` route (worktree dir gone, branch alive) and `lifecycle_sync`'s re-add.
- Workspace-context tombstones committed at teardown (`phase_teardown.py:926`).
- `refs/spec-kitty/discarded/*` in the landed prune (`landed_worktrees.py:58-75`).
- Behind-own-HEAD recovery on resume: `git reset --hard HEAD` over four checkout roles
  (repository root, coord, mission, lane worktree) with a residue proof
  (`consolidation/git_probes.py:219-290`, `consolidation/resume_recovery.py:321-397`,
  `executor.py:1030`), plus `resync_checkouts_to_tip` after rollback (`git/ref_advance.py:875`).
  These exist because a ref moved while a checkout of it stayed on disk.
- `COORD_STATUS_SURFACE_DIVERGED` (`coordination/status_surface_guard.py:45`) — worktree file vs
  its own HEAD.

### 1(iv) Consolidation gates: branches vs checkouts

| Gate / mechanism | Reads | Needs a persistent lane checkout? |
|---|---|---|
| Approval bound `check_lane` (`consolidation/approved_bound.py:465-500`) | `commits_in_range(repo_root, claim_base, lane_tip)`, `sha_reachable_from(stamp, lane_tip)` — refs only | No |
| `lane_head` stamp (`status/lane_head.py:61-108`) | `git rev-parse refs/heads/<lane>` | No |
| Lane recheck at gate (`consolidation/phase_gate.py:92`, `reconciliation.py:2240 lane_tips_moved_refusal`) | live lane tip refs vs validated tips | No |
| Claim build (`reconciliation.py:1594 build_approved_wp_set`, `:2145 _approved_bound_verdict`) | event log + refs | No |
| Closed world / mixed-lane attribution (`consolidation/wp_attribution.py:112, 242`; `reconciliation.py:978`) | lane first-parent spine + stamps | No |
| Squash blob attribution (`reconciliation.py:1271`) | `authored_blobs` per lane ref | No |
| Line attribution (`consolidation/line_attribution.py`) | `git blame` on refs | No |
| Owned-file evidence (`consolidation/wp_evidence.py`) | refs (survives pruned lanes via `--merge-commit`) | No |
| for_review gate (`lanes/for_review_gate.py:238`) | commits on the lane branch since claim base | No |
| Lane consolidation merge itself | detached temp worktrees (`lanes/consolidation.py:1279,1358`; scratch `consolidation/workspace.py:180`) | No — already ephemeral |
| Dirty-checkout preflight (`consolidation/entry_preflight.py:277 _assert_mission_checkouts_clean`) | working trees of coord/mission/lane worktrees | Exists only *because* they exist |
| Resume recovery / rollback resync (above) | working trees | Exists only because they exist |
| Lane auto-rebase (`lanes/auto_rebase.py`, `lifecycle_sync.py`) | rebases in the lane worktree | Yes (could run in a temp worktree) |
| Dependency-lane merge at allocation (`worktree_allocator.py:1745`) | merges in the lane worktree | Yes (could run in a temp worktree) |
| Destroyed-lane guard, lane-tip refs | branch + worktree + context | Largely mooted if the branch, not the checkout, is the unit |

Central finding: **every integrity gate is ref-based.** The approval bound, closed world, blob and
line attribution, lane recheck and owned-file evidence read lane branches, `lane_head` stamps and
git ancestry, never a lane checkout. The machinery that reads lane *checkouts* is hygiene for the
checkouts themselves (dirty preflight, resume reset, resync, divergence guard, destroyed-lane
recovery). Lanes-as-branches survive; persistent checkouts are what generate the extra surface.

---

## 2. Size of the model

Commands run from `/home/user/spec-kitty`:

```
for d in lanes coordination workspace consolidation; do
  find src/specify_cli/$d -name '*.py' | wc -l; cat $(find src/specify_cli/$d -name '*.py') | wc -l; done
git log --since=2026-08-06 --oneline -- <paths> | wc -l      # and | grep -ci fix
grep -rhoE '"[A-Z][A-Z0-9]+(_[A-Z0-9]+){1,}"' lanes coordination workspace consolidation policy/lane_tip_recorder.py | sort -u
```

| Package | Files | LOC | Commits since 2026-08-06 | of which subject contains "fix" |
|---|---|---|---|---|
| `src/specify_cli/lanes/` | 22 | 12,319 | 152 | 88 |
| `src/specify_cli/coordination/` | 23 | 14,362 | 143 | 81 |
| `src/specify_cli/workspace/` | 6 | 2,668 | 26 | 11 |
| `src/specify_cli/consolidation/` | 42 | 27,618 | 234 | 157 |
| `policy/lane_tip_recorder.py` | 1 | 296 | (in total) | |
| **Total (deduplicated commits)** | **94** | **57,263** | **500** | **315 (63%)** |
| for comparison: all of `src/` | | | 3,507 | 2,035 (58%) |
| `src/mission_runtime/` (placement) | 14 | 6,473 | 54 | |
| `src/specify_cli/upgrade/` | | | 255 | |

So 14% of all `src/` commits in the window touched these four packages, at a higher fix ratio
than the repository average. Tests carrying the model: `tests/lanes` 75 files / 22,963 LOC,
`tests/coordination` 37 / 15,542, `tests/consolidation` 142 / 56,827, `tests/specify_cli/{lanes,
coordination,workspace}` 75 / 22,561; 1,398 test files mention "worktree".

Error/refusal codes: 157 distinct upper-snake string constants in those packages; about 45 name a
lane, worktree, coord, checkout or surface condition (e.g. `DESTROYED_LANE`,
`LANE_WORK_TIP_UNKNOWN`, `WRITE_CHECKOUT_{DIRTY,OCCUPIED,WRONG_BRANCH}`,
`COORD_STATUS_SURFACE_{DIVERGED,UNREADABLE}`, `COORDINATION_WORKTREE_{BRANCH_MISMATCH,UNMATERIALIZED}`,
`COORD_WRITE_SURFACE_UNMATERIALIZED`, `COORD_SEED_*` (6), `COORD_MOVED_AFTER_LANDING`,
`COORD_LATE_PROJECTION_REFUSED`, `COORD_TEARDOWN_KEPT_ONLY_COPY`, `PROJECTION_TEARDOWN_ABORTED`,
`BOOKKEEPING_WORKTREE_MISSING`, `BRANCH_IN_OTHER_WORKTREE`, `LANE_AUTO_REBASE_FAILED`,
`DEPENDENCY_LANE_MERGE_CONFLICT`, `WORKTREE_REMOVE_FAILED`, `WORKTREE_REGISTRY_UNAVAILABLE`); some
are verdict reasons rather than refusals (`MAIN_WORKTREE`, `CURRENT_WORKTREE`). Roughly 25 of the
45 are coord-worktree-specific.

Usage signal (dogfooding, `kitty-specs/*/meta.json` created since 2026-08): `single_branch` 179,
`lanes` 82, `coord` 53, `lanes_with_coord` 5, no stored topology 132 (read as `lanes`). The
richest topology, which most of the coord machinery serves, is the rarest in practice.

---

## 3. Options

Interaction baseline with the Java write service (ADR 2026-10-22-1): one service per git common
dir (D-2), so all worktrees share one writer; the service "resolves the write location: which
partition, worktree and branch" (D-3) and commits status in its unit of work (D-4); only a file
adapter ships (D-6), and D-6 lists the git-committed ledger, file-based merge semantics and
`lane_head`/ancestry gates as reasons a non-file adapter needs its own ADR. **The service removes
concurrent-writer races; it does not remove read-side divergence**: readers (section 1(i)) still
read whichever checkout file their adapter picks, and the service still writes into a worktree
file. Until reads also go through one ref-addressed source, "which copy" stays a question.

### (a) Tighten the current model

- **What:** one status-surface contract (single function, single fallback rule, the
  `write_dir` semantics everywhere: no read-side primary degrade; reads of a committed log go to
  the status ref, not a working tree); explicit lifecycle owner for Mission worktrees after an
  out-of-CLI landing (extend #7173's prune with a `mission_owned → landed` proof using the PR
  merge commit, or make `accept --mode pr` the teardown point); prune lane worktrees by proof
  (absorbed tip on target) rather than by command.
- **Benefits:** no topology change; keeps parallel multi-agent execution; gates untouched;
  smallest blast radius per step.
- **Costs:** the 57k LOC surface stays; the ~45 codes stay; each fix is another adapter rule,
  which is how the eight adapters arose. Converging adapters 1-8 touches `mission_runtime`
  (shrink-only ledgers), `status/aggregate.py`, `runtime/next/committed_authority.py` and
  consolidation's run authorities.
- **Breaks:** nothing structurally; behaviour changes in the EMPTY/UNMATERIALIZED window
  (fail-closed instead of primary fallback) will surface new refusals.
- **Java service:** complementary; the service becomes the single writer, the single resolver
  becomes its request context (open question 2).
- **Verdict:** necessary regardless of direction (the resolver convergence and the post-PR
  owner are prerequisites for b/c/d too), but not sufficient.

### (b) Lanes stay branches; checkouts become ephemeral

- **What:** a lane is `refs/heads/kitty/mission-…-lane-<id>` plus its `lane_head` stamps and
  status events. A command that needs to build or edit code materialises a worktree for its own
  duration (the pattern consolidation already uses: `consolidation/workspace.py:180`,
  `lanes/consolidation.py:1279`); agent sessions get a checkout leased for the session and
  removed (or detached) at `for_review`/session end once the tip is committed and recorded.
- **Survives:** every integrity gate in 1(iv) (all ref-based); `lane_head` stamps; lane
  computation and parallelism (lanes are still separate branches); `lanes.json`.
- **Retires or shrinks:** the persistent-checkout hygiene: dirty-checkout preflight for lane
  worktrees, lane-worktree resume reset, `resync_checkouts_to_tip` for lanes, the `REUSE` /
  `CRASH_RECOVERY` routes, the `.kittify/workspaces` context records (path is derivable from
  `predict_lane_worktree`, `worktree_allocator.py:687`), the "merge outlives session" problem for
  lanes (no checkout to strand), most stale-`.kittify/` drift in lanes. Lane-tip refs become
  *more* important (the branch is the only durable thing), but the hook could be replaced by
  recording at lease release.
- **Costs / migration:** `worktree_allocator.py` (2,180 LOC) reshaped into a lease; dependency
  merge and auto-rebase move to temp worktrees; agent prompts/skills that `cd` into
  `.worktrees/<slug>-lane-<id>` across turns (upstream templates in `spec-kitty-open-packs`)
  must accept a lease handle; `resolve_workspace_for_wp` gains "materialise if absent" (it
  already tolerates non-existent paths, `workspace/context.py:798`). Upgrade migration: drop
  existing clean lane worktrees whose tip is recorded; keep dirty ones.
- **Breaks:** an agent that leaves uncommitted work at session end loses the lease guarantee
  (must commit-or-refuse at release); long-running IDE sessions pointed at a lane path; review
  worktree reuse. Uncommitted work becomes the main new risk.
- **Java service:** status writes no longer need any lane path; with lanes ephemeral, only the
  coord worktree and the repository root remain as status-bearing checkouts.

### (c) `single_branch` by default; lanes opt-in

- **What:** create-time default becomes `single_branch` (today `coord` on primary, `lanes`
  elsewhere: `cli/commands/agent/mission_create.py:377`); lanes require `--topology lanes` with
  a reason (parallel agents on disjoint owned files).
- **Benefits:** matches observed usage (179 of 451 recent Missions already `single_branch`);
  removes lane and coord worktrees from the common path at once; `WRITE_CHECKOUT_*` refusals are
  the only checkout codes on that path; status surface is the write checkout (no coord copy).
- **Costs:** parallelism becomes opt-in; serial WPs in one checkout make the approval bound
  coarser (single_branch missions are not stamped or bounded — a CLAUDE.md-listed residual of
  #5668), so the review-integrity story for single_branch must be closed first; protected
  targets need the minted mission branch (`docs/context/topology.md`, "Mission branch").
- **Migration:** small: a default flip plus doc/template changes; existing Missions keep their
  stored topology (ADR 2026-06-22-1 SSOT).
- **Breaks:** nothing for existing Missions; multi-agent parallel workflows must opt in.
- **Java service:** simplest case (one checkout, one log).

### (d) Drop lane worktrees altogether

- **What:** retire code lanes (LANES / LANES_WITH_COORD); every Mission runs in a write checkout
  or owned checkout.
- **Benefits:** retires the largest share of `lanes/` (allocator, auto-rebase, lane_tip,
  recorder, frozen membership, lane consolidation) and the mixed-lane closed-world machinery.
- **Costs / breaks:** loses parallel multi-agent execution, which is the product's stated reason
  for lanes (ADR 2026-04-03-1 drivers: "safe parallelism"); invalidates the 2x2 topology and its
  migrations; consolidation's per-lane attribution, closed-world and canceled-lane axes lose
  their subject, so either they are removed (large test churn: 56,827 LOC in
  `tests/consolidation`) or kept dormant. Highest migration cost, highest product cost.
- **Verdict:** (b) gets most of the benefit of (d) while keeping parallelism.

### (e) Status off the checkout: a ref-addressed status store

- **What:** status events are committed to the status ref (coordination branch, or a
  `refs/spec-kitty/status/<mission_id>` ref) with git plumbing (`hash-object`, `commit-tree`,
  `update-ref` with compare-and-swap, the discipline `git/ref_advance.py` already has) and read
  with `git show <ref>:<path>`. No checkout is the status surface; there is nothing to diverge.
- **Benefits:** makes the operator ruling true by construction (#6466/#6884 class closed); the
  coord *worktree* (not the coord branch) disappears, taking `COORD_STATUS_SURFACE_*`,
  `COORDINATION_WORKTREE_*`, `COORD_WRITE_SURFACE_UNMATERIALIZED`, most `COORD_SEED_*`, sparse
  checkout registration and the EMPTY/UNMATERIALIZED adapter rules with it. Reads converge on one
  ref read (the read service already "pulls the committed ledger", ADR 2026-10-22-1 D-6).
- **Costs:** a plumbing writer; event-log merge semantics move from file merge to ref CAS
  (ADR 2026-02-09-3 is file based); the bookkeeping that consolidation projects onto the target
  must be redone; the create-to-first-write window needs a rule.
- **Java service:** the natural home. D-3 already gives the service "which partition, worktree
  and branch"; a git-ref adapter behind `EventLogPort` (D-6) is the change, which D-6 says needs
  its own ADR. It fits step 4 of the migration order ("the service takes
  `status.events.jsonl`"). Doing it in Python first would create a second writer the ADR forbids
  (D-5), so this option is sequenced *through* the service, not before it.

### (f) Coord-only topology without a coord worktree

A variant of (e): keep the coordination branch as the status/lifecycle home, delete the
coordination worktree, write via plumbing. Collapses `coord` and `lanes_with_coord` onto
"single_branch + status ref" and "lanes + status ref". This is the shape (b)+(e) converge to.

### Summary table

| Option | Parallel lanes | Gates / lane_head | Lane-tip refs | Status divergence | Migration effort | Main risk |
|---|---|---|---|---|---|---|
| a tighten | kept | unchanged | kept | reduced (one contract) | low-medium, incremental | adapter creep returns |
| b ephemeral checkouts | kept | unchanged | kept, simpler | lane copies gone | medium (allocator, templates) | uncommitted work at lease end |
| c single_branch default | opt-in | unchanged; single_branch bound gap | n/a on default path | gone on default path | low | parallelism regression; bound residual |
| d drop lanes | lost | lane axes moot | removed | gone | high | product capability loss |
| e/f ref status store | kept | unchanged | kept | gone by construction | medium-high, via Java service step 4 | merge-semantics ADR; plumbing writer |

Architect's ordering (for the synthesis to weigh): (a)'s resolver convergence and post-PR owner
first (prerequisite for all); (c) as a cheap default flip once the single_branch bound residual
is closed; (b) for Missions that opt into lanes; (e)/(f) as the target state, landed by the Java
write service's status handover rather than a Python precursor. (d) is dominated by (b)+(c).
