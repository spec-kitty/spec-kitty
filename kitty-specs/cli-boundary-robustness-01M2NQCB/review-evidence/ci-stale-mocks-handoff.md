# CI stale resolver mocks follow-up (#4674)

Workspace: `review-pr`, branch `issue-4600-cli-boundary-robustness`; starting HEAD `7d6e1592f3ffc5682899ebe6e7d91d166ab36506`. Python Pedro implementer; cached resolved `WP03-profile.json` reread. Only `tests/agent/test_commands.py` changed; no product/state/core edits, no SaaS setting override, no uv/symlink, no push or approval.

Three stale mocks now accept typed keyword-only `json_output: bool = False` and record calls. Existing assertions retained; additional exact mode assertions are `[False]` for human verify/dashboard and `[True]` for JSON verify. Existing positional defaults preserved. No catch-all kwargs.

CI `ci-agent-shard3.log`: 2 failed, 498 passed, 6 skipped (327.49s), both unexpected keyword `json_output`. Same-file JSON sibling was not reported in that shard; direct local reproduction proves it shares the defect (no speculative explanation of shard selection).

Red before edits at starting HEAD, exact command (cwd review-pr):
```sh
PYTHONPATH=src ../spec-kitty/.venv/bin/python -m pytest tests/agent/test_commands.py::test_verify_setup_command_runs tests/agent/test_commands.py::test_dashboard_kill_stops_instance tests/agent/test_commands.py::test_verify_setup_json_output -q > ../ci-stale-mocks-red.log 2>&1
```
Result: 3 failed in 95.33s, each TypeError unexpected keyword json_output. Existing failing tests supply red proof; no invented test-only red commit needed.

Green uses same exact command with output `../ci-stale-mocks-green.log`; result **3 passed in 76.01s**, exit 0.

Validation:
- `../spec-kitty/.venv/bin/ruff check tests/agent/test_commands.py`: pass.
- `git diff --check`: pass.
- `../spec-kitty/.venv/bin/ruff format --check tests/agent/test_commands.py`: preexisting failure before/after. Formatter-debt exclusion exists in pyproject line993. Sole proposed formatting hunk is unrelated assertion in test requiring --mission (final line285); changed mock code needs no formatting. Retained debt, no exclusion/config changes. Logs ci-stale-mocks-format-{baseline,final}.log and ci-stale-mocks-format-diff.log.
- `../spec-kitty/.venv/bin/mypy --follow-imports=skip tests/agent/test_commands.py`: 32 inherited errors before and after. Entire diagnostic logs equal after normalization of shifted line numbers, verified programmatically. Logs ci-stale-mocks-mypy-{baseline,final}.log. No type debt expansion.

Commit `0e906806015e4260d7846b29d1d956bd905d3fbc` (one test file, 24 insertions/3 deletions). Independent reviewer and root own canonical completed-mission `mission follow-up --commit` recording; no WP-state rewrite.
