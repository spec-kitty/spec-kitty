# Research: Single-branch topology honesty and destroyed-lane tip guard

**Sources**:
- The operator decision on #5100 (comment 5870360497).
- The pre-spec alignment squad (architect-alphonso) and scope squad (planner-priti).
- The post-spec squad: reviewer-renata (fidelity), architect-alphonso (architecture), paula-patterns (patterns).
- Evidence is quoted at `origin/main` 99352f08. Squad claims labelled as inference are marked here.

## R-1 Where topology is ignored

- **Decision**: make the lane manifest the chokepoint. A `single_branch` finalize writes one repo-root lane, id `lane-planning`, holding every work package.
- **Rationale**: every existing reader already routes a planning lane to the repository root.
  - `_resolve_workspace_for_wp_impl` does this at `workspace/context.py:836-850`.
  - `is_planning_lane` (`lanes/compute.py:34-50`) is documented as "the single seam".
  - Keying readers on the manifest avoids adding topology reads to about 20 call sites.
- **Evidence**:
  - `compute_lanes` (`lanes/compute.py:477`) has no topology input.
  - The resolver branches only on WP kind (`context.py:760`) and on the lane.
  - Code work packages always get a `.worktrees` lane (`:855-868`).
- **Alternatives considered**:
  - A topology arm inside the resolver alone. Rejected: it leaves the manifest dishonest, so the gates and consolidate would still see `lane-a`.
  - A new lane id `lane-root`. Rejected: it breaks existing readers and dashboards for no gain.

## R-2 `is_planning_artifact_only` is overloaded

> **Superseded by plan.md post-plan fold B3** (analysis finding I1). `is_planning_artifact_only` stays **lane-based**. The "no code" claims use the new `has_code_wps(manifest)`. The split described below is NOT implemented.

- **Decision**: split it into two predicates.
  - `is_repo_root_lane(lane)`: where the lane executes.
  - `is_planning_artifact_only(manifest)`: no code deliverables. Returns false when any work package in the manifest is `code_change`.
- **Rationale**: for `single_branch` code work packages the current predicate would do three wrong things:
  - skip the acceptance matrix (`acceptance/gates_core.py:277`);
  - skip the runtime-state cutover (`consolidation/executor.py:1671`);
  - skip the mission→target phase (`executor.py:1469`).
- **Alternatives considered**: reusing the predicate unchanged. Rejected for the silent-skip hazards above.

## R-3 Lane presence for topology derivation

- **Decision**: `backfill_topology._has_lanes` (`:52`) counts code lanes only, through `has_code_lanes`.
- **Rationale**: `read_topology`, `classify_from_meta` and backfill all route through `_derive_topology`, so one change covers all three.
- **Evidence**: `_assert_topology_corroborated` (`mission_runtime/resolution.py:441`) has no production caller that passes a lane signal (patterns lens). It needs no change.

## R-4 Fail-closed placement for unmigrated missions

- **Decision**: add the pure predicate `assert_topology_matches_manifest(topology, manifest)` next to `is_single_branch` in `mission_runtime/context.py`. Call it at exactly two writers:
  - `compute_and_persist` before `write_lanes_json`;
  - `allocate_lane_worktree`, the only creator of lane worktrees. Its callers are `implement_support.py:169` and `orchestrator_api/commands.py:1376`.
  - Error code: `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`.
- **Rationale**: this blocks every command that would act on the new semantics with old artifacts, while reads (status, accept, doctor) keep working.
- **Alternatives considered**: failing inside `read_topology`. Rejected: that breaks status reads for all 64 missions.

## R-5 Protection authority

- **Decision**: add `ProtectionPolicy.is_protected_target(branch, primary_branch)`, which returns `branch == primary_branch or policy.is_protected(branch)`. `--commit-to-target` is honoured through the policy's existing operator hatch.
- **Rationale**: the decision says "primary plus configured". `ProtectionPolicy` alone differs in two ways:
  - an explicit configured list replaces the defaults;
  - a primary branch with a non-default name is unprotected when there is no `origin/HEAD` (`protection_policy.py:18-30`).
  - One query on the existing authority satisfies both the decision and C-002.
