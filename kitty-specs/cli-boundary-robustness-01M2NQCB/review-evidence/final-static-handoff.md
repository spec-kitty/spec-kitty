# Final static validation

Frozen merged HEAD `ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92`, compared against `b17a81506331bc434b93a692f4f6261d008dc81e`. Actual changed Python paths: **47**, recorded in `final-static-python-files.txt`. Exact argv arrays, outputs and exits are in `final-static-results.json` and individual logs.

Selection command: `git diff --name-only --diff-filter=AMR b17a81506331bc434b93a692f4f6261d008dc81e..ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92 -- '*.py'`.

| Command | Result |
|---|---|
| `.venv/bin/ruff check <47 paths>` | PASS, exit 0 |
| `.venv/bin/mypy --strict <47 paths>` | Exit 1; 22 inherited errors in 3 files |
| `.venv/bin/ruff format --check .` | PASS, exit 0; 1,949 files already formatted |
| `git diff --check b17a81506331bc434b93a692f4f6261d008dc81e..ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92` | PASS, exit 0 |

The sorted full mypy error lines exactly equal the previous integrated candidate's 22 diagnostics: no added, removed, relocated, or text-changed diagnostic. WP06's two additional Python files and final WP03 correction introduce none. This is an exact line-for-line comparison, not merely equality of counts.

Inherited diagnostics: 21 test annotation/generic errors across `tests/specify_cli/cli/commands/test_mission_reopen.py` and `test_mission_follow_up.py`; one `no-any-return` at `src/specify_cli/cli/commands/agent/tasks_shared.py:572`. Prior evidence and independent baseline references remain in `integrated-static-handoff.md`, `integrated-static-mypy.log`, lane-d `wp04-mypy-baseline.log`, and `WP05-cycle2-baseline-mypy.log`. Strict mypy is not claimed green.

No tests, uv, Spec Kitty CLI, or edit commands executed. Environment copied unchanged by subprocesses; SaaS-sync settings preserved. HEAD remained identical and tracked checkout remained clean after checks. Logs: `final-static-ruff.log`, `final-static-mypy.log`, `final-static-format.log`, `final-static-diff.log`.
