---
affected_files: []
cycle_number: 2
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T12:12:56Z'
reviewer_agent: claude
wp_id: WP19
---

# WP19 review: cycle 2, changes requested (reviewer-renata)

Reviewed: lane-f `46b174ff58` against cycle 1 `03629fcfc1` and base `4f2ddb7939`.

The B1 design is correct and the cycle-1 probe scenarios are fixed:
- Ignored path: `None` plus a warning.
- HEAD on another branch: `None` plus a warning, not the stale commit.
- Happy path (HEAD on the target branch, two paths changed in separate commits): the receipt names the tip, which is correct.
- HEAD on a different branch at the same commit: the receipt names that commit, which is correct.

The two new tests are red against the cycle-1 `workflow.py` for the right reasons, and green now.

Also fixed: N1 (the record is corrected in the tracer and the class docstrings), N3, N4 and N5. Gates are clean: ruff, `format --check --force-exclude`, C901 and mypy --strict. Targeted suite: 106 passed. The allowlisted line is verbatim at L945, and no new `placement_seam(`, `write_dir(` or `CommitTarget(` call was added.

## BLOCKING

### B2. The "tracked at candidate" half of the B1 fix has no test, and coverage of the new lines is under the gate

I measured diff coverage of the WP19 `workflow.py` additions by running `test_workflow.py`, `test_guard_capability_regression.py` and `test_coord_commit_integrity_e2e.py`. Result: **25/30 added executable lines (83%)**. NFR-003 and the CI diff-cover gate both require at least 90%.

The five missed lines are exactly the new verification branches:
- L795-796: `_paths_tracked_at_commit`, the `ValueError` arm for a path outside `porcelain_root`.
- L805: `_paths_tracked_at_commit`, the arm where `git cat-file -e` fails.
- L858/L864: `_already_present_receipt_sha`, the "candidate does not track" rejection.

This branch is load-bearing but nothing pins it. Deleting the `_paths_tracked_at_commit(...)` call leaves every test green:
- the ignored-path test already returns at the empty `git log`;
- the HEAD-mismatch test returns at the ancestor check.

The WP's quality gates require a focused test for each new helper and branch.

Required (tests only; no source change needed):
1. **Partially untracked path set.** `git log -1 HEAD -- <paths>` finds a commit, but one path is not tracked there. Two ways to build it:
   - a tracked file plus a path that does not exist (porcelain is clean and the log finds the tracked file's commit); or
   - a file whose deletion was committed.
   
   Assert `sha is None` and exactly one warning. This also pins the behaviour I reproduced: one missing path in the set makes the whole receipt `None`. That is an honest result, but pin it so it is a deliberate one.
2. **Path outside the root.** Call `_paths_tracked_at_commit` directly with a path outside `porcelain_root` and assert `False`, plus one `True` case.

## NON-BLOCKING

### N6. Relative paths resolve against the wrong directory

`_paths_tracked_at_commit` calls `path.resolve()`, which resolves a relative path against the process cwd, while the git commands run with `cwd=porcelain_root`. Every current caller passes absolute paths, so this is latent. A one-line guard fixes it: `p if p.is_absolute() else porcelain_root / p`. Optional in this cycle.

### N2 (closed). The fixture justification holds

`tests/_factories/coord_mission.py` produces none of: `spec.md`, `plan.md`, `lanes.json`, a charter bundle, an analysis report, or a WP file. It cannot pass `implement`'s preflight.

`_build_mission_repo` is already imported across modules by eight other test files, including `test_coord_commit_integrity_e2e.py`, `test_issue_2508.py` and `test_workflow_review_lane_gate.py`. WP19 follows that existing convention and does not add new coupling. The tooling-friction tracer records the reason.

Recommended as a post-mission follow-up, not blocking WP19: promote `_build_mission_repo` into `tests/_factories/`, or extend `make_coord_mission` with an implement-ready option.
