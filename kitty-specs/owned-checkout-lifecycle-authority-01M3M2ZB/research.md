# Research: Owned-checkout lifecycle authority

**Sources**: the pre-spec squad (architect-alphonso, debugger-debbie, python-pedro, planner-priti; see `research/pre-spec-options-memo.md`), the post-spec squad (reviewer-renata, paula-patterns), and the plan research (architect-alphonso: carrier design; python-pedro: mechanics). All claims were checked against `origin/main` @ `af847be7` / `dccf6aa7d` unless marked *hypothesis*.

## R-01 Carrier location and shape
- **Decision**:
  - A new `src/mission_runtime/owned_checkout.py` holds a frozen `OwnedCheckout` (`repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology`, `target_branch`), re-exported from `mission_runtime`.
  - Construction goes only through `OwnedCheckout._mint(...)`, guarded by a module-private sentinel. `__post_init__` checks containment (`mission_dir` is under `owned_root/kitty-specs`) and that `owned_root != repository_root`.
  - `OwnedMission` is deleted. Its `files()` containment helper moves onto `OwnedCheckout` as pure path logic.
- **Rationale**:
  - `runtime` and `mission_runtime` cannot import `specify_cli.core.OwnedMission` without new edges (`test_layer_rules.py:116`, `_baselines.yaml:21`).
  - `runtime → mission_runtime` is already used by 5 modules (for example `runtime_bridge.py:197`).
  - MR-1/MR-2 forbid importing submodules from outside the package, so the type must be on the package root.
- **Alternatives**:
  - Keep `OwnedMission` in `specify_cli.core`: this forces bare paths in runtime, which is the current defect.
  - Move it with the old field names: rejected by the operator (decision `01M3M65K…`), because the terminology canon rules out bare "primary".
  - Keep an alias: forbidden by the no-shim burn-down.

## R-02 Topology per command
- **Decision**: `resolve_owned_mission(..., allowed_topologies)`, with `LIFECYCLE_OWNED_TOPOLOGIES={SINGLE_BRANCH}` and `NEXT_OWNED_TOPOLOGIES={SINGLE_BRANCH, LANES, LANES_WITH_COORD, COORD}`. `OWNED_TOPOLOGY_UNSUPPORTED` fires when the stored topology is outside the allowed set. The `coordination_branch` refusal applies only when coordination topologies are disallowed.
- **Rationale**: the operator kept owned coordination-topology `next` (decision `01M3M4GM…`). The e2e `tests/e2e/test_worktree_owned_root_concurrency.py:405-431` relies on it, with P on its target branch, so the branch and protection checks of FR-002 hold (*hypothesis*: confirmed red-first in IC-05). `LANES` is included in `NEXT_OWNED_TOPOLOGIES` (not just the coordination topologies) to preserve today's behaviour exactly: on `main`, `next --owned-checkout` applies no topology check at all (it calls only the claim primitive, `next_cmd.py:160-176`), so a plain lanes-without-coordination owned mission is accepted today. Per the "keep coordination topologies" decision `01M3M4GM…`, the rewire onto the single validator must not newly narrow that set — `next` keeps accepting every topology it accepts today, so `LANES` joins `SINGLE_BRANCH`, `LANES_WITH_COORD` and `COORD`.

## R-03 `effective_root` census and migration
- **Finding**: bare owned-root parameters or fields across `mission_runtime/resolution.py` (including `PlacementSeam.effective_root` at `:1981`), `runtime/next` and `specify_cli`. `src/charter` uses `effective_root` for the org-pack root, a different sense, which is excluded. The exact, current count is the census in plan Scale/Scope (the authoritative measured number); this research note does not restate a separate count.
- **Decision**: convert all bare owned-root parameters and fields (plan Scale/Scope census) to `owned: OwnedCheckout | None` in this mission. Gate G4/G5 has an empty allowlist. The operator's rationale: "half-implemented work and ratchets have been hurting us for weeks."

