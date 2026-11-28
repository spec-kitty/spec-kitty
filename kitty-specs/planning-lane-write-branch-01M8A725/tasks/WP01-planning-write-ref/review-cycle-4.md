---
affected_files: []
cycle_number: 4
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-25T22:47:00Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review cycle 4 (claude::reviewer-renata): REJECT

Commit reviewed: ea0adc94.

## The two cycle-3 findings: both resolved

- **The remedy for a Mission without coordination: resolved.** Case D now names `git switch <branch>` in the repository root checkout and does not mention the doctor.
- **A remote name containing "/": resolved.** Case C now refuses and names the remote `my/fork`. Cases A and B behave as before.

Checks: 37 tests pass, and ruff, C901, format and mypy are clean.

Not findings:
- `_branch_and_remote` handles `HEAD`, `main` and other refs outside the namespace correctly.
- Listing all of `refs/remotes/` is one `for-each-ref`, filtered in Python, and `blob_at` runs only for refs in the namespace. The cost is acceptable.

## Findings

1. **[LOW] src/mission_runtime/resolution.py (`name = "checked out in the repository root checkout"`, in `PlanningCheckoutMissing.__init__`): the message contradicts itself.**
   - Case D renders as "the Mission branch kitty/mission-sd-01M8EEEE (checked out in the repository root checkout) of Mission 'sd-01M8EEEE' is not checked out anywhere".
   - Case C renders as "(checked out in the repository root checkout) ... exists only as my/fork/...".
   - Recommendation: reword it, for example "(written in the repository root checkout)", or drop the parenthetical. Pin the rendered text in a test.

2. **[LOW] "Coordinated" is decided by two different readers (C-004).**
   - The probe uses `bool(meta.get("coordination_branch"))` in `_branch_claiming_mission`, in resolution.py.
   - `planning_lane_target` uses `routes_through_coordination(resolve_topology(...))`, at src/specify_cli/coordination/planning_commit.py:295.
   - They disagree on a meta that records `topology: lanes_with_coord` without a `coordination_branch`. My probe case C fixture has that shape, and the probe path gave the `git switch` remedy where the `planning_lane_target` path would give the doctor remedy.
   - Recommendation: decide it with one predicate in both paths. For example, apply `routes_through_coordination` to the claiming meta's stored topology, or read `coordination_branch` in both places. Add a test where the two shapes would otherwise differ.
