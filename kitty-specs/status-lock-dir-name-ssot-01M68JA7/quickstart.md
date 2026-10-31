# Quickstart — verify the status-lock directory name single-source change

All commands from the repository root,
`/home/exedev/work/sk-6516`, on `issue-6516-status-lock-dir-name-ssot`.

## 1. Red-first proof (already captured, reproducible)

```bash
# Drop the module from the audit allowlist and watch the existing gate fail.
uv run pytest tests/audit/test_no_legacy_path_literals.py \
  -k test_no_handrolled_spec_kitty_home_in_global_state_modules -q
```

Expected **after** the fix: green. On `origin/main` plus the allowlist entry
removed it fails with
`src/specify_cli/status/locking.py:65: _NON_GIT_LOCK_HOME = ".spec-kitty"`.

## 2. The gate covers the module again

```bash
uv run pytest tests/audit/test_no_legacy_path_literals.py -q
```

Expected: all green, including the new allowlist-bypassed scan that asserts no
`src/specify_cli/status/locking.py:` violation exists even with
`frozenset()` as the allowlist.

## 3. The lock behaviour did not move

```bash
uv run pytest tests/status/test_lock_fallback_never_mints_marker.py -q
uv run pytest tests/status/test_locking_reentrancy_migration.py -q
```

Expected: green with **no edits to these files**. The bare-tree test still
asserts `<root>/.spec-kitty/spec-kitty-locks/<key>.status.lock` and that neither
`.kittify` nor `.git` was created.

## 4. The review lock still resolves the same directory

```bash
uv run pytest tests/specify_cli/test_audit_tail_readers.py -q -k lock
uv run pytest tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py -q
```

Expected: green; these import `LOCK_DIR` and build real lock files under
`tmp_path / LOCK_DIR`, so a wrong value fails the behavioural path.

## 5. Runtime-root resolution is unchanged

```bash
uv run pytest tests/paths/ tests/kernel/test_runtime_root_resolver_parity.py -q
```

Expected: green — `get_runtime_root().base` still resolves to
`~/.spec-kitty` on POSIX, the platformdirs path on Windows, and
`$SPEC_KITTY_HOME` verbatim when set.

## 6. Lint and format

```bash
uv run --frozen ruff check src/specify_cli/paths src/specify_cli/status src/specify_cli/review tests/audit
uv run --frozen ruff format --check --force-exclude src/specify_cli/paths/windows_paths.py \
  src/specify_cli/paths/__init__.py src/specify_cli/status/locking.py \
  src/specify_cli/review/lock.py tests/audit/test_no_legacy_path_literals.py
```

Expected: `All checks passed!` and no "would reformat" output.

## Manual check (one-liner)

```bash
uv run python -c "
from specify_cli.paths import RUNTIME_STATE_DIR_NAME as n
from specify_cli.status import locking
from specify_cli.review.lock import LOCK_DIR
print(n, locking._NON_GIT_LOCK_DIR, LOCK_DIR, getattr(locking,'_NON_GIT_LOCK_HOME',None))
"
```

Expected: `.spec-kitty .spec-kitty .spec-kitty None` — one name, two consumers,
and the misleading `..._HOME` symbol gone.
