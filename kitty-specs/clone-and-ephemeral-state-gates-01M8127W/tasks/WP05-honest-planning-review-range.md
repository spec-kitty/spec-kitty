---
work_package_id: WP05
title: Honest planning-lane review range (#7759)
dependencies: []
requirement_refs:
- FR-013
- C-003
planning_base_branch: issue-7809-clone-ephemeral-state-gates
merge_target_branch: issue-7809-clone-ephemeral-state-gates
branch_strategy: Planning artifacts for this mission were generated on issue-7809-clone-ephemeral-state-gates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7809-clone-ephemeral-state-gates unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-clone-and-ephemeral-state-gates-01M8127W
base_commit: 7fbbee86234ee687d370aab8246c989c6fb44f01
created_at: '2026-11-22T07:37:14.925822+00:00'
subtasks:
- T022
- T023
- T024
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/review/wp_range.py
create_intent:
- tests/review/test_planning_range_bookkeeping_only_7759.py
- docs/changelog/unreleased/7759.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/review/wp_range.py
- src/specify_cli/review/context_block.py
- tests/review/test_planning_range_bookkeeping_only_7759.py
- docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md
- docs/changelog/unreleased/7759.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Honest planning-lane review range (#7759)

## Objective (#7759)

A planning-lane work package's review range can be made of coordination status commits only, presented as if it held the work. Docs WPs get their own lane after WP04, which removes most of this. For the remaining planning-lane WPs (`kitty-specs/`-only), when the derived range holds only bookkeeping commits, the review context reports the range as unavailable with the reason.

## Grounding

- **`src/specify_cli/review/wp_range.py`.**
  - `resolve_wp_review_range` is at `:596`.
  - The planning-lane derivation (operator rulings Q10 / Q12) is `_coordination_and_planning` `:529`, `_status_shares_planning_branch` `:548` and `planning_branch_apart_from_status` `:557`.
  - Bookkeeping pathspecs: `bookkeeping_pathspecs` `:269`, `mission_bookkeeping_pathspecs` `:278`.
  - The listing: `_listing` `:490`, `_count` `:474`.
- **`src/specify_cli/review/context_block.py`.** `render_review_context` already renders unavailable ranges with their reason; reuse that shape.
- **Bookkeeping definition.** Use the existing pathspecs in `wp_range.py` (the review range's single owner of the review pathspecs). Do NOT add a third definition.

## Design

After a planning-lane range is derived (the never-stamped, status-event path), count the commits in `base..tip` that touch anything outside the bookkeeping pathspecs, using the existing helpers. If none, return the unavailable outcome with a new reason constant (for example `PLANNING_RANGE_BOOKKEEPING_ONLY`). Its human text says the derived range contains only status-bookkeeping commits and the work package's own commits are not on that branch. Code-lane ranges are unchanged.

Add a short cross-reference paragraph to ADR `2026-11-08-2` (Amendment 2026-11-22): the planning range is withheld when it is bookkeeping-only, and docs WPs get their own lane (ADR `2026-11-06-3` amendment).

## Subtasks

- **T022** Red-first test `tests/review/test_planning_range_bookkeeping_only_7759.py`:
  - real git: a lanes Mission with a planning-lane WP whose status events are committed on the coordination branch and whose work is not → `resolve_wp_review_range` returns unavailable with the new reason;
  - positive control on the same fixture: a planning-lane WP with a non-bookkeeping commit in range keeps its range.

  Commit it red.
- **T023** Implement the check and the rendering.
- **T024** ADR cross-reference and the changelog fragment `docs/changelog/unreleased/7759.fixed.md`.

## Tests to run

- New file, `tests/review/`.
- `tests/specify_cli/review/`: out-of-matrix, run it and disclose it.
- Tests referencing `resolve_wp_review_range` / `render_review_context` (grep).
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
