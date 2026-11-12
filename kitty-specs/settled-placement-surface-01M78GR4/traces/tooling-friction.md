# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-12 · claude-orchestrator · Live repro on main: spec-commit WRONG_SURFACE from the coord worktree (relative path); from the root the remedy says git checkout <topic>, which git refuses (coord worktree holds it); implement on protected root refuses with --no-auto-commit advice the agent action command lacks; baseline-tests.json silently left untracked.

2026-11-12 · claude-orchestrator · CLI lifecycle commits (status transitions, finalize-tasks, record-analysis, implement claim) are unsigned (%G? = N) although commit.gpgsign=true with an ssh key; the host flags them Unverified (#5197). Deferred to the post-consolidation history cleanup, which re-signs every commit.

2026-11-12 · python-pedro · WP01: the T001 integration test takes ~95s serially (real create + finalize per row); the prompt's 'walk from nearest existing ancestor' was unnecessary because find_ancestor already walks a not-yet-created path; primary_partition_checkout's raw-repo_root vs main-root comparison is behaviour-equivalent only because every caller treats holder==repo_root like None.
