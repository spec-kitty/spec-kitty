# Tooling friction

- **[2026-10-27][setup] Charter sibling repo attach refused.** `add_repo spec-kitty/spec-kitty-charter` was denied by the session permission classifier; grounding proceeded without it (no charter-service surface is touched). Disposition: workaround.
- **[2026-10-27][specify] spec-kitty helper commits carry no attribution trailer.** `spec-commit`, `setup-plan`, `finalize-tasks` and `record-analysis` author their own commits without the operator's `Co-Authored-By` trailer. Disposition: fixed at closeout by history compaction.
- **[2026-10-27][plan] New tests cannot live beside the module they test.** `tests/specify_cli/` and `tests/specify_cli/cli/commands/` are `out_of_matrix_test_dirs` (nightly only), so per-PR diff coverage needs `tests/core/` and `tests/cli/commands/` instead. Disposition: workaround; #4374/#4732 track promotion.

2026-10-27 · claude · [implement] Issue-matrix guard counts every #NNN in all planning artefacts, not just spec.md: approval of WP01 was refused until context-only citations (#3895, #6117, #6185, #6608, #6675, #6715, events #92) got not-applicable rows. Disposition: workaround (record rows up front).

2026-10-27 · claude · [implement] With agents.auto_commit=false, move-task --to approved leaves the review-cycle artifact and the note event uncommitted on the coordination worktree. Disposition: workaround (orchestrator safe-commits after each verdict).

2026-10-27 · claude · [implement] A fresh lane worktree venv lacks the optional extras and packs are untracked: the first uv run fails tests/core collection (respx) until uv sync --frozen --all-extras and make sync-packs run in the lane. Disposition: workaround.

2026-10-28 · claude · [consolidate] Review feedback was lost on consolidation: implement's auto-merge brings coord-branch review-feedback-N.md onto the lane branch, move-task then refuses until the lane deletes it, and the squash consolidation carries that deletion to the target. Restored both WP02 feedback files from the unreachable coord commit 4caef809. Disposition: candidate gap (file upstream).
