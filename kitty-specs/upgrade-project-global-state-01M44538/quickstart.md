# Quickstart — verifying the fix

1. Reproduce the defect on the old behaviour with the issue's scripts (grounding Appendix A): `bash pathA.sh <new> <rc4>`, `bash pathB.sh <new> <3.2.7>`, `bash pathC.sh <new> <rc4> lanes_with_coord`. Before the fix, each prints `BUG:` or refuses.
2. Run them again with the fixed CLI. `consolidate` exits 0 and lands every WP. After `upgrade`, no lane or coordination branch has a `chore: apply spec-kitty upgrade changes` commit.
3. Recovery: on a repository already upgraded by rc5, install the fixed CLI and re-run `spec-kitty consolidate --mission <slug>` (or the review). No manual edits are needed.
4. Targeted tests: `tests/upgrade/`, `tests/lanes/`, `tests/consolidation/test_conflict_classifier.py`, `tests/integration/test_lane_lifecycle_sync.py`, `tests/specify_cli/test_state_contract.py`, the mission's new real-CLI tests, then `make test-fast`.
