# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-3 · Friction: the first mission scaffold (agent-string-parser-hardening-01M6694B) was created while on main, freezing target_branch=main; spec-commit then refused (PROTECTED_BRANCH_REFUSED). Removed the scaffold (worktree, lane branch, kitty-specs dir) and recreated with --start-branch issue-6755-agent-string-parser-hardening; corrected slug posted on the issue. Lesson: switch to the topic branch before mission create.
