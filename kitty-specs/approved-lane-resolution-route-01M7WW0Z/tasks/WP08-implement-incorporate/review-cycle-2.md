---
affected_files: []
cycle_number: 2
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-25T09:26:23Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP08
---

# WP08 review cycle 2 (lane-h 1b55ea66a9 on 753fd3a9): REJECT

Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

## Verified
- Red-first: the cycle-2 tests fail 14 / pass 15 against the c7fa31a1c0 sources.
- Post-fix: 29 passed. incorporate.py has 100% in-process coverage, and the 35 new workflow.py lines are covered.
- Blast radius:
  - tests/lanes + implement/workflow CLI: 4255 passed, 5 skipped, 1 xfailed.
  - terminus -k "incorporate or post_approval": 16 passed.
  - Arch gates commit_scope_owner / layer_rules / merge_pipeline_ratchets / no_legacy_terminology / no_worktree_name_guess: 274 passed.
  - no_dead_symbols -n0: 37 passed.
  - ruff, format, C901, mypy: clean.
- Cycle-1 items 1, 2, 4, 6 and 7 are resolved. The A-10 narrowing (`git merge --abort` is a back-out) is accepted. Item 3 stays deferred to WP07.
- The cycle-1 invariants hold after the rebase:
  - the stamp SHA is the merge argument;
  - refs/heads/<b>;
  - no status write;
  - exit 3;
  - --force is refused;
  - no duplication of main's SiblingLane / find_sibling_lanes / refine_stale_result.

## Must fix: INCORPORATE_CANCELED_CONTENT_UNDER_STAMP is wrong in both directions

### 1. (MED) Over-refusal from a second window authority
Where: incorporate.py `_active_windows` / `_window_commits_under` (~:210-251) and `_ACTIVE_LANES` (:59).

A canceled WP's window runs from its entry into any active lane until it leaves them all. Every first-parent commit inside that span counts as canceled, including another WP's approved commits.

Repro:
1. WP02 is claimed at h0, makes no commits, and goes to for_review.
2. WP01 commits w1 and is approved at w1.
3. WP02 is canceled.
4. The refusal now names w1, which is approved WP01 work. The remedy cannot clear it.

consolidation/wp_attribution.py already owns window reconstruction: `_windows` implementation/review classes, `_window_commits` stamp-ancestry checks, `_resolve_contested`, `resolve_canceled_wp`, `lacks_lane_head_stamps`.

FIX:
- Build the refusal on `resolve_canceled_wp` (or `canceled_spine_content`).
- Refuse when `Attributed.commits` contains a commit the stamp reaches.
- An `Unattributable` result also refuses (fail closed).
- Delete `_active_windows`, `_window_commits_under` and `_ACTIVE_LANES`.
- Add the scenario above as a regression test that must NOT refuse.

### 2. (MED, integrity) Canceled content inside a merge evades the refusal
Where: `_window_commits_under` (~:241) drops every merge.

Repro:
1. During canceled WP02's window, the lane gets a merge whose resolution adds src/canceled.py.
2. WP02 is canceled at that merge.
3. WP01 commits w1 and is approved at w1.
4. There is no refusal, and `--incorporate` carries src/canceled.py into the lane.

The canonical resolver also skips merges, so fix 1 alone does not close this.

FIX (fail closed):
- For every merge in a canceled WP's window that the stamp reaches, refuse when `git_probes.merge_own_changed_paths(merge)` is non-empty or raises.
- WP07 will wrap that probe in WP01's guard when composing the attribute check.
- Add the repro as a test that expects the refusal.

The reviewer can paste the probe fixture (probe08_keep.py) if wanted. Its output lines are `OVER-REFUSAL: … reaches commits of canceled WP02` and `EVADED: merge … carries src/canceled.py`.

## For WP05 (binding probe, outside WP08's scope)
A merge with its own content inside a canceled WP's window is dropped from the canceled window. An approved stamp then reaches it, so it counts as "reviewed" under #7307. WP05 must add a real-git test of this exact shape that refuses, via either RESOLUTION_MERGE_UNREVIEWED or canceled-content.