## R-04 Placement fall-back (root cause of O3/O4/O5)
- **Finding**:
  - `placement_seam(repo_root, slug)` resolves the primary-partition kinds through `get_main_repo_root`, so R is returned even when `repo_root` is P (`workspace/context.py:642,694,734`; `resolution.py:1094`).
  - `next_cmd.py:176` sets `repo_root=effective_root=P`, yet reads still land in R.
- **Decision**: `PlacementSeam.owned`. When it is set, primary-partition kinds read `owned.mission_dir` and never call `get_main_repo_root`.

## R-05 Claim commit (FR-010)
- **Finding** (run on HEAD):
  - `move-task --to claimed --owned-checkout P` makes exactly one commit on P's branch (`chore(spec-kitty): status transition WP01`). It touches only `status.events.jsonl` and `status.json`.
  - No commit hash is recorded (`CommitReceipt.commit_sha` is discarded, `transaction.py:855`).
  - Today's review base uses subject matching (`workflow_executor.py:2236-2279`, `prompt_builder.py:222-269`). It can never match owned claims after the event-only cutover.
  - #5009's b1a1693bf is still subject matching.
- **Decision**:
  1. Take the last `to_lane=claimed` event for the WP in P's log.
  2. Run `git -C P log --format=%H -S<event_id> HEAD -- kitty-specs/<slug>/status.events.jsonl`, which must return exactly 1 commit.
  3. The diff is `claim..HEAD -- <owned_files>`.
  4. On 0 or ≥2 matches, or when there are no `owned_files`, fail with `OWNED_REVIEW_BASE_UNAVAILABLE` (a `blocked` decision).
- **Alternatives**: recording `receipt.commit_sha` in a follow-up annotation costs a second commit per claim and a schema change, so it was rejected.

## R-06 `next` O5 wedge
- **Finding**:
  - `runtime_next_step` persists the advance to `implement` inside a try (`runtime_bridge.py:2288`).
  - Then `_map_runtime_decision` → `_build_wp_iteration_decision` → `_wp_iteration_action_and_state` → `decision._state_to_action:434` raises `ValueError`, outside that try, via `resolve_workspace_for_wp` folding to R.
  - `_commit_owned_next_mutations` never runs.
- **Decision**:
  - Carry the fact on `DecideNextContext`.
  - Resolve the WP workspace through the owned arm, which cannot fold to R.
  - Resolve before persisting the advance.
  - Wrapping the error into `blocked` is explicitly not the fix (FR-008).

## R-07 Finalize write order and atomicity
- **Finding**: the write order in `mission_finalize.py` is:
  1. meta `:3381`
  2. issue-matrix `:3417`
  3. WP frontmatter `:3472`
  4. tasks.md `:3478`
  5. TasksStarted `:3506`
  6. canonical events and bootstrap `:2980-2982`
  7. lanes.json `:2992`
  8. acceptance matrix `:3009`
  9. commit `:3020`

  Refusals after writes are ownership manifests `:3489`, stale-canceled `:3501`, lane cycle and pins `:2992`, and O6's status-surface refusal via `status/bootstrap.py:151`. **Dependency-graph cycles and invalid refs are already atomic** (`_validate_dependency_graph` at `:3431` runs before any WP write, verified clean).
- **Decision**:
  - Build the whole finalize plan in memory first, reusing the `--validate-only` path (INV-6), then apply all writes.
  - Amend spec US4-AS3 to use a **lane dependency cycle** (WP01→WP02→WP03 with WP01 and WP03 sharing an owned file) as the red-on-base refusal.
- **Superseded by origin/main's #5100** (merge `ff666bbbe`): a `single_branch` mission — the only owned lifecycle topology — computes exactly one repo-root `lane-planning` lane (Invariant T-1), so the lane-dependency-cycle refusal is unreachable inside an owned checkout. The atomic-finalize guarantee (FR-015 / US4-AS3) is now proven by the single-lane finalize test, with the stale-canceled, planning-pin-orphan and issue-matrix refusals keeping the post-write-refusal coverage.