- **Alternatives considered**:
  - Policy-only semantics. Rejected by the fidelity lens as relitigation.
  - A new protection check. Rejected under C-002.

## R-6 Where the lane work tip lives, and how it is recorded

- **Decision**: store the tip as the hidden ref `refs/spec-kitty/lane-tip/<lane-branch>`.
  - A plain-`sh` post-commit hook writes it: it case-matches `refs/heads/kitty/mission-*-lane-*` and runs `git update-ref`.
  - spec-kitty's own lane advances update the same ref.
  - It is deleted at terminal work-package states and at consolidation teardown.
  - For a lane that predates recording, the ref is backfilled from the live branch the next time spec-kitty touches it.
- **Rationale** (architecture lens experiments on git 2.43):
  - The post-commit hook in the common hooks dir fires from linked worktrees.
  - It fires under `--no-verify`, for amends, rebase picks and cherry-picks, and its exit status is ignored.
  - A Python hook is out: `import specify_cli.workspace.context` takes about 1.3 s, which breaks NFR-001.
  - Branch deletion removes the branch reflog, and `git worktree remove` removes the worktree HEAD log. Only a spec-kitty-held ref survives.
  - The ref also keeps the stranded commits alive through `gc`, so the work is restorable, not merely detectable.
  - `spec-kitty context cleanup` deletes the context of exactly a destroyed lane. A tip stored in the context would therefore fail open.
- **Deviation**: the brief said "persist in the workspace record". The workspace record keeps `base_commit` and gains nothing. It remains the allocator-owned record (FR-022). The deviation is flagged in the PR.
- **Alternatives considered**:
  - A `WorkspaceContext` field. Rejected for the reasons above.
  - Recording only at spec-kitty observation points. Rejected: the #5115 acceptance sequence (commit, then delete, with no spec-kitty call in between) cannot pass.
  - A `reference-transaction` hook. Rejected: it reports old = 0 on deletion.
  - `git fsck --unreachable`. Rejected: O(repo) and it cannot attribute a commit to a lane.
- **Residuals**:
  - An operator `git merge`, `pull` or `reset` on a lane is not recorded at commit time. It is recorded at the next spec-kitty touch. The lagging ref still points at the lane's own work, which is fail-safe.
  - Hooks that are disabled or foreign mean recording happens only at spec-kitty touches. spec-kitty warns.

## R-7 Absorption: telling "destroyed" from "squash-merged"

- **Decision**: a tip counts as absorbed when any of these holds:
  - it is an ancestor of the target;
  - it equals the lane's creation base;
  - `git merge-tree --write-tree <target> <tip>` produces a tree equal to `<target>^{tree}`.
  - On git older than 2.38, fail closed, reusing the existing handling at `consolidation/reconciliation.py:815`.
- **Rationale**: the architecture lens verified two cases.
  - A two-commit squash plus later unrelated target edits yields equal trees.
  - A destroyed commit yields a different tree.
  - A conflicting later target edit refuses, which fails closed.
- **Alternatives considered**:
  - Patch-id or `git cherry`. Rejected: they miss a squash of several commits into one.
  - WP status. Rejected: `done` and `approved` are already outside the trigger set (`worktree_allocator.py:239`); the real case is an external squash while the WP is `for_review`.

## R-8 When the protected-target mission branch is created

- **Decision**: mint it at `mission create`, when the stored topology is `single_branch`, the target is protected and `commit_to_target` is not set.
  - Check it out in the write checkout.
  - Record `mission_branch` in `meta.json`.
  - Refuse if the branch already exists.
- **Rationale**: commit-router rule 3 (`coordination/surface_authority.py:245`, `commit_router.py:337-367`) refuses coordination-less commits to a protected target, planning artifacts included. So a branch that did not exist until implement could never receive the spec, plan or tasks.
- **Alternatives considered**: implement-time minting. Rejected as infeasible for that reason.

## R-9 Consolidating a `single_branch` mission

