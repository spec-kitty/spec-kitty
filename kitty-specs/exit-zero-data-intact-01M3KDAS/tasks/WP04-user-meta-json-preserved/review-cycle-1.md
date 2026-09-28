---
affected_files: []
cycle_number: 1
mission_slug: exit-zero-data-intact-01M3KDAS
reproduction_command:
reviewed_at: '2026-09-28T11:14:49Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review — changes requested (reviewer-renata)

The production fix is correct and I am not asking for changes to it. `coherence.py` uses a depth-exact, monorepo-safe anchor with function-local literals. ruff, format and mypy --strict are clean, and the ratchet, destructive-op-routing and layer gates pass (152 passed with the owned re-pin files). Red-first holds: against a base-source snapshot, 8 new tests FAIL and all controls PASS; on head, 32/32 pass.

The requested changes are all in the test file `tests/consolidation/test_user_meta_json_dirty_4933.py`. The WP contract requires these assertions, and right now they are either weak or missing.

**Issue 1 — NFR-003 remedy assertion is too weak (primary arm), ~line 300.**
`assert "commit" in captured.out.lower() or "stash" in captured.out.lower()` would pass on any output that contains the word "commit" anywhere. Pin the real remediation line instead:
`assert "Remediation: Commit, stash, or revert the local changes" in captured.out`
Apply the same assertion to `test_two_dirty_user_files_are_aggregated_into_one_refusal`.

**Issue 2 — FR-009 / NFR-003 not asserted on the lane-worktree arm** (`test_dirty_user_meta_json_in_lane_worktree_refuses_before_removal`).
The WP says the refusal "names worktree + file" and prints the commit/stash remedy. The test only asserts the error code and the file. Add both of these:
- `assert str(wt_path) in captured.out` (the worktree is named)
- the same `Remediation: Commit, stash, or revert` assertion as in Issue 1

Rich wraps lines at the console width, so pin the width before asserting (e.g. `monkeypatch.setenv("COLUMNS", "400")`) or normalise newlines out of `captured.out`. Otherwise the long tmp path can split across lines.

**Issue 3 — regression marker not removed after green** (line ~48, `pytestmark`).
T022 and the red-first procedure say to remove `pytest.mark.regression` once the test is green. Drop it from `pytestmark` and keep `git_repo` and `non_sandbox`.

Non-blocking notes:
- The ruff-format reflow of unrelated lines in `coherence.py` and `test_self_bookkeeping_allowlist.py` was needed, because the base file was not format-clean at line-length 164. It should have been its own campsite commit. Split it next time.
- FYI, not yours to fix (the executor belongs to WP03's lane): on the primary arm, the refusal also prints "Resume recovery guidance (behind-own-HEAD …): git reset --hard HEAD". The cause is `_report_pre_mutation_refusal` → `classify_resume_dirty_remedy(main_repo, lane_branch=mission_branch)`, which returns BEHIND_OWN_HEAD whenever the mission branch is an ancestor of HEAD. On a fresh consolidation that is the normal state. This has been escalated to the orchestrator. Do not assert on its absence in this WP.
