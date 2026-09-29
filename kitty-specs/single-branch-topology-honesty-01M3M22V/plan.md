# Implementation Plan: Single-branch topology honesty and destroyed-lane tip guard

**Branch**: `issue-5100-single-branch-topology` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/single-branch-topology-honesty-01M3M22V/spec.md`

Planning questions were answered by the binding operator decision (#5100 comment 5870360497) and three squads:
- pre-spec alignment and scope;
- post-spec fidelity, architecture and patterns.

Their evidence is consolidated in [research.md](research.md). No question is deferred.

## Summary

Three defect classes, each closed at one chokepoint rather than at every call site.

1. **The planning lane falls back to `main` (FR-001/002).** `lane_branch_name(slug, "lane-planning")` silently returns `"main"` when no target is passed. The for_review gate predicts a lane worktree that is never created.
   - **Fix:** the planning-lane name requires the target branch.
   - **Fix:** the gate resolves the workspace through `resolve_workspace_for_wp` instead of predicting a `.worktrees` path.
2. **Topology is ignored for `single_branch` (FR-003…017).** `single_branch` is recorded in `meta.json` but ignored by lane computation, the workspace resolver and implement.
   - **Fix:** the lane manifest becomes the chokepoint. A `single_branch` finalize writes one repo-root lane: the existing `lane-planning` id, now holding every WP. Every existing `is_planning_lane` reader then routes to the write checkout unchanged.
   - **Also:** code lanes are refused for `single_branch` at the two writer chokepoints, the manifest write and lane-worktree allocation.
   - **Also:** the create default, a re-stamp migration and a doctor finding.
   - **Protected targets:** a mission branch minted at create, a write-target arm in the placement seam, and a mission→target phase in consolidate.
3. **The destroyed-lane guard checks the lane's creation base, not its work tip (FR-018…022, FR-024).**
   - **Fix:** a plain-`sh` post-commit hook records `refs/spec-kitty/lane-tip/<lane-branch>` at every lane commit. spec-kitty's own lane advances update the same ref.
   - **Fix:** the guard refuses when that tip is neither an ancestor of the target nor absorbed, where absorbed means a merge-tree no-op.

## Technical Context

**Language/Version**: Python 3.11+ (CLI), POSIX `sh` (hook), git ≥ 2.25 (git ≥ 2.38 for absorption evaluation; older fails closed)
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); no new dependencies
**Storage**: `kitty-specs/<mission>/meta.json`, `lanes.json`; `.kittify/workspaces/*.json` (gitignored); git refs `refs/spec-kitty/lane-tip/*` (local, unpushed)
**Testing**: pytest. Issue-pinned `@pytest.mark.regression` red-first tests through the real CLI (`typer` runner / subprocess on temp git repos), plus focused unit tests per helper. Targeted only (C-007).
**Target Platform**: Linux, macOS, Windows 10+ (Git for Windows bundles `sh`)
**Project Type**: single (Python CLI package)
**Performance Goals**: hook ≤ 50 ms p95 per commit (NFR-001); `implement` < 2 s (NFR-002)
**Constraints**: no runtime topology fallback (C-003); coord topologies unchanged (C-004); single protection authority (C-002); never overwrite foreign hooks (C-010); minimal edits in sibling-owned `consolidation/*` and `tests/integration/**` (C-005)
**Scale/Scope**: 64 in-repo missions to re-stamp; ~25 source files touched across `lanes/`, `workspace/`, `migration/`, `cli/commands/`, `policy/`, `git/`, `consolidation/`, `mission_runtime/`

## Charter Check

| Charter rule | Status | How |
|---|---|---|
| Single canonical authority | PASS | Each concern has one owner:<br>• topology: `meta.json` via `read_topology`<br>• protection: `ProtectionPolicy`<br>• lane placement: the manifest plus `is_repo_root_lane`<br>• work tip: the hidden ref<br>• execution-mode stamp: one `ResolvedWorkspace` property. |
| Require-canonical + migration over fallback | PASS | The re-stamp migration plus a fail-closed check at the chokepoints. There is no reinterpretation at runtime.<br>Tip backfill-on-touch is local-state recording, not topology inference (research R-6). |
| Architectural alignment | PASS | Reuses the existing seams:<br>• `is_planning_lane`<br>• `_ensure_mission_branch`<br>• `_validate_worktree_clean`<br>• `owned_mission`<br>• `placement_seam(effective_root=)`<br>• `git_probes`<br>• the hook installer.<br>The layer rules are unaffected: no new imports into `kernel`/`charter`. |
| ATDD-first / red-first (C-011, ADR 2026-07-17-1) | PASS (planned) | Each issue test is committed RED before its fix commit. The reviewer checks red→green. |
| Campsite cleaning (SO #2) | PASS (planned) | `worktree_allocator.py` is 1,400+ lines. The guard helpers it touches are extracted before behaviour changes.<br>`_resolve_workspace_for_wp_impl` is split per arm so every function stays at complexity ≤ 15. |
| Architectural gate discipline | PASS (planned) | New gate `tests/architectural/test_planning_lane_branch_requires_target.py`: no call to `lane_branch_name(..., PLANNING_LANE_ID)` without a target. It has a concrete floor and a self-mutation test. |
| Pack tiers | N/A | No doctrine edits. |
| Terminology canon | PASS | Mission, repo root checkout, and every sense of "merge" named. The glossary entry is FR-023. |
| User customization preservation | PASS | Hook install only into an empty slot or one with the spec-kitty signature; otherwise warn (FR-024). |
| No full heavy suites | PASS | Targeted test list per work package; named architectural gate files only. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/single-branch-topology-honesty-01M3M22V/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/  (single-branch-execution.md, lane-work-tip.md, topology-restamp.md)
├── traces/     (tooling-friction.md, approach.md, design-decisions.md)
└── tasks.md + tasks/ (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── lanes/{branch_naming,compute,compute_and_persist,for_review_gate,implement_support,worktree_allocator,recovery,lane_tip}.py
├── workspace/context.py                      # resolver arm split + effective_root (PR #5009 arm)
├── cli/commands/{implement,agent/mission_create,agent/tasks_move_task,doctor}.py
├── core/{mission_creation,paths,owned_mission}.py
├── git/protection_policy.py                  # is_protected_target (primary OR configured)
├── policy/hook_installer.py                  # post-commit tip recorder (sh)
├── migration/backfill_topology.py            # has_code_lanes, restamp_single_branch_with_code_lanes
├── upgrade/migrations/m_4_0_0rc5_single_branch_code_lanes_restamp.py
├── orchestrator_api/commands.py              # route allocation + stamp through shared helpers
└── consolidation/{executor,reconciliation}.py  # minimal: mission→target phase for single_branch (C-005)
src/mission_runtime/{context,resolution}.py   # assert_topology_matches_manifest; write-target arm for mission_branch
tests/lanes/test_issue_5115_destroyed_lane_non_coord.py   (red-first, regression)
tests/integration/test_issue_5100_single_branch_topology.py (red-first, regression)
tests/migration/test_single_branch_code_lanes_restamp.py
tests/architectural/test_planning_lane_branch_requires_target.py
```

**Structure Decision**: this is a single Python package. Tests mirror the source layout under `tests/`. The two issue-pinned tests go where the brief places them.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Tip is stored in a git ref, not in `WorkspaceContext` (differs from the brief's wording) | The tip must survive deletion of the branch, the worktree and the context record. It must also keep the commits reachable for restore. | A `WorkspaceContext` field fails in three ways:<br>• it is deleted by `context cleanup`, so the guard fails open;<br>• writing it needs a Python hook, about 1.3 s per commit (NFR-001);<br>• it does not keep stranded commits alive through `gc`. |
| Mission branch minted at create, not at first implement | A protected target refuses every planning commit (`commit_router` rule 3), so the spec, plan and tasks could never land. | Implement-time minting cannot receive planning artifacts. |
| Consolidate edit in the sibling-owned `consolidation/*` | FR-012 (decision item 4) needs a mission→target landing for the repo-root lane. | Skipping it leaves protected-target missions un-landable. Kept to one arm plus an authored-blob source; the overlap is noted in the PR. |

## Implementation Concern Map

### IC-01 — Planning-lane branch never falls back to `main`

- **Purpose**: make every planning-lane branch resolution name the target branch, and make the for_review gate use the resolved workspace.
- **Relevant requirements**: FR-001, FR-002
- **Affected surfaces**:
  - `lanes/branch_naming.py:~520-535`: `lane_branch_name`; the planning arm refuses when no target is given.
  - `lanes/for_review_gate.py:86,121-160`: gate through `resolve_workspace_for_wp`; fix the docstring.
  - `lanes/implement_support.py:~478`: `_approved_dependency_lane_refs`.
  - `lanes/worktree_allocator.py:~1253`: `_merge_dependency_lane_tips`. Pass `planning_base_branch=manifest.target_branch`.
  - New architectural gate file.
- **Sequencing/depends-on**: none.
- **Risks**:
  - `consolidation/executor.py:1987` has a literal `"lane-planning"`. It is sibling-owned; only touch it if the gate flags it.
  - The gate needs an allowlist-free floor.

### IC-02 — Topology reader counts code lanes; fail closed; re-stamp migration; doctor

- **Purpose**: separate "has lanes" from "has code lanes", refuse `single_branch` code lanes at the writers, migrate the 64 missions, and report drift.
- **Relevant requirements**: FR-014, FR-015, FR-016, FR-017
- **Affected surfaces**:
  - `lanes/compute.py:34-53`: add `has_code_lanes`, `is_repo_root_lane`, and a split `is_planning_artifact_only` that returns false when any WP is `code_change`.
  - `migration/backfill_topology.py:52-67`: `_has_lanes` counts code lanes only; add `restamp_single_branch_with_code_lanes()`.
  - `mission_runtime/context.py`: new `assert_topology_matches_manifest`.
  - Call sites of that assertion: `lanes/compute_and_persist.py:146` and `lanes/worktree_allocator.py:689`.
  - New `upgrade/migrations/m_4_0_0rc5_single_branch_code_lanes_restamp.py`.
  - `cli/commands/_identity_audit.py:329` and `doctor.py:500`: finding `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`.
  - A data commit re-stamping the 64 in-repo `meta.json` files.
- **Sequencing/depends-on**: none. It must land before IC-03 changes what `single_branch` computes.
- **Risks**:
  - Re-stamped missions switch from uncommitted to committed status annotations (`status_transition.py:1582`). This is expected and documented.
  - Missions whose `meta.json` is not on the checked-out branch stay unmigrated and are caught by the fail-closed check.

### IC-03 — `single_branch` executes in the write checkout

- **Purpose**: finalize writes one repo-root lane, the resolver maps every WP to the write checkout, the execution-mode stamp says `direct_repo`, and the implement refusals are in place.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-009, FR-010, FR-011, FR-013, and the dependency-merge skip from US2.9.
- **Affected surfaces**:
  - `lanes/compute.py:477` (`compute_lanes`) and `compute_and_persist.py:85-146`: take topology and build the repo-root manifest for `single_branch`.
  - `workspace/context.py:747-868`: split the arms, key the planning arm on `is_repo_root_lane` rather than WP kind, and add `effective_root`. This absorbs PR #5009's arm with a `Co-authored-by: samuelgoff` trailer.
  - Execution-mode stamp:
    - A new `ResolvedWorkspace.status_execution_mode` property.
    - Callers: `implement.py:~1480`, `agent/workflow.py:~1450`, `agent/workflow_executor.py:~1573`, `orchestrator_api/commands.py:1604,1697,1870`, and `tasks_move_task.py:~2809`.
    - `_mt_owned_workspace` at `tasks_move_task.py:781` changes to `repo_root`.
  - Implement refusals:
    - Dirty checkout: reuse `_validate_worktree_clean` (`worktree_allocator.py:1401`), excluding spec-kitty-owned paths and exempting resume.
    - One in-progress WP per write checkout: extract the `ACTIVE_WP_CONTEXT_AMBIGUOUS` computation at `context.py:470-486` into a shared helper.
  - Dependency merge is skipped for `is_repo_root_lane`.
  - `cli/commands/agent/mission_create.py:410-420`: the implicit default becomes `LANES`.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**:
  - WP-kind branching at `context.py:760` must not diverge from lane-based branching.
  - Owned-checkout validation (`owned_mission.py`) must accept the resolved write checkout.

### IC-04 — Lane work tip and destroyed-lane guard

- **Purpose**: record lane tips at commit time and at every spec-kitty lane advance, and guard on tip reachability and absorption.
- **Relevant requirements**: FR-018, FR-019, FR-020, FR-021, FR-022, FR-024; NFR-001.
- **Affected surfaces**:
  - New `lanes/lane_tip.py`: ref naming, `record_tip`, `read_tip`, `is_absorbed`.
  - `policy/hook_installer.py`: install a `post-commit` `sh` recorder into `git rev-parse --git-path hooks`, only when the slot is empty or already spec-kitty's.
  - `lanes/worktree_allocator.py:268-353`: the guard uses the tip ref, and no longer returns early when no context exists but a tip ref does.
  - Record points:
    - `allocate_lane_worktree`, at creation and on reuse;
    - `_merge_dependency_lane_tips`;
    - `lifecycle_sync.attempt_auto_rebase`;
    - the for_review transitions;
    - `tasks_move_task.safe_commit`.
  - Ref deletion points: terminal WP states and consolidation teardown.
  - `orchestrator_api/commands.py:1376`: persist the context through the allocator (FR-022).
  - Backfill: record the tip on touch when the branch is live.
  - The error remedy names `git branch <b> refs/spec-kitty/lane-tip/<b>`.
- **Sequencing/depends-on**: IC-01, because both touch `worktree_allocator.py`.
- **Risks**:
  - `merge-tree --write-tree` needs git ≥ 2.38; reuse the fail-closed git-version handling at `reconciliation.py:815`.
  - Windows `sh` availability.
  - Hook repin and upgrade interplay (ADR 2026-08-27-1).
  - The destroyed-lane error must never fire on coord topologies differently than today. The #4889 tests must stay green.

### IC-05 — Protected-target mission branch

- **Purpose**: mint and check out the mission branch at create, route writes to it, provide the override flag, and land the branch in consolidate.
- **Relevant requirements**: FR-007, FR-008, FR-012
- **Affected surfaces**:
  - `git/protection_policy.py`: `is_protected_target(branch, primary)`; the `commit_to_target` override goes through the existing hatch.
  - `core/mission_creation.py:~1080`: mint `commit_to_target` and `mission_branch`, and refuse an existing branch.
  - `cli/commands/agent/mission_create.py`: the `--commit-to-target` flag.
  - `core/paths.py:~770`: a reader beside `read_retention_from_meta`.
  - Write target: `mission_runtime/resolution.py`; the `single_branch` write target becomes `meta.mission_branch` when set.
  - `core/owned_mission.py:~105`: an `expected_write_branch` resolver.
  - Consolidate:
    - `consolidation/executor.py:~1469,3170`: the mission→target phase runs whenever `mission_branch != target_branch`.
    - `consolidation/reconciliation.py:~1054`: authored blobs for the repo-root lane come from `base..mission_branch`.
    - Switch the checkout back to the target before teardown.
- **Sequencing/depends-on**: IC-03.
- **Risks**:
  - This is the largest surface and touches sibling-owned consolidation (C-005).
  - The coord-vs-mission branch name is shared by design; readers must key on `meta.topology` and `coordination_branch`, never on ref shape.

### IC-06 — Truthful docs and glossary

- **Purpose**: correct the doc drift and add a topology glossary entry.
- **Relevant requirements**: FR-023
- **Affected surfaces**:
  - `CLAUDE.md` (Execution Workspace Strategy)
  - `docs/architecture/execution-lanes.md:39-41`
  - `docs/context/orchestration.md` (new `#topology` entry, or a new `docs/context/topology.md` linked from it)
  - `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-02…IC-05.
- **Risks**: docs freshness and SEO gates (`scripts/docs/check_docs_freshness.py`); terminology gate.

## Validation strategy (targeted, C-007)

- **Per work package:** its own new or changed test files, plus the owning module's existing tests:
  - `tests/lanes/`
  - `tests/workspace/` (if present)
  - `tests/specify_cli/cli/commands/test_mission_create*.py`
  - `tests/migration/`
  - `tests/policy/`
  - `tests/consolidation/` (only the files that touch the changed functions)
- **Named architectural gates:**
  - `test_layer_rules.py`
  - `test_no_legacy_terminology.py`
  - `test_ruff_format_enforcement.py` (via `ruff format --check`)
  - the new planning-lane gate
  - `test_no_dead_symbols.py` if `__all__` changes
- **Baseline:** `make test-fast`.

## Post-plan squad folds (binding; supersede conflicting text above)

Two lenses reviewed the plan: code-truth (reviewer-renata) and red-first feasibility (paula-patterns). The folds below override any earlier text in this plan that conflicts with them.

### Blockers

- **B1: kind-based deciders that must key on `is_repo_root_lane`.** These places decide by work-package kind or lane assignment and each needs one arm keyed on `is_repo_root_lane`:
  - `implement.py:1576` (`_resolve_execution_lane`)
  - `implement_support.py:136-150` (`create_lane_workspace`). Today it early-returns only for `PLANNING_ARTIFACT` and raises `ValueError` for a repo-root code work package.
  - `orchestrator_api/commands.py:1343` (`_resolve_start_workspace`)
  - `orchestrator_api/commands.py:1427` (`_resolve_existing_workspace`)
  - `lanes/recovery.py:403,701,723`

  `allocate_lane_worktree` and `predict_lane_worktree` refuse a repo-root lane.
- **B2: claim-time base.** A repo-root lane has no lane branch, so the for_review gate has no base to compare against.
  - At claim (implement start, and on resume if the ref is missing), record `refs/spec-kitty/wp-base/<mission_slug>/<WP>` = the write checkout's HEAD.
  - The for_review gate for a repo-root lane evaluates `wp-base..HEAD` in the write checkout. With no commit since claim it refuses, which is the control case.
  - This applies to planning_artifact work packages too, which is the FR-001 fix.
  - The ref is deleted at terminal states.
- **B3: `is_planning_artifact_only` stays lane-based.** It is **not** split by work-package kind. Instead:
  - Add `has_code_wps(manifest)` for the no-code claims at `acceptance/gates_core.py:277,770` and `consolidation/executor.py:1671`.
  - For single_branch, `manifest.mission_branch` = `meta.mission_branch` if set, otherwise `target_branch`. This follows the `_synthesize_no_lane_manifest` precedent at `executor.py:3326-3383`.
  - Override `compute_and_persist._preserved_mission_branch` (`:68-81,170`) for single_branch.
  - `executor.py:680` keys on `is_repo_root_lane`.
  - `orchestrator_api/commands.py:997` keeps a single_branch mission off the lane-merge path.
  - The `--skip-lanes` behaviour must not regress.

### Majors

- **M1: other lane-worktree creators.** Two more places create lane worktrees:
  - `lanes/auto_rebase.py:~928` / `lifecycle_sync.py:137-139`
  - the review `-b` path at `agent/workflow.py:1809-1821`

  Route both through the allocator, or apply `assert_topology_matches_manifest` and tip recording there. For a repo-root lane, review runs in the write checkout.
- **M2: naming API split.**
  - `code_lane_branch_name(slug, lane_id)` raises for `lane-planning`.
  - `lane_branch_name(slug, lane_id, *, target_branch: str)` makes the target a required keyword, which mypy enforces.
  - Update every caller: `worktree_allocator.py:491` (`predict_lane_worktree`), `sparse_checkout.py:232`, `backfill_ownership.py:148`, `mission_type.py:796,1005`, `context.py:846,864`, `implement_support.py:~478`, `worktree_allocator.py:~1253`.
  - The architectural gate then only has to assert that the old positional form is gone.
- **M3: topology passed explicitly to `compute_and_write_lanes`.** All three callers pass it:
  - `tasks_finalize.py:382`
  - `mission_finalize.py:2503`
  - `migration/mission_state.py:1621`. This is `doctor mission-state --fix`, which must catch and report the new error instead of crashing.

  The fail-closed assertion goes after `compute_and_persist.py:170` and before the write at `:172`.
- **M4: hook contract fixes.**
  - Match the lane-id suffix: `id=${b##*-lane-}; case "$id" in ''|*[!a-z]*) exit 0;; esac`. A slug that merely contains `-lane-` must not match.
  - Also install a `post-rewrite` recorder, which runs after a rebase or amend once HEAD is re-attached.
  - Legacy `{mission}-{wp}` workspaces are out of scope; this is a documented residual.
- **M5: separate installer for the recorder.** `install_lane_tip_recorder` installs into `git rev-parse --git-path hooks` and skips with a warning when a foreign hook is present. The existing pre-commit installer is unchanged.
  - Installed at lane allocation.
  - Installed for existing clones by an upgrade migration (`m_4_0_0rc5_install_lane_tip_recorder`).
- **M6: FR-010 cannot reuse `ACTIVE_WP_CONTEXT_AMBIGUOUS`.** That logic (`context.py:437-477`) is keyed on WorkspaceContext. Add a new helper `in_progress_wps_in_write_checkout(repo_root, write_checkout)` that scans the status of single_branch missions whose resolved write checkout equals this one.
- **M7: guard order.**
  1. The coord base-unreachable check (#4889) runs first, unchanged.
  2. Then the tip check runs for every topology. The base-reachable early return at `worktree_allocator.py:350` is removed for the tip path.

  #4889 FR-009 tests that relied on base-reachable re-open are re-pinned only where the tip is absorbed. Any flip is justified in the work package. The trigger set is the existing `{in_progress, blocked, for_review, in_review}`; the data-model's "non-terminal" means this set.
- **M8: resolver precedence.** The `is_repo_root_lane` check runs before the WorkspaceContext lookup (`context.py:~804`), so a stale record never routes a single_branch work package to a lane worktree.

### Minors

- `recovery.py:817` hardcodes the stamp.
- `context/resolver.py:270` computes `authoritative_ref` and must honour `meta.mission_branch` (IC-05).
- `planning_artifact_wps` in the finalize JSON stays derived from work-package kind.
- `tasks_status_view.py:140` must not report repo-root code work packages as `stale_detection_unavailable`.
- `lane_tip.py` must not import `consolidation.*`. The merge-tree probe lives in `lane_tip.py`, and git < 2.38 raises `AbsorptionUnsupported`.
- Add a control test that the `has_code_lanes` change leaves un-stamped planning-only missions correctly classified.

### Feasibility and fixtures

- **#5115 test.** Clone `tests/lanes/test_lane_allocation_integrity_e2e.py::_build_coord_mission` as `_build_lanes_mission` (no coordination branch, `topology: lanes`).
  - Reuse `_run_cli_implement`, `_destroy_lane`, `_commit_real_work`, `_wp_context` and `_ids()`.
  - Commit an owned file with a plain `git commit`.
  - Set `GIT_CONFIG_GLOBAL` to an empty file so a global `core.hooksPath` cannot interfere.
  - Assert the tip ref after the CLI assertions.
- **#5100 test.** Two cases:
  - Unprotected: `tests/e2e/conftest.py::e2e_project` (branch `e2e-status-commit`). Re-export it with `from tests.e2e.conftest import e2e_project  # noqa: F401`, following the `protected_target_fixtures` precedent.
  - Protected: `create --topology single_branch` on `main` with `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` unset (`tests/git/protected_target_fixtures.py`).
  - Prefer `CliRunner`, with a module-scoped template copied per test.
  - Markers: `integration`, `git_repo`, `regression`.
  - The `--commit-to-target` case is its own test function, because it is a usage error on main today.
- **Migration test** lives at `tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py`. It uses `MigrationRegistry.get_by_id("4_0_0rc5_single_branch_code_lanes_restamp")` and asserts the result is not None, rather than importing the module. An ImportError is not a valid red.
- **Blast radius.** `tests/e2e/…::TestFullCLIWorkflow::test_full_workflow_sequence` asserts `.worktrees/<slug>-lane-a` on a default-topology mission. It stays valid after FR-013 because the default becomes `lanes`. Re-run it in the create-default work package.

### Work package order (adopted)

| WP | Scope | Addresses |
|---|---|---|
| WP01 | Campsite, behaviour-preserving: extract the allocator guard helpers; split `_resolve_workspace_for_wp_impl` into per-arm helpers; complexity ≤ 15 | — |
| WP02 | Naming API split; for_review gate through the claim-base; repo-root arms in implement, orchestrator and recovery. Planning work packages only, which already resolve to the repo root. | IC-01, B1, B2, M2 |
| WP03 | Predicates `has_code_lanes`, `has_code_wps`, `is_repo_root_lane`; `assert_topology_matches_manifest` at the writers; the topology parameter; re-stamp migration, operator CLI and doctor finding; the 64-mission data commit | IC-02, M3 |
| WP04 | single_branch readers: the stamp property on every path; refusals (dirty, in-progress scan, wrong branch); resolver precedence; dependency-merge skip; consolidate and orchestrator-merge arms for an unprotected single_branch; `tasks_status_view` | IC-03, B3, M6, M8, M1 |
| WP05 | Activation: `compute_lanes(topology=single_branch)` writes the one repo-root lane with `mission_branch = target`. The #5100 red-first test goes green for the unprotected cases. | IC-03 |
| WP06 | Create default becomes `lanes`; pinned create tests updated | FR-013 |
| WP07 | Lane work tip: `lane_tip.py`; recorder installer (post-commit and post-rewrite) plus the install migration; guard order; recording at spec-kitty advances; the orchestrator writes context only through the allocator. The #5115 red-first test goes green. | IC-04, M1, M4, M5, M7 |
| WP08 | Protected-target mission branch: create-time mint; `--commit-to-target`; write-target and authoritative-ref arm; `expected_write_branch`; consolidate mission→target phase and blob source. The #5100 protected cases go green. | IC-05 |
| WP09 | Docs, glossary and changelog | IC-06 |

**Red-first placement.** Each red-first test is committed RED at the start of the work package that first turns part of it green:
- #5100: at WP05. The protected cases are marked `xfail(strict=True)` until WP08.
- #5115: at WP07.
- The migration test: at the start of WP03.
