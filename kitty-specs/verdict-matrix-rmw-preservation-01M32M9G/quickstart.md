# Quickstart — Verifying the verdict-matrix RMW preservation fixes

All commands run from the repository root checkout of `spec-kitty_THREE`, using the editable venv
(`.venv/bin/python -m pytest`, NOT a bare `uv run` which would re-sync the env).

## #4858 — acceptance-verdict concurrency

Red-first (before the fix), the new regression must be RED on the mission base and GREEN after:

```bash
# The new concurrency tests (flat + coord + criterion), then the owning suites:
.venv/bin/python -m pytest tests/specify_cli/acceptance/test_acceptance_verdict_command.py -q
.venv/bin/python -m pytest tests/integration/test_accept_matrix_coord_partition.py -q
.venv/bin/python -m pytest tests/acceptance/ tests/lanes/test_acceptance_matrix.py -q
```

Behavioural check: two concurrent verdicts for distinct invariants (earlier-started finishing
last, one failing) → both rows survive on disk and `overall_verdict == "fail"`; a spy confirms
`feature_status_lock` is acquired with `lock_key == matrix_dir.name` under the git common dir, the
slow check runs before the lock, and `write_acceptance_matrix` routes through `atomic_write`.

## #4868 — issue-verdict coord legacy-Markdown preservation

```bash
.venv/bin/python -m pytest tests/integration/test_issue_verdict_coord_legacy_md_preservation.py -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_issue_verdict_command.py -q
.venv/bin/python -m pytest tests/specify_cli/tasks/ -q
.venv/bin/python -m pytest tests/architectural/test_issue_matrix_json_migration_completeness.py -q
```

Behavioural check: on a coord mission with a legacy `issue-matrix.md` (#A `fixed` + evidence),
recording issue #B keeps BOTH #A and #B in the committed coord `issue-matrix.json` (resolved via
`coord_read_dir_for`), reports `migrated is True`, and leaves no primary-side residue. The flat
control (`test_issue_verdict_command.py::...test_legacy_markdown_mission_migrates_on_first_write`)
stays green.

## Gates

```bash
.venv/bin/python -m pytest tests/architectural/test_lock_primitive_ban.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_no_retired_subsystems.py \
  tests/architectural/test_no_legacy_terminology.py -q
make test-fast
uv run --frozen ruff check . && uv run --frozen ruff format --check .
```

## Red-on-base verification (ATDD, per root)

For each new test, confirm RED on the mission planning base and GREEN on the final commit:

```bash
git stash  # or check out the base
git -C . show <base>:...  # run the new test against the pre-fix source via PYTHONPATH if needed
```
