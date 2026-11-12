# WP03 review, cycle 1: changes requested (narrow)

The resolver is well built. The range rules, the rework cell, the lane-mate exclusion by base, the numstat values, the moved-past rules, the git-call count, red-first, the gates and the quality checks all pass. The changes requested are two test gaps on a stated rule and one fail-soft hole.

**Issue 1 (MEDIUM, FR-004 / design rule "every derived anchor is ancestry-guarded"): no test pins the derived-anchor ancestry guards.**
- Mutation 1, `src/specify_cli/review/wp_range.py:299`: changing `if stamped is not None and ctx.is_ancestor(stamped, tip):` to `if stamped is not None:` leaves `tests/review/` green (31/31).
- Mutation 2, `wp_range.py:304`: dropping `ctx.is_ancestor(claim_base, tip)` also leaves it green (31/31).
- `test_recorded_open_off_the_lane_falls_back_and_names_the_gap` only moves `wp_window.open_sha` off the lane. The opener's `lane_head` stays an ancestor, so the guard on the fallback is never exercised.
- Add two cells:
  - (a) A lane Mission with `not_recorded` (or `not_on_lane`) whose opener `lane_head` is rewritten to a non-ancestor SHA (e.g. `cs._not_on_lane_sha`). Assert the range is `UNAVAILABLE` and that `base` is not that SHA.
  - (b) A commit-to-target `single_branch` whose `wp-base` ref points at a non-ancestor commit (e.g. a side-branch commit written with `git update-ref`). Assert `base_source is EVENT_COMMIT` and that `base` is not the stale ref.
- Confirm that each new cell goes red under the matching mutation above.

**Issue 2 (MEDIUM, NFR-004 "never raises"): `read_claim_base` can raise `OSError` into the resolver.**
- `specify_cli.lanes.claim_base.read_claim_base` calls `subprocess.run` without catching `OSError`.
- When git cannot be started on a `single_branch` Mission, the status read (a plain file read) can still succeed. Then `is_ancestor` turns into False, the window becomes a `not_on_lane` gap, `_derived_bases` reaches `read_claim_base`, and the `OSError` propagates out of `resolve_wp_review_range`.
- Fix: in `_derived_bases`, wrap the call so that `OSError` (and `subprocess.SubprocessError`) reads as "no claim base", logged at debug level. Do not edit `claim_base.py`; it is not owned by this WP.
- Add a test: monkeypatch `wp_range.read_claim_base` to raise `OSError` on a stripped-stamp `single_branch` fixture, and assert that no exception escapes.

**Issue 3 (LOW): two names for the Mission directory.**
- `resolve_wp_review_range` uses `ctx.surface.mission_dir_name` for `owned_pathspecs` but the raw `mission_slug` argument for `_bookkeeping_excludes`.
- With an owned checkout, `resolve_status_read` accepts a mid8 or ULID handle (#7539). If a caller passes one, the bookkeeping prefixes are wrong: status commits then count in `moved_past`, and status files show up in `out_of_map`.
- Fix: use `ctx.surface.mission_dir_name` for `_bookkeeping_excludes` (lines 458/473), or document that `mission_slug` must be the directory name.

**Deviations reviewed and accepted** (please report them in the completion note for the tracer):
- `__all__` narrowed to `resolve_wp_review_range`, because of the dead-symbol intra-module rule.
- New fields `listing_gap` and `RangeGap.STATUS_UNREADABLE`.
- `bookkeeping_commits` dropped. Neither data-model.md nor the contract renders it.
- `files` and `out_of_map` come from one numstat, split by `matches_owned`.
  - I checked empirically that the printed `git log --oneline base..tip -- <owned_pathspecs>` returns exactly `commits` for `src/m1/**`, `src/m1`, and `kitty-specs/<slug>/**` + `src/m1/*.py`.
  - Git's default (non-`:(glob)`) pathspec matching agrees with `fnmatch` (`*` crosses `/`), so FR-005 and FR-008 stay consistent.
  - Minor: the module docstring line "every pathspec is a git glob" really means "default git wildcard matching, never `--literal-pathspecs`". Consider saying that, so WP05 does not add `:(glob)`.
