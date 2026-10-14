# Tracer: tooling-friction

Mission: main-red-test-premise-repair-01M4XV67

- The conftest shared venv ignores uv.lock (it installed events 10.5.0), which confounds reducer-version repros.
- A transient `.git/index.lock` (a background watcher) failed three CLI writes: finalize-tasks, one issue-verdict and one acceptance-verdict commit. Each succeeded on retry or was picked up by the next commit. The CLI could retry briefly on index.lock.
- `move-task --to for_review` runs a pre-review regression gate that takes several minutes and exceeds a 120 s agent Bash timeout. Agents must background it.
- `test_no_retired_paths_exist` goes red locally on untracked `__pycache__`-only directories of retired packages. The checkout is clean in git; CI is unaffected.
- `check_docs_freshness.py` needs `PYTHONPATH=$PWD` when run as a script.

## Assessment at close
The friction was environmental, not in the mission. Of the four items, only the index.lock retry is worth an upstream look.
