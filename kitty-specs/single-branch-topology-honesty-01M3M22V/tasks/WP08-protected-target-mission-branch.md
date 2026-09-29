---
work_package_id: WP08
title: Protected-target mission branch
dependencies:
- WP07
requirement_refs:
- FR-007
- FR-008
- FR-012
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-29T06:12:12.446220+00:00'
subtasks:
- T034
- T035
- T036
- T037
- T038
phase: Phase 7 - Protected target
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/git/test_protection_policy_protected_target.py
- tests/core/test_mission_create_protected_single_branch.py
- tests/specify_cli/consolidation/test_single_branch_mission_to_target.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/git/protection_policy.py
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/paths.py
- src/specify_cli/core/owned_mission.py
- src/mission_runtime/resolution.py
- src/specify_cli/consolidation/reconciliation.py
- tests/git/test_protection_policy_protected_target.py
- tests/core/test_mission_create_protected_single_branch.py
- tests/specify_cli/consolidation/test_single_branch_mission_to_target.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Protected-target mission branch

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile named in the frontmatter (`python-pedro`, `implementer`, `claude`) and follow its guidance.

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref` and address every item before continuing.

---

## Objectives & Success Criteria

This WP implements the operator decision's amendment to item 4 (FR-007, FR-008, FR-012 protected case; US3). When a `single_branch` mission targets a **protected** branch, the flow is:

- **Protected** means the primary branch, or a branch `ProtectionPolicy` reports as protected (C-002, research R-5).
- **Create:** `mission create` mints `kitty/mission-<slug>-<mid8>` and checks it out in the write checkout (no worktree). It records `meta.json` `mission_branch` and routes every later planning, status and code write to that branch.
  - It refuses if the branch already exists.
  - The mint happens at **create**, not at implement (research R-8): protected targets refuse planning commits, so the branch must exist before specify/plan/tasks commit.
- **Opt-out:** `--commit-to-target` skips the mint. It is persisted as `commit_to_target: true` and honoured through `ProtectionPolicy`'s existing operator-hatch concept, so there is no second bypass.
- **Implement:** requires the write checkout to be on `mission_branch`. The wrong-branch refusal from WP04 now keys on `expected_write_branch`.
- **Consolidate:** lands `mission_branch` onto `target_branch` through the mission→target phase, then switches the write checkout back to `target_branch` before deleting `mission_branch`. It never removes the repository root checkout or `target_branch`.

**Done when:**
- The #5100 protected-case tests (xfail strict from WP05) now PASS, with their xfail markers removed.
- The new unit and consolidation tests pass.
- There is no regression in coord or lanes create.

## Context & Constraints

- Read first:
  - `spec.md` US3 and its edge cases
  - `research.md` R-5, R-8, R-9
  - `plan.md` IC-05 and the folds (B3; minor "`context/resolver.py:270` `authoritative_ref`")
  - `contracts/single-branch-execution.md` (consolidate table)
  - `data-model.md` (`meta.json` fields)
- **Mirror the retention-field pattern** for `commit_to_target`:
  - mint `True` only (`core/mission_creation.py:~1080-1083`);
  - add `MissionMetaOptional` (`mission_metadata.py:~88`, out-of-map);
  - add a fail-closed raw reader beside `read_retention_from_meta` in `core/paths.py:~770`. A non-boolean value **fails closed** and is never coerced by truthiness.
- **Branch-name sharing.** `coord_branch_name` delegates to `mission_branch_name` (`lanes/branch_naming.py:645`), so both produce the same name. Readers must key on `meta.topology` and on `coordination_branch` (null for these missions), never on ref shape.
  - Grep `kitty/mission-` in `src/specify_cli/lanes/recovery.py` (`:137` globs it) and in the doctor.
  - Make sure neither classifies a single_branch `mission_branch` as coord or orphan. Add a test.
- **Sibling-owned consolidation (C-005).** `consolidation/executor.py` edits are out-of-map and minimal:
  - make the `_phase_mission_to_target` early return at `:~1469` conditional on `mission_branch == target_branch`;
  - add the checkout switch-back before teardown.

  List every hunk in the Activity Log.
- **Out-of-map edits** (rationale required):
  - `cli/commands/agent/mission_create.py` (the flag)
  - `mission_metadata.py`
  - `context/resolver.py:~270`
  - `consolidation/executor.py`
  - `lanes/recovery.py`
  - WP04's refusal site in `implement`, if needed

## Branch Strategy

- **Planning base / merge target**: `issue-5100-single-branch-topology`. Run `spec-kitty implement WP08 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

### Red-first (charter C-011; analysis finding C1)

Before any implementation commit in this WP, commit the new behaviour tests **alone**, and show that they are RED against the WP's planning base.

- The failure must be an assertion failure. An ImportError, or a crash in a fixture, does not count as red.
- Record the red run (command plus the failing test names) in the Activity Log.
- The reviewer verifies red→green.

The red set for this WP is the new tests in T034 to T037. The `xfail(strict=True)` protected cases from WP05 are additional red proof.


### Subtask T034 – Protection query and `commit_to_target` meta

