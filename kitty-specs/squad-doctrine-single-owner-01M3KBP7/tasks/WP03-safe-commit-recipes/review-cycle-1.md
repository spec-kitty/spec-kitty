---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T10:54:31Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review (reviewer-renata): changes requested

The core work is in good shape. The red-first scan was red at 9e51fcb6, listing exactly the 11 sites, and it is green at head. The helper is clean. Ruff, format, mypy and C901 pass. No executed git call changed. The hint never names the environment-variable bypass. Four issues remain, and all are small.

## Required

### 1. FR-018 is not fully met: 5 of the converted recipes print no `--to-branch`

FR-018 and the WP objective say every printed recipe renders as `spec-kitty safe-commit <files> -m "<msg>" --to-branch <branch>`. The helper allows `branch=None`, and these sites pass nothing:

| Site | Recipe | Branch to resolve |
|------|--------|-------------------|
| `tasks_parsing_validation.py`, `_validate_research_artifacts` (~L336) | the `research(...)`/`docs(...)` recipe | `main_repo_root`'s branch, or the mission planning branch through the existing resolver |
| `tasks_parsing_validation.py`, `_check_uncommitted_worktree_changes` (~L536) | the deliverable recipe | `worktree_path`'s checked-out branch |
| `tasks_parsing_validation.py`, `_check_implementation_commit_present` (~L566) | the deliverable recipe | `worktree_path`'s checked-out branch |
| `tasks_parsing_validation.py`, `_check_kitty_specs_contamination` (~L666) | the cleanup recipe | `worktree_path`'s checked-out branch |
| `charter/_synthesis.py`, `_print_synthesis_commit_reminder` | the synthesis recipe | the repo root's current branch |

Without the flag, safe-commit uses its HEAD fallback and prints `warning: --to-branch will be required in v3.3`. The printed guidance therefore depends on a deprecated path. The Activity Log and the 92c7ce9f body say only one site omits the flag.

What to change:
- Resolve the branch at print time, for example with `get_current_branch(worktree_path)` (`specify_cli.core.git_ops`), or thread the lane branch in from the caller.
- One extra git call on an error-guidance path is fine.
- Fall back to `None` only if HEAD is detached.
- If you keep an omission on purpose, give each one an inline rationale and record it in the Activity Log.

### 2. The site wiring has no tests

The tests only assert `"spec-kitty safe-commit" in ...`. None of them pins `--to-branch <expected>` at a real site. Reverting `workspace.branch_name` to the merge-target branch would still pass everything.

Add one assertion per module that checks the full rendered recipe, including `--to-branch`:
- the implement footer (`build_implement_prompt_lines`) and `implement_finalize_and_print`, expecting the lane branch;
- the planning recipe in `implement.py`;
- the `mission_setup_plan._warn_commit_failed` recipe;
- the `tasks_parsing_validation` guidance;
- the synthesis reminder.

### 3. The scanner's argv exclusion is too broad

`_is_subprocess_argv_element` skips a string in any list or tuple literal passed to any call. So `"\n".join(["Commit first:", "  git commit -m \"feat: x\""])` is not flagged. I confirmed this with a mutation probe: a `print(...)` recipe was caught, but the `join([...])` recipe was missed.

Today it hides no real site: 0 hits in `src/specify_cli` are suppressed by it. It is still a hole in the regression guard.

What to change:
- Narrow the exclusion to real git argv, for example a list whose first element is `"git"`, or a call to a `subprocess.*` or `*run*` function.
- Add a test that proves a joined guidance list IS flagged.

### 4. Correct the force-add claim

T013 and the 92c7ce9f commit body say safe-commit force-adds named paths. It does not at the CLI level. `_has_candidate_changes` and the directory expansion both use `git status` without ignored files, so a gitignored path gives `No requested changes to commit`. I reproduced this in a sandbox with both a directory argument and an explicit file argument.

Dropping `-f` is still acceptable, because migration `m_0_12_1` removes `kitty-specs/` from `.gitignore`. Please:
- state this accurately in the Activity Log and the final commit body;
- record it as an upstream gap about ignored named paths in safe-commit.

## Non-blocking notes

- **Allowlist:** I accept the 13 entries.
  - `core/mission_creation.py:869` (`--allow-empty` with an unborn HEAD) is fine: safe-commit needs file paths and a branch ref, and neither exists yet. It is worth an upstream gap.
  - `implement.py:656` (`_DEMOTION_REFUSAL_MSG`) is borderline. It tells the operator to commit `meta.json`, which could be written as a concrete safe-commit recipe.
- **`PROTECTED_PRIMARY_HINT`** follows the charter. Two suggestions:
  - It is printed unconditionally in `implement.py`, even when the planning branch is not protected.
  - Consider naming the charter's `issue-<n>-<slug>` topic branch.
- **Pre-existing, outside this WP's files:** safe-commit's own refusal text (`git/commit_helpers.py`) still says `set SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1 if you own this branch`. That contradicts the charter. File it upstream; do not fix it here.
- **Setup-plan recipe:** it passes `_target_branch`. That equals the resolved placement for the primary kinds (spec, plan, tasks), so it is OK. `router_result.placement_ref` would be the more authoritative source if it is populated on the error path.
