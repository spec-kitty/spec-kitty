# Quickstart: verifying Lane Branch Naming Authority

## Reproduce #5108 on HEAD (red)
```bash
.venv/bin/python -m pytest "tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget" -q
# 2 failed: "Reconciliation refused (fail-closed): no approved lane resolved any commits"
```

## After the mission (green)
```bash
# divergent shapes: claim, executor stages, end-to-end merge
.venv/bin/python -m pytest tests/merge/test_reconciliation_divergent.py tests/merge/test_executor_lane_naming.py -q
.venv/bin/python -m pytest "tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget" -q
# mission branch preserved across re-finalize
.venv/bin/python -m pytest tests/lanes/test_refinalize_mission_branch.py tests/lanes/test_lane_identity.py -q
# match-site parsers
.venv/bin/python -m pytest tests/specify_cli/lanes/test_lane_naming_parsers.py -q
# gate (non-vacuous)
.venv/bin/python -m pytest tests/architectural/test_no_worktree_name_guess.py -q
# #5113
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py -q
```

## Manual check (#5113)
```bash
spec-kitty agent mission create demo --mission-type software-dev --friendly-name Demo \
  --purpose-tldr t --purpose-context c --pr-bound --branch-strategy already-confirmed --json
spec-kitty agent decision open --mission <slug> --flow specify --slot-key specify.x.y \
  --input-key x --question "Q?"            # succeeds; coordination worktree now exists
spec-kitty doctor coordination --mission <slug> --fix   # the remedy named by the error
```