- In `git/protection_policy.py`, add `ProtectionPolicy.is_protected_target(self, branch: str, *, primary_branch: str) -> bool`, which returns `branch == primary_branch or self.is_protected(branch)`.
- Document in the docstring that this is the #5100 decision's "primary plus configured" rule.
- Add a reader `read_commit_to_target(meta) -> bool` in `core/paths.py`:
  - absent → `False`;
  - a non-bool → raise the same error type that retention uses.
- Tests go in `tests/git/test_protection_policy_protected_target.py`:
  - a primary branch named `trunk` with no `origin/HEAD` is protected;
  - a configured list `[release]` still protects the primary;
  - `[]` still protects the primary;
  - an unrelated feature branch is not protected.

### Subtask T035 – `--commit-to-target`, create-time mint, refuse an existing branch

- `mission_create.py`: add a `--commit-to-target/--no-commit-to-target` option (default off) and pass it through to `core/mission_creation.py`.
- In `core/mission_creation.py`, after the topology is resolved and **before any mission file is committed**, check:
  - topology is `SINGLE_BRANCH`,
  - the target is a protected target,
  - `commit_to_target` is false.

  When all three hold:
  1. Compute the name with `mission_branch_name(slug, mid8)`, the existing composer. Do not compose it a second time.
  2. If that ref exists, refuse with `MISSION_BRANCH_EXISTS` and name the branch.
  3. Create the branch at the target tip and check it out in the write checkout. Reuse the `--start-branch` checkout mechanics where possible, and `_ensure_mission_branch` (`worktree_allocator.py:1419`) for creation if it fits.
  4. Record `mission_branch` in `meta.json`.
- If the write checkout is dirty, refuse before switching.
- Tests go in `tests/core/test_mission_create_protected_single_branch.py`:
  - mint + checkout + meta field;
  - `--commit-to-target` → no mint, and the meta flag is `true`;
  - existing branch → refused;
  - unprotected target → no mint (control);
  - `lanes` topology on a protected target → unchanged (control).

### Subtask T036 – Write-target and authoritative-ref arm; `expected_write_branch`

- In `mission_runtime/resolution.py`, for single_branch with `meta.mission_branch` set, the write target (the destination ref for all artifact kinds) is `mission_branch`. Otherwise it stays `target_branch`.
  - The commit router must not refuse these writes. Check commit-router rule 3 (`coordination/surface_authority.py:245`, `commit_router.py:337-367`): the destination is now the unprotected mission branch.
  - `safe_commit`'s HEAD == destination assertion must hold.
- In `context/resolver.py:~270`, `authoritative_ref` honours `mission_branch`.
- In `core/owned_mission.py`, add `expected_write_branch(meta, policy, primary_branch) -> str`. It returns `mission_branch` when set, otherwise `target_branch`.
  - `resolve_owned_mission` (`:~105`) currently refuses protected targets and requires the current branch to equal `target_branch`. Change it to compare against `expected_write_branch`.
  - WP04's wrong-branch refusal uses the same helper.
- Add a test: a status transition on a protected-target single_branch mission commits to `mission_branch` with no `SafeCommitHeadMismatch`.
- Add a test (US3.2): with the write checkout switched to the target branch, `implement WP01` on the protected mission is refused with `WRITE_CHECKOUT_WRONG_BRANCH` naming `mission_branch`.

### Subtask T037 – Consolidate mission→target for protected single_branch

- `executor.py`: run `_phase_mission_to_target` whenever `manifest.mission_branch != manifest.target_branch`, including for single_branch.
- `reconciliation.py` (`~:613,1054`): the authored-blob source for the repo-root lane of a single_branch mission is the first-parent history of `base..mission_branch`, so the squash blob-attribution axis has content. Keep it fail-closed: an empty set when WPs are approved must still refuse.
- After landing:
  1. `git checkout <target_branch>` in the write checkout.
  2. Delete `mission_branch`, honouring the retention flags (`--keep-branch` / `retain_branches`).
  3. Never remove the repository root checkout or `target_branch`.
- Tests go in `tests/specify_cli/consolidation/test_single_branch_mission_to_target.py`:
  - end state: the target contains the work, the checkout is on the target, the mission branch is gone, and the root checkout is intact;
  - retention keeps the branch;
  - unprotected single_branch still does no landing (the WP04 behaviour).

### Subtask T038 – Flip the #5100 protected-case xfails

