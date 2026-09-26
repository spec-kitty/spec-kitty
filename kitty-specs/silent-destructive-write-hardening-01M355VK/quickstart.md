# Quickstart — reproduce & verify

Each defect ships an issue-pinned `@pytest.mark.regression` test (RED on merge-base, GREEN on branch).

## WP01 #4908
Repro: `charter interview/generate --mission-type research` → `charter activate directive 025-boy-scout-rule`;
assert `catalog.mission` flips research→software-dev and references shrink (RED), then GREEN after fix.
Verify: sibling `pack apply --compile` path also preserved.

## WP02 #4897
Repro: healthy mission + one resolved Decision Moment → `doctor mission-state --fix`;
assert DecisionPoint rows drop to 0 and `doctor decisions` goes unclean (RED), then GREEN after fix.
Verify: `agent decision list` count unchanged; already-preserved classes still preserved.

## WP03 #4894
Repro: two branches each append a fenced `## section` to the same `traces/*.md`; `git merge`;
assert fences/Example lines collapse (RED), then GREEN after fix (both sections intact or conflict).
Verify: `_union_acceptance_history` behavior unchanged.

## Blast radius (run in addition to `make test-fast`)
- WP01: `tests/specify_cli/cli/commands/charter/` (+ `tests/charter/`, `tests/doctrine/` if touched)
- WP02: `tests/status/`, `tests/migration/` (or mirror), decisions tests
- WP03: `tests/merge/`, `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py`
- `ruff check .` · `ruff format --check .` · `mypy`
