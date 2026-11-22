---
work_package_id: WP01
title: Hex colours are not issue references (#7808)
dependencies: []
requirement_refs:
- FR-012
- SC-004
planning_base_branch: issue-7809-clone-ephemeral-state-gates
merge_target_branch: issue-7809-clone-ephemeral-state-gates
branch_strategy: Planning artifacts for this mission were generated on issue-7809-clone-ephemeral-state-gates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7809-clone-ephemeral-state-gates unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/tasks/issue_matrix.py
create_intent:
- tests/tasks/test_issue_reference_hex_colour_7808.py
- docs/changelog/unreleased/7808.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/tasks/issue_matrix.py
- src/specify_cli/tasks/issue_reference_discovery.py
- tests/tasks/test_issue_reference_hex_colour_7808.py
- docs/changelog/unreleased/7808.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Hex colours are not issue references (#7808)

## Objective (#7808)

Issue-matrix discovery reads a CSS hex colour as an issue. A hash followed by `000000` becomes issue 0 and blocks approval. After this WP, a hash-number with a leading zero is never an issue reference in any of the three issue-number patterns, and neither is an all-digit hex colour in CSS declaration form. A real reference on the same line is still found.

## Grounding

- `src/specify_cli/tasks/issue_matrix.py:168` `_GH_ISSUE_PATTERN`: the hash arm is `#(\d{2,6})`. Change it to `#([1-9]\d{1,5})` and keep `match.group(1)` as the capture. The bare-arm terminators are unchanged.
- `src/specify_cli/tasks/issue_matrix.py:192` `_matched_issue_number`: the one Python-side filter. `detect_issue_references` and `issue_numbers_in_text` (`:263`) both use it. Add the colour filter here: reject a hash-arm match when the text directly before it is a CSS declaration (a property name such as `color`, `colour`, `background`, `background-color`, `fill`, `stroke`, `border`, `border-color` or `outline`, then `:` and optional spaces) and the digits are 3, 4 or 6 long. `_matched_issue_number` needs the source string and the match position. Pass `match.string` or the line; do not add a second regex scan elsewhere.
- `src/specify_cli/tasks/issue_reference_discovery.py:347` `_SOURCE_DESCRIPTION_LEAD_PATTERN` and `:354` `_CLOSING_KEYWORD_PATTERN`: the same no-leading-zero rule (`[1-9]\d{1,5}`).
- Do NOT filter on a CSS keyword anywhere on the line. "fix border regression" followed by a real 4-digit issue reference must still be found (researcher finding).
- `#abc123` must stay unmatched (`tests/specify_cli/tasks/test_issue_matrix_scaffold.py:237`).

## Subtasks

- **T001** Red-first acceptance test `tests/tasks/test_issue_reference_hex_colour_7808.py`. Cover:
  - `discover_issue_references` on a Mission dir whose `research.md` holds colour declarations (six- and three-digit all-digit values, with a leading zero and without);
  - `issue_numbers_in_text`;
  - the closing-keyword / source-description paths;
  - positive controls on the same fixture: a real reference, a real reference on a CSS-word line, and a backticked real reference.

  Commit it red.
- **T002** Leading-zero rule in all three patterns.
- **T003** The CSS-declaration colour filter in `_matched_issue_number`.
- **T004** Changelog fragment `docs/changelog/unreleased/7808.fixed.md`.

## Tests to run

The new file, plus `tests/specify_cli/tasks/test_issue_reference_discovery.py`, `test_issue_reference_terminators.py`, `test_issue_ref_url_provenance.py`, `test_issue_matrix_scaffold.py`, `tests/tasks/`, `tests/agent/cli/commands/test_tasks_helpers.py` and `make test-fast`. `tests/specify_cli/tasks` is out-of-matrix: disclose it if you change a file there (you should not need to).

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
