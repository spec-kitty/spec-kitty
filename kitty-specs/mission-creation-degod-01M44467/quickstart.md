# Quickstart: verifying the mission-creation decomposition

```bash
# Golden matrix (core + CLI). Must be green with 0 diff to the frozen harness.
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py \
  tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py -n 4 --dist loadfile -q
git diff <WP01-commit> -- tests/core/golden tests/core/test_mission_creation_golden_*.py   # must be empty

# Regenerate the snapshot (ONLY on the recorded base commit, to prove reproducibility)
SPEC_KITTY_REGEN_GOLDEN=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py -q

# Pure cores and family checks
.venv/bin/python -m pytest tests/core/test_mission_creation_decisions.py tests/core/test_mission_creation_family.py -q

# Patch census (reporting tool, not a gate)
.venv/bin/python -m tests._support.patch_census --report

# Gate files implicated by the move (named individually; never the whole directory)
.venv/bin/python -m pytest tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_mission_resolver_walker_gate.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py \
  tests/specify_cli/cli/commands/test_commit_recipes.py tests/core/test_adapters.py \
  tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py -q

make test-fast
```

Baseline reds to expect: baseline-red #5705 (`test_commit_recipes::test_no_unallowed_git_commit_recipe_strings_in_src`) and #5706 (`test_mission_creation_fire_once` under coverage, co-scheduled).