- **Decision**:
  - **Unprotected or `commit_to_target`:** no git landing, bookkeeping only.
  - **Protected:** the mission→target phase runs whenever `mission_branch != target_branch`. Authored blobs for the repo-root lane come from first-parent `base..mission_branch`. The write checkout is switched back to the target before the mission branch is deleted. The repository root checkout and the target branch are never removed.
- **Rationale**:
  - `_phase_mission_to_target` returns early for planning-only missions (`executor.py:1469`).
  - The squash verifier would refuse with no authored content (`reconciliation.py:613,1054`).
- **Risk**: this is sibling-owned territory (C-005). The edit is kept to one arm plus one blob-source branch, and the PR calls it out.

## R-10 Execution-mode stamp

- **Decision**: add one `ResolvedWorkspace.status_execution_mode` property: `direct_repo` when `resolution_kind == "repo_root"`, else `worktree`. Every emit site uses it.
- **Evidence**:
  - The derivation is already copied three times: `implement.py:1480`, `workflow.py:1450`, `workflow_executor.py:1573`.
  - move-task passes no mode (`tasks_move_task.py:2809`), so it gets the model default `worktree`.
  - `_mt_owned_workspace` (`:781`) hardcodes `lane_workspace`.
  - The orchestrator hardcodes the mode at `commands.py:1604,1697,1870`.

## R-11 Create default

- **Decision**: in `mission_create.py:410-420`, both implicit `SINGLE_BRANCH` returns become `LANES`. These are the non-primary arm without pr-bound and the pr-bound arm where coordination is unreachable.
  - `single_branch` then comes only from `--topology single_branch` or `--owned-checkout`.
  - The pinned tests in `tests/specify_cli/cli/commands/test_mission_create*.py` are updated. These are the minimal golden edits under C-005.
- **Rationale**: decision item 2, plus "single_branch only from explicit" (answers #2602).

## R-12 PR #5009

- **Decision**: absorb only the resolver arm: an `effective_root` parameter on `resolve_workspace_for_wp` / `_resolve_workspace_for_wp_impl`, re-keyed on topology, with a `Co-authored-by: samuelgoff` trailer. The rest of #5009 stays with its author.
- **Evidence**:
  - `main` already has `placement_seam(effective_root=)` (`mission_runtime/resolution.py:2491`) and `core/owned_mission.py`.
  - #5009 is 72 commits behind and in maintainer RESCOPE triage (its comment 5834855854).
  - A sequencing comment was posted on #5009.

## Adversarial evidence (dispositions)

| Finding | Lens | Disposition |
|---|---|---|
| B1: protection weakened | fidelity | changed (R-5) |
| B2: one in-progress WP scoped per mission | fidelity | changed (FR-010) |
| M1: dirty refusal breaks resume | fidelity | changed (FR-009) |
| M2: `single_branch` consolidation unspecified | fidelity | changed (FR-012, R-9) |
| M3: dependency merge unspecified | fidelity | changed (US2.9) |
| M4: mission/coord branch name collision | fidelity | changed (R-8; readers key on `meta.json`) |
| M5: fail-closed scope too narrow | fidelity | changed (R-4) |
| M6: non-vacuity controls missing | fidelity | changed (controls added to US1, US2, US5, US6) |
| Tip storage and hook cost | architecture | changed (R-6) |
| Squash predicate | architecture | changed (R-7) |
| Mission branch timing | architecture | changed (R-8) |
| `is_planning_artifact_only` overloaded | architecture | changed (R-2) |
| Chokepoint placement | patterns | accepted (R-1, R-4) |
| Work-tip migration cannot be one-shot | patterns | changed (R-6 backfill on touch) |
| move-task stamp | patterns | accepted (R-10) |
| Owned-checkout refuses mission branch | patterns | accepted (IC-05 `expected_write_branch`) |
| Protected-target arm is mission-sized | architecture | deferred_with_rationale → kept in scope because the brief's acceptance test requires it. Sequenced last (IC-05) so earlier slices are independently reviewable. |
