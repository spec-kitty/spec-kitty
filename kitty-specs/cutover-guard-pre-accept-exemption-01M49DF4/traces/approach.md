# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-07 · claude · (observed 2026-10-06) Grounding squad (alignment + scope) found #5835 real on main and unsuperseded; operator ruled guard-side exemption over birth stamp.

2026-10-07 · claude · (observed 2026-10-06) Post-spec review: the backfill verifier's has_evictable_state counts tasks.md subtask rows, so legacy runtime had to narrow to the WP-frontmatter slice or the exemption would never fire.

2026-10-07 · claude · (observed 2026-10-06) Plan: the dogfood test (#5300) never calls is_cut_over; it uses eligible_runtime_missions + assert_birth_invariant_holds. The exemption became one helper consumed by both.

2026-10-07 · claude · (observed 2026-10-07) WP01 review round 1 rejected: pre_accept_exemption ignored an absent mission_id, so the CI guard failed a Mission the dogfood check exempted (the two consumers disagreed). Fixed and re-reviewed.

2026-10-07 · claude · (observed 2026-10-07) Pre-PR squad (correctness + boundary lenses) found two arch-gate blockers the targeted runs missed (meta-read census, status module boundary) plus 5 minors; folded one commit each. First CI run then caught two more (dead-symbol gate, changelog house style).

2026-10-07 · claude · (observed 2026-10-07) Tracer notes were first hand-written into kitty-specs/<mission>/tracer/ instead of via spec-kitty agent tracer-append (traces/); moved after the fact. Use tracer-append from the start.
