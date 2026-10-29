---
affected_files: []
cycle_number: 1
mission_slug: lane-evidence-independence-01M5YHXF
reproduction_command:
reviewed_at: '2026-10-27T18:00:46Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback (reviewer-renata), cycle 1

Verdict: changes requested. There are two blocking findings. The rest of the WP is in good shape:
the red-first commit is genuinely red on its parent, single_branch keeps its codes and text, the
`_sb_*` copies are gone, `approved_bound.py` and `preflight.py` are unchanged, every GitProbeError
and unreadable log fails closed, ruff, format and C901 pass, and the only noqa is the copied
BLE001 with its rationale.

## Blocking

**1. Two tests in the WP's own new test file fail on every run, and the lanes fixture never exercises the axis.**
- Where: `tests/consolidation/test_lane_evidence_axis.py::test_claim_refuses_an_approved_lane_with_no_owned_commit`
  and `::test_an_attested_work_package_is_admitted_and_named`. They fail at `07bc02e2` and at HEAD
  (2 failed / 2 passed, both serially and under xdist).
- Cause: `tests/terminus/lanes_fixture.py:191` calls `pin_planning_commit` BEFORE the bootstrap
  commit that adds `tasks/WP0x-work.md` and `lanes.json`. So `planning_commit_sha` is the `init`
  commit. On top of that, `_wp_file_text` (lanes_fixture.py:57) declares `owned_files: [src/**, kitty-specs/**]`.
  Every lane's window `planning..lane` therefore contains the WP's own task files, which match
  `kitty-specs/**`, so an emptied lane still reads as implemented. Probe output for the emptied
  WP01 lane: evidence paths = `{kitty-specs/<slug>/tasks/WP01-work.md, .../WP02-work.md, .../lanes.json}`.
- Effect: the claim-builder refusal (T003, FR-004) has no passing test on the lanes fixture. Every
  terminus test built on `build_lanes_mission*` has an axis that always passes, which hides
  regressions.
- Required fix: pin the planning commit AFTER the bootstrap commit, as `finalize-tasks` does.
  Drop `kitty-specs/**` from the fixture's owned_files (the code lanes commit under `src/` only).
  Then re-run `tests/consolidation/test_lane_evidence_axis.py` and the terminus lanes tests.

**2. Widening the window to dependency lanes lets a hollow work package pass (fail-open, implementer decision (a)).**
- Where: `src/specify_cli/consolidation/wp_evidence.py:349-379` (`dependency_evidence_windows` /
  `_widened_paths`), used at :405.
- Failure scenario. Ownership is disjoint and in-model: WP01 owns `src/m1/**` on lane-a, and WP02
  owns `src/m2/**` on lane-b, which depends on lane-a.
  1. WP02 is claimed: lane-b is cut and merges lane-a@T1. WP02 never commits anything.
  2. Lane-a then advances to T2, for example during a rework of WP01, with a commit that touches
     `src/m2/x.py` (an out-of-map edit, a sanctioned practice).
  3. WP02 is approved.
  - Planning window `planning..lane-b`: shows only `src/m1/real.py`, which is correct, and WP02 is MISSING.
  - Widened window `lane-a@T2..lane-b`: shows `src/m2/x.py`, so WP02 passes with refusal None.
  Lane-b differs from the dependency tip only because the dependency moved, not because WP02 did
  any work. A probe test (two cases, both behave as described) is at
  `/tmp/claude-0/-home-user-spec-kitty/98a00833-f8c1-5968-adf2-832916f6ed94/scratchpad/probe/test_widen_probe.py`.
- Also wrong:
  - The widening is not in the spec. spec.md says "Merges of sibling lanes into a lane do not count
    for this WP (owned files are disjoint)".
  - Its only motivating test (`test_wp_evidence.py::test_a_removal_of_a_dependency_lanes_content_counts_as_evidence`)
    gives WP01 and WP02 the same `src/m1/**` across two lanes. Lane computation
    (`find_overlap_pairs`) would put those two WPs in ONE lane. Under disjoint ownership the
    widening can never supply legitimate evidence. It can only admit content written by another lane.
- Required fix, either of:
  - (preferred) Measure the lane against what it merged in, not against the dependency's live tip:
    the window `git merge-base <dep_tip> <lane_tip>..<lane_tip>`. A dependency that advances after
    the cut then cannot add paths.
  - Remove the widening and its overlapping-ownership test.
  - Either way, add the probe scenario as a regression test asserting `IMPLEMENTATION_MISSING: WP02`.
  - If the widening stays, cover its GitProbeError branch (wp_evidence.py:408-414 has no test).

## Non-blocking (fix if cheap)

- `tests/specify_cli/orchestrator_api/test_contract_version.py`: `test_contract_version_response_reports_1_18_0` now asserts 1.19.0. Rename it.
- `wp_evidence.py`: `__all__` is out of order (`wp_task_dir` before `refusal_codes`). `canonical_code` has no caller in `src/`.
- `wp_evidence.py:44` imports the private `_status_only_excluded_prefixes` from `lanes/for_review_gate.py`. Make it public, or move the list into `wp_evidence` and import it from the gate.
- `wp_task_dir` (wp_evidence.py:174-186) falls back to the coord-aware `feature_dir` when the primary dir has no `tasks/`. Under coord topology that dir is the coordination worktree, which may hold a stale copy of `tasks/`. Prefer failing closed: no tasks on primary means ownership is unresolved, so the WP is MISSING. If you keep the fallback, log at warning level.
- Lanes path: a WP that is approved in the snapshot but listed in no lane of `lanes.json` is never judged (the single_branch path judges every approved WP). This is low risk because no lane merges it. Consider judging it as `EVIDENCE_WINDOW_UNCOMPUTABLE`.
- `_mt_matches_owned_file` / `_mt_owned_file_patterns` still duplicate the matcher in `tasks_move_task.py`. WP03 owns that file and must delegate to `wp_evidence` (one-authority ruling 5). This is a coordination note, not a WP01 defect.
- The recovery text names `--attest-no-implementation`, which does not exist until WP02 lands. It is fine only if both land together.
