# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Three frictions: (1) the lane worktree does not carry the untracked packs/ tree, so tests/architectural/test_no_legacy_terminology.py reports 'no synced files under packs/internal' until make sync-packs runs in the worktree; (2) a git checkout -- <file> during a non-vacuity probe discards uncommitted production edits, so the probe must be reverted by a scripted edit, not by git; (3) test_issue_4891_accept_missing_lanes is red on pristine origin/main because the #6715 gate refuses its never-created lane branch (filed #6859).
