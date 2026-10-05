# Quickstart: verifying frozen lanes for started work packages

## Reproduce #5573 (base commit) and verify the fix

```bash
uv sync --frozen --all-extras && uv pip install -e .
# End-to-end reproduction through finalize-tasks (red on the base commit, green after the fix):
.venv/bin/python -m pytest tests/integration/test_refinalize_keeps_started_lanes.py -q
# Compute-level invariant + permutation sweep (fast):
.venv/bin/python -m pytest tests/lanes/test_frozen_lane_membership.py -q
```

## By hand

1. Create a `lanes` mission with WP01 (`a.py`) and WP02 (`b.py`), then `spec-kitty agent mission finalize-tasks --mission <m> --json`.
   The result is lane-a = [WP01] and lane-b = [WP02].
2. `spec-kitty implement WP02 --mission <m>` and commit work in the lane-b worktree.
3. Amend WP01: `owned_files: [a.py, b.py]`, `dependencies: [WP02]`. Commit.
4. Re-run `finalize-tasks --json`. **Expected:** success, with one lane `lane-b` = [WP02, WP01].
5. Also start WP01 before step 3, on lane-a. **Expected:** exit 1, `error_code: LANE_MEMBERSHIP_FROZEN`,
   `reason: started_lanes_collapsed`, and nothing written.
