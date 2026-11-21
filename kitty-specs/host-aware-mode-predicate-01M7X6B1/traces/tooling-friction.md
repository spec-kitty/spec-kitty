# Tooling friction — host-aware-mode-predicate-01M7X6B1

Tooling touched: spec-kitty mission lifecycle (create/plan/tasks/analyze/implement), pytest + an NTFS emulation fixture, ruff, mypy.

- **[2026-11-20][plan] `spec-commit` refuses a directory argument and the decisions lock file.** Passing `decisions/` failed. Passing every file under it failed too, because `index.json.lock` is a runtime lock. The workaround was to pass the files explicitly, excluding `*.lock`. Candidate gap: let `spec-commit` skip runtime locks.
- **[2026-11-20][implement] mypy reports `no-any-return` at `asset_preparation.apply_assets` only when it checks `operations.py` and `asset_preparation.py` together.** The base commit shows the same error under the same invocation, and each file checked alone is clean. This is pre-existing and depends on the invocation; it is not caused by this Mission.
