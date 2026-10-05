---
affected_files: []
cycle_number: 2
mission_slug: nightly-suites-green-01M44FEP
reproduction_command:
reviewed_at: '2026-10-05T06:37:42Z'
reviewer_agent: reviewer-renata
wp_id: WP07
---

# WP07 review cycle 2: changes requested

Reviewer: reviewer-renata. The four cycle-1 changes are done. The printed guidance works wherever the Mission has an identity (proven in a scratch repository on a protected and a non-protected target, for both sites). Two narrow items remain.

1. **A legacy Mission is told to run a command that heals nothing.** `cli/commands/mission_type.py:1128-1129` returns before the persist leg when `mid8` is empty, while `cli/commands/consolidate.py:742` still reaches the warning. For a Mission with no `mission_id`, `mission close` exits 0 and both files stay dirty. Branch the text in `post_merge/retrospective_terminus.py::_rerun_command` when the Mission has no identity, and add a test.
2. **No permanent test runs the retrospective command.** `tests/specify_cli/post_merge/test_retrospective_triggering.py:433-467` asserts text only. Add a real-path test: merged fixture, failing commit, run the printed `mission close`, assert a clean tree.

Residual notes: `mission close` also tears down a retained coordination worktree; the consolidate-triggered warning was not exercised end to end; shapes still missed by the classifier: `git commit.`, `git commit...`, `[options]`, redirects.
