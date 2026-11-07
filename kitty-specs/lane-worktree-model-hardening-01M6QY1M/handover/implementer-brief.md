# Common implementer brief: Mission lane-worktree-model-hardening-01M6QY1M (epic #7276)

- Load your assigned agent profile first (`spec-kitty profiles show <profile>`) and work under it. Read /home/user/spec-kitty/CLAUDE.md
  (project rules) and follow the WP prompt file you are given, which is the source of truth for scope.
- Charter: ATDD red-first: commit the failing acceptance test(s) as a SEPARATE commit BEFORE any implementation commit (C-011).
  Complexity <= 15 per function; no new `# noqa` / `# type: ignore`; mypy --strict clean on touched files; `uv run --frozen ruff check <files>`
  and `uv run --frozen ruff format --check --force-exclude <files>` clean. Mission, never "feature". `consolidate`, never "merge" for lanes.
- Tests: run your WP's declared targeted surface plus its blast radius (CLAUDE.md "Test policy"). NEVER run `make test-full`, a bare
  `tests/architectural/` directory, or e2e/performance suites; only named architectural gate files. Record exact commands and pass/fail counts.
  Classify any red you did not cause per CLAUDE.md's "baseline-red gotcha" before touching it.
- LANE WORKTREE ENVIRONMENT: if your workspace is under `.worktrees/`, first run `make sync-packs` there (the packs tree is not shared).
  Run Python with the lane's own source first on the path, e.g.
  `PYTHONPATH=$PWD/src /home/user/spec-kitty/.venv/bin/python -m pytest ...` (the shared editable venv otherwise imports the ROOT checkout's src/).
  Verify once with `PYTHONPATH=$PWD/src /home/user/spec-kitty/.venv/bin/python -c "import specify_cli;print(specify_cli.__file__)"`.
  For mypy/ruff use `/home/user/spec-kitty/.venv/bin/mypy` / `.venv/bin/ruff` with your file paths.
- REPOSITORY ROOT CHECKOUT WPs (planning lane): other agents work in the same checkout concurrently. Never `git add -A`/`git add .`, never stash,
  never reset, never checkout other files. Commit ONLY your WP's owned files with explicit paths:
  `spec-kitty safe-commit <path> <path> -m "..."` (or `git add <paths> && git commit`). If a commit picks up someone else's file, stop and report.
- Commits: no model identifiers anywhere. End every commit message with:
    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_019C2Tk4jy87Q2BYScdrsEnj
  Commit identity must be `Claude <noreply@anthropic.com>` (check `git config user.email`).
- Integration check before handoff: new code must have live callers; grep for them. Old paths removed or redirected.
- Handoff: `spec-kitty agent tasks mark-status <Txxx...> --wp WPxx --status done --mission lane-worktree-model-hardening-01M6QY1M`. IMPORTANT: always pass your FULL identity `--agent claude::<your-profile>` (e.g. claude::python-pedro) on move-task, or the review-independence gate (REVIEW_NOT_INDEPENDENT) refuses the approval, then
  `spec-kitty agent tasks move-task WPxx --to for_review --mission lane-worktree-model-hardening-01M6QY1M --agent claude::<your-profile> --note "<summary>"`.
- Tracer files: do NOT edit Mission files from a code lane. Return, in your final message, a "Friction" list and a "Decisions" list
  (one line each) for the orchestrator to append to kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/.
- Final message (<= 250 words): commits (sha + subject), tests run with counts, lint/mypy results, out-of-map edits, Friction, Decisions,
  anything you could not do.
- NEVER run a mutating `doctor ... --fix`, `upgrade`, or `migrate` against the shared repository (/home/user/spec-kitty or any other lane). Test them only in tmp fixtures. The installed CLI is the base code. Lane worktrees carry the managed status sparse exclusion, so pass `--allow-sparse-checkout` if a base-code spec-kitty command refuses on it.
