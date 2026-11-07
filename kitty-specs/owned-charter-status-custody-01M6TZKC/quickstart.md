# Quickstart: Owned Mission coordination status charter custody

From `/home/stijn/.t3/worktrees/spec-kitty/t3-bfbad01c`:

```bash
# Public red-first reproduction (record before the fix, rerun afterward)
SPEC_KITTY_RUN_PERFORMANCE=1 PWHEADLESS=1 .venv/bin/python -m pytest \
  'tests/e2e/test_worktree_owned_root_concurrency.py::test_installed_cli_keeps_two_owned_worktrees_isolated[0]' -q

# Focused integration and owning runtime surfaces
.venv/bin/python -m pytest -q -p no:randomly tests/integration/test_owned_prompt_charter_scope.py
.venv/bin/python -m pytest -q -p no:randomly tests/integration/test_owned_next_runtime.py

# Shared ordinary-change baseline
make test-fast
```

Do not run the 20-node matrix locally. The merged-commit nightly owns that verdict and the separate startup-budget investigation.
