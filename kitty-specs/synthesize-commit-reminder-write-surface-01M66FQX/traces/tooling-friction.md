# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-j · First specify run created the mission with target_branch=main (protected); spec-commit refused. Unwound the 6-minute-old mission (coord worktree + branch + untracked scaffold; reverted the 3 aborted lifecycle.jsonl lines) and re-created on the topic branch issue-6631-synthesize-reminder-write-surface. Lesson: create the mission from the topic branch, or pass --start-branch.

2026-10-30 · maintainer-j · tests/charter/conftest.py autouse _git_init_tmp_path inits tmp_path as a git repo on the default branch before the test body, so git init --initial-branch is a no-op re-init there; the e2e test must git branch -M to a non-protected lane branch (default {main,master} are protected for safe-commit when .kittify/config.yaml has no protection block). Lane worktree creation required committing mission-events.jsonl first (spec-commit).
