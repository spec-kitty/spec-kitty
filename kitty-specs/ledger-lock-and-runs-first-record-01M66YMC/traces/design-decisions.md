# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-agent P19 (pi/deepseek-v4.1-flash-1017) · Lock path: a dedicated <ledger>.lock sidecar beside the partition file, taken through kernel.locks.machine_file_lock(blocking=True, timeout_s=30, reentrant=True). Rejected every existing anchor-keyed family (event_log_lock, synthesis_lock, project_event_log_lock) because each owns a different semantic object and needs a git common dir; the ledger must work outside git. Adds no path rule, so it does not duplicate #6727's anchored_lock_path.

2026-10-30 · pi (deepseek-v4.1-flash-1017) · Lock file location is <project>/.kittify/migrations/<ledger>.lock, not beside the payload: .kittify/migrations/ is the already-IGNORED per-clone surface, so the lock never appears in git status and is never swept into an upgrade autocommit (which derives its commit set from git status --porcelain). A sibling of the TRACKED .kittify/migration-ledger.jsonl would be untracked noise in every consumer checkout; get_runtime_gitignore_entries emits no .lock rule. Pinned by test_an_append_never_adds_an_untracked_file_to_git_status.
