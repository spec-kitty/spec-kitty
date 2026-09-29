---
affected_files: []
cycle_number: 2
mission_slug: mixed-lane-authorship-soundness-01M3M7Y0
reproduction_command:
reviewed_at: '2026-09-28T21:01:25Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback — cycle 2 (reviewer-renata)

Verdict: CHANGES REQUESTED. The only remaining item is narrow: the direction of the fifth residual's ideal outcome.

Verified closed from cycle 1 (in lane-f):
- Issue 2 (docs): closed. The paragraph now covers all five residuals and states the hunk-level exception precisely.
- Issue 3 (sentinel): closed. The patched method writes the sentinel, and the test asserts it did not exist before the run and exists with the expected content after it.
- Issue 4 (benchmark): closed. It asserts FAIL for mixed and PASS for baseline, checks that the verdict is stable across runs, and takes the min of 3 runs after a warm-up. Local run: delta 0.55 s.
- Issue 5 (`raises=AssertionError`): closed. All 5 xfail normally, and under `--runxfail` all 5 fail on their ideal-verdict AssertionError.
- Other checks:
  - production_path: 4 passed
  - terminology: 96 passed
  - check_docs_freshness --ci: 0 errors
  - ruff, ruff format and mypy: clean

## Blocking

**Issue 1 (HIGH): residual 5 pins the wrong ideal outcome (PASS). PASS is the unsafe direction.**
`test_sibling_never_entered_implementation_commit_ideally_not_attributed_to_canceled_wp` asserts `status == VerifyStatus.PASS`. In this scenario WP03 is itself canceled, never entered implementation, and has no approved window. Its out-of-workflow file ships to the target unsuperseded. Today's FAIL is the SAFE (over-blocking) direction; the only defect is that the finding names WP02 instead of WP03.

Pinning PASS as the ideal is harmful:
- If a future change makes this shape PASS (unapproved content ships silently), the strict xfail XPASSes. The natural response is to drop the xfail, which locks in the unsafe behaviour as "fixed".
- The correct fix (a FAIL that names WP03, or a REFUSE) would keep xfailing, so the pin never signals it.
- It contradicts residual #4 in the same file. #4 pins FAIL as the ideal for the same issue-5069 class ("content never approved by any governed window").

It is a genuine variant of the WP04 cycle-3 residual. The root cause is the same: `_window_commits` sweeps in chronological order and skips siblings that never entered implementation (wp_attribution.py ~L453). The cycle-3 probe's net-zero outcome and today's FAIL differ only in whether the misattributed path survives on the target. So the pin belongs here; only its assertion is wrong.

Fix:
1. Assert the ideal as "no misattribution, still not PASS". For example, take the `VerifyResult` (not just `.status`) and assert:
   - `result.status != VerifyStatus.PASS`, and
   - no `canceled_content` entry for `src/pkg/wp03_stray.py` has `wp_id == "WP02"`.
   Either the entry names WP03, or the result is REFUSE. Guard for `divergence is None` so that a PASS fails the assertion rather than raising a different exception. This keeps `raises=AssertionError` meaningful.
2. The docstring must say explicitly that today's FAIL is the safe direction and only the WP named in the finding is wrong. Remove "the overall verdict should be PASS".
3. Check with `--runxfail` that the test fails on this assertion today, because WP02 is named.
4. Docs: in the fifth-residual clause of status-model.md, add that the gate still FAILs (safe direction), e.g. "the gate still FAILs (the safe direction), but the finding names the wrong WP".
