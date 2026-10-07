# Quickstart: verify the fix

```bash
# Reproductions (red on base, green after)
SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest \
  tests/upgrade/test_noop_upgrade_history_untouched_5811.py \
  tests/integration/migration/test_residue_dir_not_mission_5812.py -q

# Manual check on a repository with historical Missions
git status --short            # clean
.venv/bin/spec-kitty upgrade --yes
git status --short            # still clean under kitty-specs/ and .kittify/mission-state-audit/

# Explicit repair stays a no-op on healthy history
.venv/bin/spec-kitty doctor mission-state --fix
git diff --stat -- 'kitty-specs/*/status.events.jsonl'   # empty for writer-shaped logs
```