- Remove `xfail` from `test_protected_target_mints_mission_branch` and `test_commit_to_target_overrides` in `tests/integration/test_issue_5100_single_branch_topology.py`. This file is owned by WP05; the edit is out-of-map, removing the markers only.
- Make them pass, and add the assertion that `implement WP01` on the protected mission runs on `mission_branch`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/git/test_protection_policy_protected_target.py tests/core/test_mission_create_protected_single_branch.py tests/specify_cli/consolidation/test_single_branch_mission_to_target.py tests/integration/test_issue_5100_single_branch_topology.py -q
grep -rl "ProtectionPolicy\|read_retention_from_meta\|resolve_owned_mission\|_phase_mission_to_target\|authoritative_ref" tests/ --include=*.py   # run each listed file (not directories)
.venv/bin/python -m pytest tests/git/ -q -k protect   # only if the listed files are few; otherwise name them
make test-fast
.venv/bin/mypy --strict <touched files> ; .venv/bin/ruff check . ; .venv/bin/ruff format --check .
```

## Risks & Mitigations

- **Largest surface; it touches the sibling-owned consolidation.** Keep the hunks minimal and listed. If a consolidation change grows beyond about 40 lines, stop and report instead of widening.
- **Switching the operator's checkout at create.** Only switch when the tree is clean. Refusal is the safe default.
- **Ref-shape readers mis-classifying the mission branch.** Add explicit tests for recovery and doctor.

## Review Guidance

- The create-time mint happens before any mission file is committed.
- `commit_to_target` fails closed on a non-bool.
- The consolidate end state matches the contract.
- The xfails are removed, and the tests are green for the right reason.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
- 2026-09-29T00:00:00Z – claude – Cycle 4 (FR-008: `commit_to_target` honoured as a mission-scoped hatch).
  - **Red run** (commit `68d22c51`, tests only): `PYTHONPATH=<lane>/src .venv/bin/python -m pytest tests/integration/test_issue_5100_single_branch_topology.py -k commit_to_target` -> `FAILED ...::test_commit_to_target_overrides` at `assert finalized.exit_code == 0`: `Bookkeeping refused: PROTECTED_BRANCH_REFUSED: Refusing to record 'status transition WP01': destination ref 'main' is on this project's protected branch list.` (assertion failure). `tests/git/test_protection_policy_mission_scope.py`: 11 failed, `AttributeError: type object 'ProtectionPolicy' has no attribute 'resolve_for_mission'` (seam absent; negative controls only red for that reason).
  - **Green** (commit `7435a64a`): the integration test passes; named 23-file set 252 passed, 0 failed.
  - **Mutation (cycle 4):** removed the `mission_bypass_branch` fold in `ProtectionPolicy.is_protected` -> `test_commit_to_target_overrides` red with the same `PROTECTED_BRANCH_REFUSED` (1 failed); fold restored, not committed.
  - **Out-of-map files (rationale each):**
    - `coordination/policy.py` - `WorkflowMutationPolicy` decides protection via `resolve_for_mission(repo_root, change_set.mission_slug)` so bookkeeping commits honour the mission hatch.
    - `coordination/types.py` - `GitChangeSet.mission_slug` carries the mission into that decision.
    - `coordination/transaction.py` - both `GitChangeSet` builds pass `safe_mission_slug`.
    - `coordination/commit_router.py` - `_mission_scoped` folds the mission's `commit_to_target` into an unscoped policy before surface-authority rule 6, for callers that pass `ProtectionPolicy.resolve`.
    - `git/commit_helpers.py` - `_single_mission_slug` + fold in `preflight_commit`, covering every `safe_commit` caller whose paths are all in one mission dir.
    - `cli/commands/implement.py` - implement's status-commit protection gate and narrow-triple site consult `mission_write_bypass`.
    - `cli/commands/agent/tasks_shared.py` - the two `_protected_branch_status_commit_error` / `_skip_target_branch_commit` gates consult `mission_write_bypass`.
    - `cli/commands/agent/tasks_move_task.py` - passes `st.mission_slug` to the gate so move-task on a ctt mission succeeds.
    - `cli/commands/agent/tasks_map_requirements.py` - passes `st.mission_slug` to the same gate.
    - `cli/commands/agent/mission_finalize.py` - issue-matrix, acceptance-matrix and tasks-commit policies use `resolve_for_mission` so finalize-tasks commits on the ctt target.
    - `core/owned_mission.py` - owned-checkout resolver scopes its policies with `scoped_to_mission(meta)` (owned file in WP08 map; listed for completeness).
- 2026-09-29T00:00:00Z – claude – Cycle 5 (review-feedback-5: untested safety seams).
  - New `tests/git/test_commit_to_target_scope_guards.py` (commit `ee69277a`, plus a mypy annotation follow-up): `_single_mission_slug` parametrised; real-repo `preflight_commit` (ctt-only -> bypass; ctt + `src/x.py` -> `ProtectedBranchRefused`; two missions -> refused; unflagged mission -> refused); `commit_for_mission` with an UNSCOPED `ProtectionPolicy.resolve` commits for a ctt mission on protected `main` and refuses an unflagged one.
  - **Mutation 1:** `_single_mission_slug` `return None` -> `continue` for a non-`kitty-specs/<slug>/` path: `test_single_mission_slug[paths1-None]` and `test_preflight_mixed_code_and_ctt_is_refused` FAIL (2 failed, 10 passed). Restored, not committed.
  - **Mutation 2:** `commit_router` `_mission_scoped(policy, ...).is_protected(...)` reverted to `policy.is_protected(...)`: `test_router_folds_commit_to_target_for_unscoped_policy` FAILS (1 failed, 11 passed). Restored, not committed.
  - Optional nit 4 (consolidate integration assertion) not added: verified manually by the reviewer; not cheap.
