# Approach

- 2026-10-06: grounding squad (alignment + scope) → operator ruled guard-side exemption over birth stamp.
- 2026-10-06 post-spec review: the backfill verifier's `has_evictable_state` counts `tasks.md` checkboxes, so "legacy runtime" had to narrow to the frontmatter-only slice or the exemption would never fire.
- 2026-10-06 plan: discovered the dogfood test (#5300) does not call `is_cut_over`; it uses `eligible_runtime_missions` + `assert_birth_invariant_holds`. The exemption becomes one helper consumed by both.
