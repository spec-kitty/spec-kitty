---
affected_files: []
cycle_number: 1
mission_slug: truthful-discovery-step-01M3KABP
reproduction_command:
reviewed_at: '2026-09-28T07:06:39Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review: changes requested (one blocking issue)

## Blocking: the lane branch changes kitty-specs/ and conflicts on merge
Commit 4a8b4902 ("chore: remove planning artifacts from lane branch") did not put kitty-specs/ back to the lane base. It copied the planning branch's state from that moment onto the lane. As a result:
- `git diff claude/project-thread-silj7c...HEAD` (and a diff against base_commit f338859) changes 4 kitty-specs/ files: status.events.jsonl (+11 lines), status.json, and the base_branch frontmatter in both WP01 and WP03.
- `git merge-tree --write-tree claude/project-thread-silj7c HEAD` reports CONFLICT (content) in status.events.jsonl and in status.json, because the planning branch has recorded more events since then.

Fix: in the lane worktree, run `git checkout f338859f0a6e1cd2647979a2cd6d29efb3fa9206 -- kitty-specs/`, then commit. After that, `git diff f338859..HEAD --stat -- kitty-specs` must be empty and merge-tree must be clean. Put the Activity Log on the planning branch only.

## Verified: no changes needed
- Production diff: only the 5-line `_ensure_branch_checked_out` shim is deleted from mission.py (C-005). `git grep` finds no matches in src or tests (SC-004).
- The 6 named test files give 43 passed. ruff check is clean and mypy on mission.py is clean. The format drift in mission.py and 2 of the tests was there before this change.
- Read-only test: I added a temporary `git checkout <target_branch>` to the validate-only return in `_scaffold_issue_matrix_if_present`. The test went RED on the HEAD assertion (feat/planning-work -> main), and exit 0 still held. I restored the file and the worktree is clean. The test is not vacuous.
- The positive control is weak but acceptable: it only proves that the probe can see a checkout. Together with the explicit HEAD != target precondition assert, it meets the post-tasks fold.
- FR-011: the dead patch is removed. The compat shim in status/__init__.py:619 is intact, and test_dossier_sync_compat passes.
