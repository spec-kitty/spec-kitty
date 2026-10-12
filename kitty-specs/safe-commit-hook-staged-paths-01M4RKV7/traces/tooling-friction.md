# Tracer: Tooling Friction — safe-commit-hook-staged-paths-01M4RKV7

Tooling this mission touches: `spec-kitty` CLI (mission/plan/tasks/implement/review/accept/
consolidate), `git` (pre-commit hooks, `commit --only`, `diff-tree`, temp-index commits via
`GIT_INDEX_FILE`), `pytest`, `ruff`, `mypy`, the orchestrator-api contract gates.

- **[2026-10-12][specify] `gh issue view` / `gh api users/...` blocked.** GitHub GraphQL and
  non-repo-scoped REST are refused in this session (`HTTP 403`, repo-scoped only). Workaround:
  used `gh api repos/{owner}/{repo}/...` for read, `POST .../assignees` and `.../comments` for the
  claim. Candidate friction, documented; no code change.
- **[2026-10-12][specify] `gh api -f body@file` rejected.** `-f` does not read a file;
  `-F body=@<file>` does. Workaround applied. Minor, documented.
