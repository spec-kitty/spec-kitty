# Tooling friction: coord-status-log-home-01M3VJKP

- 2026-10-01: Driving a coord mission to `implement` in a scratch project needs `.kittify/derived/` ignored and an out-of-tree analysis report, or `record-analysis` refuses on a dirty tree.
- 2026-10-01: Single test files take 75–85 s locally on this 4-core container even when the test body runs in seconds; budget accordingly.
- 2026-10-01: `move-task WP01 --to for_review` refused with "no recorded claim base" because the work was committed on the thread branch before the WP was claimed; `--force` was used with the commit range in the note.
- 2026-10-01: The blast-radius run found 39 tests that used create as a fixture and assumed a lazily materialized coordination worktree (or a primary status log). They were re-pinned to set up UNMATERIALIZED / EMPTY / remote-only states explicitly.
