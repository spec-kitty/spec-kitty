---
work_package_id: WP03
title: Approval stamp survives the review's own sync merge (#7802)
dependencies: []
requirement_refs:
- FR-009
- FR-010
- FR-011
- NFR-001
- NFR-002
- C-002
- C-003
- SC-003
planning_base_branch: issue-7809-clone-ephemeral-state-gates
merge_target_branch: issue-7809-clone-ephemeral-state-gates
branch_strategy: Planning artifacts for this mission were generated on issue-7809-clone-ephemeral-state-gates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7809-clone-ephemeral-state-gates unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-clone-and-ephemeral-state-gates-01M8127W
base_commit: 7fbbee86234ee687d370aab8246c989c6fb44f01
created_at: '2026-11-22T07:37:16.653082+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/lanes/auto_rebase.py
create_intent:
- tests/consolidation/test_approval_stamp_presync_7802.py
- tests/status/test_lane_head_presync_7802.py
- docs/changelog/unreleased/7802.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/auto_rebase.py
- src/specify_cli/status/lane_head.py
- src/specify_cli/status/transition_pipeline.py
- src/specify_cli/status/__init__.py
- src/specify_cli/status/cutover_eligibility.py
- src/specify_cli/consolidation/approved_bound.py
- src/specify_cli/consolidation/write_branch_bound.py
- src/specify_cli/consolidation/approved_attestation.py
- src/specify_cli/consolidation/git_probes.py
- src/specify_cli/consolidation/commit_to_target_stamps.py
- tests/consolidation/test_approval_stamp_presync_7802.py
- tests/status/test_lane_head_presync_7802.py
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
- docs/changelog/unreleased/7802.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Approval stamp survives the review's own sync merge (#7802)

## Objective (#7802)

The review claim always merges the coordination branch into the lane with a local `--no-ff` merge. A later approval stamps that merge as `lane_head`. An ephemeral reviewer never pushes it, so `consolidate` elsewhere refuses `APPROVAL_STAMP_NOT_ON_LANE`.

After this WP (operator ruling: dual stamp):

- the approval also records `policy_metadata.lane_head_presync`, the lane tip before the review's own sync merge;
- the approved bound accepts whichever recorded stamp the lane contains;
- an absent stamp object gets its own remedy text.

No push, no remote contact, and the bound is not weakened.

## Grounding

- **The sync merge.** `lanes/auto_rebase.py:991 attempt_auto_rebase`, `git merge --no-edit --no-ff --no-commit <coord>` (`:1039-1042`), concluded at `:1060`. Called from `lanes/lifecycle_sync.py:169`; do not edit `lifecycle_sync.py`.
- **The stamp.** `status/lane_head.py:211-230 _branch_head` reads local `refs/heads/<lane>`; `_read_lane_head` is at `:285`. `status/transition_pipeline.py:201 _stamped_policy_metadata` sets `lane_head` (`:242`). The pipeline is git-free; the reader is injected (`coordination/status_transition.py:1675`, `:2030`). Do not edit `status_transition.py`; extend the reading instead.
- **The bound.** `consolidation/approved_bound.py`:
  - `stamp_refusal` `:496-511` (`sha_reachable_from` = `merge-base --is-ancestor`, absent object counts as not reachable);
  - `check_lane` `:515`;
  - `content_commits` drops merges at `:465-478`.
  - Other consumers: `write_branch_bound.py:205,365` (tier 2 drops merges, `:155`) and `approved_attestation.py:203`.
  - `git_probes.commit_in_clone` (`:444`) distinguishes an absent object.
- **Stamp key lists.** `consolidation/commit_to_target_stamps.py:29 WINDOW_STAMP_KEYS` and `status/cutover_eligibility.py:94 _PROVENANCE_KEYS` must include the new key. Export `LANE_HEAD_PRESYNC_KEY` through `status/__init__.py`, next to `LANE_HEAD_KEY`.

## Design

- **Recording.** When `attempt_auto_rebase` actually creates the merge commit, it first writes the pre-merge lane tip to the clone-local ref `refs/spec-kitty/review-presync/<lane-branch>` (`git update-ref`). It writes nothing when no merge is created.
- **Reading.** `LaneHeadReading` gains an optional `presync_sha`, set only when:
  - the presync ref exists and differs from the head;
  - it is a first-parent ancestor of the head;
  - every commit on the first-parent path between them is a merge (`rev-list --first-parent --no-merges <presync>..<head>` is empty, plus `merge-base --is-ancestor`).

  Otherwise it is None. Keep `__post_init__`'s one-of invariant for `sha` / `applicable` / `cause`; `presync_sha` is extra and only valid with `sha`.
- **Stamping.** `_stamped_policy_metadata` writes `lane_head_presync` when `presync_sha` is set. Extend the batch path the same way.
- **Bound.** One helper `effective_stamp(repo_root, event_metadata, lane_tip) -> StampVerdict` in `approved_bound.py` returns:
  - `lane_head` when reachable from the lane tip;
  - else `lane_head_presync` when reachable;
  - else a refusal whose detail is `absent_from_clone` (neither stamp object exists, `commit_in_clone`) or `not_on_lane`.

  `stamp_refusal`, `check_lane`, the tier-2 window end in `write_branch_bound.py` and `approved_attestation.py` all use it. The refusal code stays `APPROVAL_STAMP_NOT_ON_LANE`. For `absent_from_clone`, the refusal text names the WP and the SHA and says: push the lane from the reviewer's clone (`git push <remote> <lane>`), or rework, review and approve again. Keep `render_refusals` one recovery block.
- **ADR.** Amend ADR `2026-10-04-5` (Amendment 2026-11-22): what the pre-sync stamp is, why it keeps the bound sound (merges are dropped by both tiers), the absent-object remedy, and residuals (a reviewer commit on top of the sync merge is still refused; the presync ref is clone-local).

## Subtasks

- **T010** Red-first test `tests/consolidation/test_approval_stamp_presync_7802.py` (real git, two clones or a deleted local merge object). Scenario: implementer pushes the lane tip X; the reviewer's clone runs a review claim (sync merge M); the reviewer approves (stamp = M) and pushes only the coordination branch; the integrator's clone does not have M. Then:
  - (a) `check_lane` / `approved_bound_refusal` passes;
  - (b) a non-merge commit after X on the lane is still refused `LANE_MOVED_AFTER_APPROVAL`;
  - (c) an approval whose stamps are both absent produces the absent-object remedy.

  Drive (a) through the real approval path (`move-task --to approved` or `emit_status_transition` with the real reader). Commit it red.
- **T011** Record the presync ref in `attempt_auto_rebase`.
- **T012** `presync_sha` on the reading, plus `tests/status/test_lane_head_presync_7802.py` (merge-only path, non-merge commit in between → None, no ref → None).
- **T013** Stamp `lane_head_presync` (single and batch), plus the stamp-key lists.
- **T014** `effective_stamp`, its consumers and the absent-object remedy.
- **T015** ADR amendment and the changelog fragment `docs/changelog/unreleased/7802.fixed.md`.

## Tests to run

- New files.
- `tests/consolidation/test_approved_bound.py`, `tests/consolidation/` (owning subsystem; use `-n auto --dist loadfile`).
- `tests/status/` (`test_lane_head.py`, `test_transition_pipeline.py`, `test_wp_window_capture.py`).
- `tests/lanes/` (auto_rebase).
- `tests/integration/test_single_branch_approval_windows.py`: out-of-matrix, disclose it.
- Gates: `tests/architectural/test_remote_contact_owner.py`, `test_layer_rules.py`.
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
