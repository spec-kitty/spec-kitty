# Quickstart — verifying the consolidate rename (#3080)

## Run the renamed command
```bash
spec-kitty consolidate --mission <handle>            # primary command (was: spec-kitty merge)
spec-kitty consolidate --resume                      # reads the same state.json
spec-kitty consolidate --dry-run                     # forecast, unchanged behavior
spec-kitty merge --mission <handle>                  # EXPECT: non-zero exit + "renamed to `consolidate`" migration message
```

## Verify the frozen KEEPS are intact
```bash
# baseline_merge_commit key still present + still drives phase derivation
grep -rn "baseline_merge_commit" src/mission_runtime/lifecycle_phase.py
# MergeStrategy value "merge" unchanged
grep -rn 'MergeStrategy' src/specify_cli/consolidation/config.py   # (moved with the package rename)
# git merge-driver plumbing untouched
spec-kitty --help | grep -i merge-driver
```

## Verify the drift guard
```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
# red-first: introduce a `spec-kitty merge` in active prose → guard fails
# green-on-legit: a `git merge --no-ff` line → guard passes
```

## Verify agents/skills regenerated
```bash
spec-kitty upgrade            # regenerates the 13 agent copies + command-skills from source
ls .claude/commands/spec-kitty.consolidate.md .codex/prompts/spec-kitty.consolidate.md
test ! -e .claude/commands/spec-kitty.merge.md && echo "old slash command removed"
```

## Behavior regression
```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/consolidation/ -q     # was tests/merge/ — 0 regressions expected
```