## R-08 #4867 reproduction
- **Finding**:
  - `_resolve_owned_coordination_workspace` → `CoordinationWorkspace.resolve` → `_has_stale_worktree_registration` (`coordination/workspace.py:163`) runs `git worktree list --porcelain` with stderr **not captured**.
  - Exit 128 is re-raised as `DecisionGitLogUnavailable` (`runtime_bridge.py:389`), which nothing catches.
  - Truncating any registered worktree's `.git/worktrees/<name>/commondir` makes git print `fatal: failed to read …/commondir: Success` (verified with git 2.43; a missing file does not reproduce it).
- **Decision**:
  - Capture stderr and raise a typed `CoordinationWorkspaceUnavailable`.
  - The runtime maps it to a `blocked` decision with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
  - The red-first repro: owned `lanes_with_coord` create, remove the coordination worktree dir, add a sibling worktree with a truncated `commondir`, then `next --owned-checkout P`.

## R-09 Flagless adoption
- **Finding**:
  - `missions/operation_context.py:69-116` adopts `get_status_read_root(cwd)` without validation. Its sole caller is `agent/context.py:148`.
  - The other `get_status_read_root` uses are lane-worktree reads (#984) and a branch identity read; neither adopts mission data.
- **Decision**: `adopt_owned_checkout(repository_root, cwd, handle, *, allowed_topologies)` in `owned_mission.py` returns `None` when:
  - the caller is R or belongs to a different repository;
  - it is a coordination worktree (`surface_resolver.classify_worktree_topology`);
  - it is a lane worktree (`lanes.json` / workspace context);
  - or the validator raises.

  Otherwise it returns the fact. `operation_context.py` is deleted.

## R-10 Status surface under `.worktrees/`
- **Finding**: `status_service.read_event_log:162` refuses any `.worktrees` path shape for repository-root-labelled reads. #5009's `StatusReadSource.OWNED_CHECKOUT` is a parallel source (C-002).
- **Decision**:
  - `EventLogReadContract.owned`.
  - The guard delegates to `surface_resolver.primary_read_targets_coord_worktree(path, *, owned)`, which returns False when `owned` is set and the path is under `owned.owned_root`.
  - The label stays unchanged.
  - The fact already proves registration and branch, so no extra git calls are made (NFR-002).

## R-11 Composition policy
- **Finding**: `_dn_composition_dispatch` (`runtime_bridge.py:2020-2087`) reads `PackContext.from_config(ctx.repo_root)`. Through the real CLI that is already P (*hypothesis*); under the new call shape (`repo_root=R`) it must read `owned.owned_root`.
- **Fixture**: R's `.kittify/config.yaml` has `mission_type_activations: []` while P has a provisioned test charter (validated by #5009 1be5352ee).

## R-12 Stale-copy warning channel
- **Finding**: only `context resolve` has a `warnings` list (`mission_runtime/context.py:321`). `agent tasks status`, `setup-plan` and `next` have none.
- **Decision**:
  - A top-level JSON field `stale_repository_root_copy: {"path", "mission_id"} | null` on all five owned read payloads.
  - The human text is appended to `warnings` where that list exists, and printed on stderr in human mode.
  - Detection compares the repository-root placement against `owned.mission_dir`, with no git calls.

## R-13 CLI plumbing
- **Finding**: there is no shared `--owned-checkout` option or refusal emitter. Each command declares the option inline (`tasks.py:782,916`, `mission_finalize.py:3237`, `mission_check_prerequisites.py:563`, `next_cmd.py:132`), and the envelopes differ.
- **Decision**:
  - A new `cli/commands/_owned_checkout.py` with `OwnedCheckoutOption`, `resolve_owned_or_adopt` and `emit_owned_refusal`.
  - The emitter keeps each command's existing envelope keys.
  - The golden contracts are updated for the new flags.

## R-14 Repository root checkout passed as `--owned-checkout`
- **Finding**: `resolve_ownership_claim` returns OWNED for the repository root itself (`checkout_ownership.py:217-223`).
- **Decision**: refuse it with the new code `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, added to the NFR-004 registry.

## R-15 #5009 carry map
The keep/adapt/drop disposition of each commit is recorded in plan IC-13. Four test commits carry cleanly and are red on HEAD:
- a37e9ee39: FR-016 (genuine red);
- edaa9cd83: red only by `TypeError`, needs adaptation;
- 1be5352ee: composition red; the review assert must be rewritten to the R-05 contract;
- 4ff6ff0c0: `test_finalize_and_read_owned_mission_below_worktrees` is a genuine red. `test_owned_contract_validates_root_and_mission` is dropped (C-002). The coordination-rejection test is kept, and a registered coordination worktree case is added.

6d682dce3 is dropped.

## Adversarial evidence
There is no dependency decision, so the supply-chain adversarial pass does not apply. The design was challenged by three squads (pre-spec, post-spec, plan research). Their contested findings and dispositions:
- #4867 vs single_branch: **changed** (per-command topology).
- Flagless behaviour: **changed** (validated adoption).
- Owned implement/review path: **changed** (`next` + `move-task`).
- Claim-commit definition: **changed** (R-05).
- US4-AS3 refusal choice: **changed** (R-07).
- Parallel status source from #5009: **accepted** (dropped).

## R-16 Post-plan squad folds (randy-reducer, paula-patterns, debugger-debbie)
- **Topology single authority.** `_require_owned_single_branch` (`resolution.py:1505,1596,2361`) is deleted. Topology is decided at minting only.
- **Status shape guard.** It runs at six sites in `status_service.py`, and all six route through `surface_resolver`. `transaction.py:644`'s raw `.worktrees` check moves to `is_under_worktrees_segment`.
- **Review-base duplication.** There are three subject matchers (`workflow_executor.py:2259`, `prompt_builder.py:255`, `core/worktree_topology.py:125`), broken for every mission since the event-only cutover. They are unified into `claim_commit_for_wp` for all review paths (operator decision `01M3M70Y…`).
- **CLI duplication.** There are eight inline `--owned-checkout` declarations and a separate `_emit_checkout_ownership_error`. They are unified onto `_owned_checkout.py`, which builds on `json_contract.json_error`.
- **Path safety.** `OwnedCheckout.files()` must keep the symlink and loop defence (`kernel.resolution.resolve_rejecting_loops`).
- **Adoption.** `tasks_status_cmd.py:224`'s cwd root was falsified as a second adoption path, because the handle resolves against R first. The mission-surface-conflict refusal for different mission ids is preserved inside `adopt_owned_checkout`.
- **Sizing.** About 400 edit sites and about 26 test files; see the plan's Scale/Scope. Staging is top-down, with transitional surfaces (the six shared seams plus every other function marked TRANSITIONAL(WP18)) deleted in the closing WP (operator decision `01M3M713…`).
- **Gate.** G4/G5 were rewritten as an identifier ban plus a named carrier-field rule, and G1 covers all reference forms. G2's floor was corrected: `cli/commands/accept.py` is on the allowed path.
- **R-snapshot.** It excludes exactly P's subtree, and covers the shared lock root, `SPEC_KITTY_HOME` and cwd ∈ {R, P, elsewhere}.
- **#4867.** Only a zero-byte `commondir` reproduces it (a missing file or a lone newline gives rc 0). The stderr wording depends on the C library, so tests assert on `error_code` with a pre-assertion that the injected fault really breaks git, plus a subprocess-seam injection.
- **FR-022.** The coordination-topology owned `next` coverage was nightly-only, so an in-process per-PR twin is added.
- **Complexity.** `accept` (59) and `_create_mission_core_impl` (40) are the only over-limit functions in their per-file-ignored files. Both are fully decomposed and their C901 ignores removed (operator decision `01M3M718…`).
