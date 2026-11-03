# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · reviewer-renata · Anchor = a .git entry that can be a repository home. A .git FILE always qualifies (gitdir/worktree pointer); a .git DIRECTORY qualifies only with HEAD; a directory without HEAD is one git itself walks past, so it holds nothing to preserve. Chose a structural HEAD check over a second git probe because the ownership/safe.directory cases git refuses cannot be told apart from 'not a repository' by exit status or message, and re-running git with safe.directory=* to classify would bypass the check in production code.
