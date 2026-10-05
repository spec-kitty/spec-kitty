# Quickstart: reproduce and prove

Run from the repository root checkout with the synced environment. In a lane worktree use
`PYTHONPATH=$(pwd)/src <repository root>/.venv/bin/python -m pytest ...`.

## Baseline reds on `9adc68803f`

```bash
# Track A (red)
.venv/bin/python -m pytest "tests/integration/test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_onto_a_protected_target" -n0 -p no:cacheprovider -q

# Track C (red)
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_commit_recipes.py -n0 -p no:cacheprovider -q

# Track B (green on a fast machine; red on the shared runner)
SPEC_KITTY_RUN_PERFORMANCE=1 .venv/bin/python -m pytest tests/performance/test_owned_checkout_perf.py -n0 -p no:cacheprovider -q
```

## Job-selection dry run (Track C, Track B count pin)

```bash
.venv/bin/python -c "from scripts.ci.gate_selection import select_gates, select_modules; p=['src/specify_cli/cli/commands/_commit_message.py']; print(select_gates(p).selected_jobs, select_modules(p))"
```

## Nightly selections (closeout only)

| Job | Command |
|---|---|
| integration + next | `.venv/bin/python -m pytest tests/integration tests/next -q -n auto --dist loadfile` |
| performance | `SPEC_KITTY_RUN_PERFORMANCE=1 .venv/bin/python -m pytest -m performance -q` |
| interpreter shard 3 | Python 3.13, `-m "fast or unit"`, path list at `.github/workflows/ci-nightly.yml:646` |
| out-of-matrix | `tests/specify_cli` minus registry-claimed directories, `-m "not stress and not timing"` (`ci-nightly.yml:1111-1127`) |

A nightly run on the branch: `gh workflow run ci-nightly.yml --ref issue-5611-5419-nightly-green`.
Escalation steps only act on `refs/heads/main`.
