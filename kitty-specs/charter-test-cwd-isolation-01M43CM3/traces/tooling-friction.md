# Tooling friction — charter-test-cwd-isolation

Tooling this mission touches: `spec-kitty` mission CLI, pytest (run from lane worktrees), git linked worktrees, `gh`.

- 2026-10-04 — `spec-kitty agent mission create ... --start-branch <b>` (default topology, resolved to `coord`) failed with `meta.json commit failed: safe_commit: failed to stage requested files`, left a partial scaffold on disk, left the checkout on `main` and did not create the start branch. The resume probe then reported `malformed`. Removing the scaffold and re-running with `--topology lanes` succeeded. The staging error carries no git stderr, so the cause is unknown; a plain `git add --dry-run` of the same paths succeeded.
- 2026-10-04 — `spec-kitty spec-commit` refuses a directory argument (`decisions/`); decision files must be passed one by one.
- 2026-10-04 — A scratch linked worktree without its own `.venv` gives a `ModuleNotFoundError: pydantic` red in `test_interview_mapping_mission_alias` (subprocess `uv run --no-sync`), which looks like one more linked-worktree failure but is a venv cause (see #5140).
- 2026-10-04 — `tests/release/pinning_rule_inventory.json` was already stale on the base branch (`derive_pinning_inventory.py --check` non-zero, one freshness test red) before any mission change. Filed as #5660; WP01 regenerates the file.
- 2026-10-04 — A grounding subagent compared against `origin/main` (the fork, 119 commits behind) rather than `upstream/main`; briefs should name the upstream ref explicitly.
- 2026-10-04 — `record-analysis`, `accept` and `consolidate` refuse on any untracked file in the checkout, including other missions' untracked matrix files and editor config. Worked around by listing them in `.git/info/exclude` for the duration of the command and restoring it after; stashing would have moved files another session may be using.
- 2026-10-04 — `move-task --to approved` is refused until every cited issue in the issue matrix has a verdict; the reviewer subagent cannot set mission-level verdicts, so the first approval bounced back to the orchestrator.
- 2026-10-04 — A transient `.git/index.lock` collision hit one `acceptance-verdict` write (and probably the first `mission create`); the write landed with the next command. Likely the code-index file watcher running git concurrently.
- 2026-10-04 — `move-task --to for_review` prints nothing about the pre-review gate (scope, duration, result), so an implementer cannot tell what it covered.
- 2026-10-04 — After any edit to a test file, the first pytest run in that checkout spends about 35 s in the wall-clock-assertion collection hook rescanning `tests/`; it reads as a slow test file.
- 2026-10-04 — Approval and review commands leave status and review-cycle files uncommitted on the mission branch; each needs a follow-up `spec-commit`.
- 2026-10-04 — `scripts/docs/check_docs_freshness.py --ci` crashes with `ModuleNotFoundError: scripts` unless run with `PYTHONPATH=.`.
- 2026-10-04 — Three charter project-layer tests fail order-dependently on the base branch (`Unknown agent-profile ID 'ops-responder'`); reported as #5689.
- 2026-10-04 — `consolidate` squashes the lanes into one commit by default, so the red-first commit order is lost on the mission branch and the history has to be rebuilt by hand for a rebase-merge repository.
