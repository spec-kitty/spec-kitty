---
affected_files: []
cycle_number: 2
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T11:38:34Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review, cycle 2 (reviewer-renata): changes requested (one narrow item)

Cycle-1 items #1, #3 and #4 are resolved, and most of #2 is resolved. Evidence:

- **Format:** whole-repo `ruff format --check .` is green (2597 files already formatted). The 4 test files the implementer named are listed in the pre-existing `[tool.ruff.format].exclude` ratchet in `pyproject.toml`. They were already listed at base 5ae8a328, and they were unformatted there too. The debt is not a regression.
- **FR-018:** all 5 sites resolve `--to-branch` at print time with `get_current_branch`:
  - the contamination site uses `worktree_path`'s own branch, not `_guard_base`;
  - the research site uses `main_repo_root` and matches the printed `cd`.
- **Scanner:** the exemption now requires `elts[0] == "git"`, and `test_scanner_flags_joined_guidance_list` is a real positive control. The allowlist holds exactly 13 entries.
- **Force-add:** the correction is in the `implement.py` comment and the ebb2fb48 body.

## Required

### 1. The `implement.py` planning recipe still has no test that pins `--to-branch` (cycle-1 #2, bullet 2)

`_print_planning_artifact_commit_instructions` (`implement.py` ~L432) prints `safe_commit_recipe([str(feature_dir)], ..., planning_branch)`.

In a scratch copy I mutated that call to drop `planning_branch`. Nothing caught it. The run covered:
- `test_tasks_parsing_validation.py`
- `test_implement_writeside.py`
- `test_implement.py`
- `test_commit_recipes.py`
- `test_build_implement_prompt_lines.py`

No test in `tests/` asserts on that recipe.

**Fix:** add one test that drives the auto-commit-disabled path and asserts both of these:
- the output contains `--to-branch <planning_branch>`;
- the output does not contain the lane branch.

Mirror the other site tests.

## Non-blocking

- The upstream gap for safe-commit ignoring gitignored named paths is still not filed. The ebb2fb48 body defers it to the operator. Filing it is acceptable either way, but make sure someone owns it.
