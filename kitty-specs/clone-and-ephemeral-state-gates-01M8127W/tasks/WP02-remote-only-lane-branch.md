---
work_package_id: WP02
title: Review creates a remote-only lane branch through one owning-remote helper (#7806)
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
- NFR-001
- C-001
- SC-002
planning_base_branch: issue-7809-clone-ephemeral-state-gates
merge_target_branch: issue-7809-clone-ephemeral-state-gates
branch_strategy: Planning artifacts for this mission were generated on issue-7809-clone-ephemeral-state-gates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7809-clone-ephemeral-state-gates unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-clone-and-ephemeral-state-gates-01M8127W
base_commit: e8b9fdec5ab0b6c7fec8f7a98de65d0b7dcaa455
created_at: '2026-11-22T07:37:28.345860+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
history: []
agent_profile: implementer-ivan
authoritative_surface: src/kernel/git/tracking_branch.py
create_intent:
- src/kernel/git/tracking_branch.py
- tests/kernel/git/test_tracking_branch.py
- tests/specify_cli/coordination/test_review_remote_only_lane_7806.py
- docs/changelog/unreleased/7806.fixed.md
execution_mode: code_change
owned_files:
- src/kernel/git/tracking_branch.py
- tests/kernel/git/test_tracking_branch.py
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/workspace/context.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/specify_cli/coordination/test_review_remote_only_lane_7806.py
- docs/changelog/unreleased/7806.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Review creates a remote-only lane branch through one owning-remote helper (#7806)

## Objective (#7806)

In a teammate's clone, `agent action review` fails `LANE_AUTO_REBASE_FAILED ... is not a local branch` when the lane branch exists only as `refs/remotes/<remote>/<lane>`. After this WP:

- review creates the local lane branch from the owning remote's tracking ref, with `--track`;
- review refuses when no ref exists;
- review refuses `DESTROYED_LANE` when the local lane-tip record holds work the tracking ref lacks.

The same owning-remote rule serves the coordination branch (PR #7804) and the lane base lookup, through ONE kernel helper.

## Baseline

This Mission's target branch is stacked on PR #7804 (`origin/issue-5936-coord-materialize-from-remote`). Its helpers `coord_branch_tracking_ref` and `ensure_coord_branch_local_head` are in `src/specify_cli/coordination/surface_resolver.py`. Read them first (`git show HEAD:src/specify_cli/coordination/surface_resolver.py`, about lines 800-870).

## Grounding

- **Order of review.** `review()` (`src/specify_cli/cli/commands/agent/workflow.py:2617`) runs:
  1. `_reconcile_review_lane` (`:2463`, the origin freshness step);
  2. the claim (`:2719` → `workflow_executor.review_claim_transition` → `lanes/lifecycle_sync.py:83`, which opens the lane checkout with `create_branch_from=None` and so fails on a missing local head, `lane_checkout.py:300`);
  3. `_prepare_review_workspace` (`:2734`).
- **`_reconcile_review_lane`** gets `CREATE_FROM` (with `remote_ref`) from `git/origin_freshness.py:697` when the remote has the branch and the clone has no local head. Today it only returns that ref (`:2485-2486`). Nothing is created before the claim.
- **`workspace/context.py:1228 resolve_lane_base_ref`** is a third copy of the probe (`tracking_ref(resolve_remote(...) or "origin", lane)`). Its documented fallback (`origin` when no owner resolves) is kept.
- **Destroyed-lane guard.** `lanes/worktree_allocator.py:500-523`. The lane-tip ref is `refs/spec-kitty/lane-tip/<branch>` (`lanes/lane_tip.py`).

## Design (ruled: auto-create, stacked on #7804)

- **New `src/kernel/git/tracking_branch.py`** (declare `__all__`). It is refs-only and contacts no remote, so it is NOT in `kernel/git/remote.py`.
  - `owning_tracking_ref(repo_root: Path, branch: str) -> str | None`: `resolve_remote` + `tracking_ref` + `run_git(..., "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}", check=False)`.
  - `ensure_local_tracking_branch(repo_root: Path, branch: str) -> bool`: True if the branch is already a local head. Otherwise `git branch --track --end-of-options <b> <ref>`. Tolerate a concurrent creation. Return False and write nothing when there is no ref. Log at info.
  - Every new symbol needs a caller in `src/` (dead-symbol gate).
- **`surface_resolver.py`.** `coord_branch_tracking_ref` and `ensure_coord_branch_local_head` delegate to the kernel helper. Keep their names and behaviour: PR #7804's tests must still pass unchanged.
- **`resolve_lane_base_ref`** uses `owning_tracking_ref` when an owner resolves, and keeps the `origin` fallback.
- **`_reconcile_review_lane`.** Before returning, when the lane branch has no local head:
  - if `refs/spec-kitty/lane-tip/<lane>` exists and is not an ancestor of the owning tracking ref, refuse with the existing destroyed-lane refusal (reuse its code and remedy text, do not invent a new one);
  - otherwise call `ensure_local_tracking_branch`;
  - when the origin check is off, unreachable or ambiguous, still create from the local tracking ref, but print a warning that it was not refreshed;
  - an ambiguous owner (`resolve_remote` → None) never picks a remote, so nothing is created and today's refusal stands.

  The claim's lane sync and `_create_review_worktree` then see a local head.
- **`lifecycle_sync` stays fail-closed.** Do not edit it.

## Subtasks

- **T005** Red-first e2e `tests/specify_cli/coordination/test_review_remote_only_lane_7806.py`. Real bare origin, clone A (author: implement WP01, commit, `for_review`, `push --all`) and clone B (`git clone`). Reuse the fixture shape of PR #7804's `tests/specify_cli/coordination/test_coord_clone_writer_5936.py` (`team`, `_teammate`, `_has_local_head`); import or copy helpers, but do not edit that file. Arms:
  - B `agent action review WP01` succeeds and the lane is a local head tracking origin;
  - fail-closed control: no ref anywhere → refuses;
  - destroyed-lane control: a lane-tip ref ahead of origin → refuses `DESTROYED_LANE`.

  Run the CLI from this checkout's `.venv`. Commit it red.
- **T006** Kernel helper plus unit tests `tests/kernel/git/test_tracking_branch.py`: no remote; single remote; `branch.<b>.remote` set; several remotes without origin (None); concurrent creation; `--track` with `branch.autoSetupMerge=false`.
- **T007** Route the PR #7804 helpers and `resolve_lane_base_ref` through it.
- **T008** `_reconcile_review_lane` creation, destroyed-lane refusal and warning.
- **T009** Changelog fragment `docs/changelog/unreleased/7806.fixed.md`.

## Tests to run

- New files.
- `tests/specify_cli/coordination/` (includes PR #7804's `*_5936` tests).
- `tests/kernel/`.
- Tests referencing `resolve_lane_base_ref`, `_reconcile_review_lane` and `plan_review_lane` (grep).
- `tests/specify_cli/cli/commands/test_doctor_coordination.py` and `test_coordination_remedy_5113.py`. Both are out-of-matrix: run them and disclose them.
- Gates: `tests/architectural/test_remote_contact_owner.py`, `test_lane_checkout_single_seam.py`, `test_layer_rules.py`, `test_no_dead_symbols.py`.
- `make test-fast`.

## Do This First

1. Load the agent profile named in the frontmatter (`/spk-charter-profile-load`). Read `.kittify/charter/charter.md` and `CLAUDE.md`.
2. Read `kitty-specs/clone-and-ephemeral-state-gates-01M8127W/research.md`, which holds the code grounding, the squad corrections and the operator rulings, and this Mission's `spec.md` and `plan.md`.
3. Implement only in the workspace that `spec-kitty agent action implement <WP> --mission clone-and-ephemeral-state-gates-01M8127W --agent <you>` resolves. Never `cd` into a reconstructed path.

## Working rules (binding)

- **ATDD, red-first.** The first commit on the lane is the failing acceptance test, through the pre-existing entry point named below. It is committed on its own BEFORE any implementation commit. Record the red run (command + failing count) in the WP history (`spec-kitty agent tasks add-history`).
- **Gates.** Code must pass `ruff check`, `ruff format --check --force-exclude <files>`, and `mypy` on touched files with zero new issues. No new `# noqa` / `# type: ignore` without an inline rationale. Keep Sonar complexity at 15 or below, hoist repeated literals into constants, and test every new branch.
- **Tests to run.** Your new tests, the test files of every module you touch (find them with `grep -rl "<module>" tests --include="*.py"`), the owning subsystem directories named below, `make test-fast`, and the named architectural gates. Never run a full `tests/architectural/`, `make test-full`, or e2e/performance sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Out-of-matrix disclosure (#7801).** If you change any test under an out-of-matrix directory (for example `tests/specify_cli/cli/commands`, `tests/specify_cli/review`, `tests/specify_cli/lanes`, `tests/specify_cli/tasks`, `tests/integration`, `tests/contract`; the full list is `out_of_matrix_test_dirs` in `.github/ci-module-registry.yml`), name each file in your WP history as "nightly-only" and run it locally.
- **Changelog fragment.** Use the path in `owned_files`. Follow `docs/changelog/unreleased/README.md` and run `uv run --frozen python -m scripts.docs.check_changelog_style`.
- **Terminology.** Mission, work package, lane. Never `feature` in new prose or identifiers.
- **No push from the CLI.** Add no `git push` to any code path. Contact no remote outside `kernel.git.remote`.

## Hand-off to review

Move to `for_review` with `spec-kitty agent tasks move-task <WP> --to for_review --mission clone-and-ephemeral-state-gates-01M8127W`, after committing on the lane and pushing the lane branch to origin.

## Reviewer note (binding, because of #7802)

After approving, the reviewer pushes the lane branch so origin holds the approval's `lane_head`. The reviewer then confirms with `git ls-remote origin <lane-branch>` that the remote tip equals, or contains, the stamped SHA before ending the session.
