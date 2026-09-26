# Tracer: test blast radius (#4972)

All commands run from the lane worktree with the main checkout's venv via
`PYTHONPATH="$PWD/src" <repo-root>/.venv/bin/python -m pytest ...` (per the
"never run bare `uv run`" guidance — this worktree has no dedicated `.venv`).

## Targeted regression + focused unit tests

```
PYTHONPATH="$PWD/src" <venv>/python -m pytest \
  tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py \
  tests/upgrade/test_upgrade_worktree_commit.py \
  tests/upgrade/test_worktree_stamp_guard.py -q
```
Result: **26 passed** in 2.19s (0 failed).

## `tests/upgrade/` (full directory, per WP T005)

```
PYTHONPATH="$PWD/src" <venv>/python -m pytest tests/upgrade/ -q
```
Result: **46 failed, 838 passed, 2 skipped, 1 warning** in ~5m10s.

All 46 failures are the SAME pre-existing environment failure class,
unrelated to this diff: every failure traces to
`tests/upgrade/preview_support/fixtures.py:59` /
`tests/upgrade/preview_support/provenance.py:39` asserting
`Missing executable: <worktree>/.venv/bin/spec-kitty` — this worktree has no
dedicated `.venv` (deliberately; tests run against the main checkout's venv
via `PYTHONPATH`), so the `preview_support` fixture family that shells out to
an installed-in-checkout `spec-kitty` binary cannot resolve one. Confirmed
pre-existing by re-running a representative subset
(`test_public_witnesses.py::test_original_global_preview_is_read_only`,
`test_preview_oracle.py::test_child_environment_seals_fixture_overrides`,
`test_upgrade_cli_contract.py::test_project_json_downgrade_refuses_without_dry_run`)
against the UN-fixed `runner.py` (`git stash push -- src/specify_cli/upgrade/runner.py`):
identical 7/7 failures, same `Missing executable` cause, both before and
after the fix. Category 3/4 of the baseline-red gotcha (stale-install /
environment false reds) — none of these touch `_upgrade_worktrees` or
worktree metadata.

## `tests/e2e/test_upgrade_post_state.py` + `tests/specify_cli/cli/commands/test_upgrade_command.py`

```
PYTHONPATH="$PWD/src" <venv>/python -m pytest \
  tests/e2e/test_upgrade_post_state.py \
  tests/specify_cli/cli/commands/test_upgrade_command.py -q
```
Result: **59 passed** in 24.74s (0 failed).

## `make test-fast` equivalent (baseline)

`make test-fast` itself shells to `uv run --frozen`, which is disallowed in
this worktree (re-syncs and can disturb the hand-built `.venv`), so the
target's exact dirs/markers/flags were replayed against the main venv:

```
env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 PYTHONPATH="$PWD/src" <venv>/python -m pytest \
  tests/unit tests/status tests/cli tests/specify_cli/runtime \
  tests/architectural/test_no_retired_subsystems.py \
  -m "(fast or unit) and not slow and not e2e and not integration and not regression and not distribution and not live_adapter and not stress and not windows_ci and not platform_darwin" \
  -n auto --dist loadfile -p no:cacheprovider -q
```
Result: **3 failed, 2044 passed, 5 skipped, 4 warnings** in 228.59s.

The 3 failures are all in `tests/cli/commands/test_charter_json_error_contract.py`
and are unrelated to this diff: each fails with
`"Refusing charter write from linked git worktree <path>: use a
repository-root checkout or dedicated clone for charter authoring."` — an
environment-classification refusal from running the suite inside a linked
worktree rather than the repository-root checkout, not anything
`_upgrade_worktrees`/metadata-shaped. Confirmed pre-existing by re-running the
file against the UN-fixed `runner.py` (stash): identical 3/11 failures with
the identical worktree-refusal message, both before and after the fix.

## ruff / format / mypy / complexity (touched files)

```
ruff check src/specify_cli/upgrade/runner.py \
  tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py \
  tests/upgrade/test_upgrade_worktree_commit.py
# All checks passed!

ruff format --check src/specify_cli/upgrade/runner.py \
  tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py \
  tests/upgrade/test_upgrade_worktree_commit.py
# 3 files already formatted

ruff check --select C901 src/specify_cli/upgrade/runner.py
# All checks passed! (touched functions stay <= complexity 15)

mypy --strict src/specify_cli/upgrade/runner.py src/specify_cli/upgrade/metadata.py
# Success: no issues found in 2 source files
```

Note on the last command: a NARROW single-file `mypy src/specify_cli/upgrade/runner.py`
invocation reports two `no-any-return` findings, but both are the documented
`follow_imports = "skip"` artifact for `module = ["specify_cli.*"]` in
`pyproject.toml`'s `[tool.mypy]` config (the same class of false positive the
existing `protection_policy` / `asset_preservation.backup` / `core.errors`
overrides exist to fix, issue #3719) — under that skip, `ProjectMetadata`'s
concrete field/return types resolve as `Any` when `runner.py` is checked
alone. One of the two (`_record_migration_result`'s `return recorded`) is
pre-existing and confirmed present, unchanged, in the UN-fixed baseline at
its pre-diff line number. The other (`_aligned_worktree_timestamp`'s
`return main_stamp`) is new code from this fix; checking it together with its
one dependency (`metadata.py`, restoring the normal import graph) shows it is
correctly typed with zero issues. `pyproject.toml`'s mypy config was left
untouched — out of this WP's scope (`src/specify_cli/upgrade/runner.py` +
`tests/upgrade/` only).
