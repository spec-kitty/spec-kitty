# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-28 · claude · Tracer seeded at planning (pre-spec triage: 3 read-only lenses over the 21 nightly reds).

2026-09-28 · claude · CLI auto-commits (issue-verdict, tracer-append, move-task, implement claim metadata) are created without the configured commit signature, so GitHub marks them Unverified; every push needed a manual re-sign rebase, and re-signing the finalize-tasks commit would orphan the lane bases, forcing deferral until after consolidation.

2026-09-28 · claude · spec-kitty implement leaves its own claim metadata (meta.json vcs lock, WP frontmatter base_commit) uncommitted, then the next implement refuses with 'Planning artifacts not committed'; each claim needed a manual commit. A single_branch mission still minted 7 lane worktrees.

2026-09-28 · claude · The git stash stack is shared across lane worktrees; a bare git stash/pop in one lane (red-first proofs) can pop another lane's work. Use WIP commits or git archive exports for red-first proofs instead.

2026-09-28 · claude · An in-flight mission reddens test_dogfood_corpus_backfilled on its own branch (claimed WPs make it cutover-eligible) until accept stamps status_phase; expected by the #2917 seam design but surprising mid-mission.
