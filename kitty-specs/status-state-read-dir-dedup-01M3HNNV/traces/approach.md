# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->
2026-09-27 — Start: hoist the post-merge gate's `_resolve_partition_read_dir` (with its #154 `.exists()` degrade) to one public resolver and repoint the render (`workflow_cores`) and verdict (`tasks_verdict_persistence`) STATUS_STATE copies onto it. Red-first via the #154 ambient-ancestor fixture, which reproduces the silent empty read today (`latest_review_feedback_reference` → `(None, None, None)`).
2026-09-27 — Shift: the same ambient fixture also makes the review-cycle artifact dir (WORK_PACKAGE_TASK) phantom, so `has_prior_rejection` stays False even after the fix. Narrowed FR-002 to "same resolver for the event-log read" and recorded the artifact-dir exposure as C-005 / a follow-up instead of widening the mission.
2026-09-27 — Post-spec/plan squad folds: the phantom is only the foreign-anchor shape (UNMATERIALIZED raises since #4959), so C-002 now covers both raising cells and the resolver unit tests pin both propagations; SC-001 narrowed to the two read paths actually fixed; red-first repro driven through the public entries (`resolve_review_feedback_context`, `resolve_review_verdict_facts`) instead of internals; trio-seam allowlist added to WP02's surface.
2026-09-27 — Hoist moved into WP01 (post_merge now delegates in the same commit) so the new public name has a cross-module caller at its introducing commit and `test_no_dead_symbols` stays green there; WP ownership updated to match.
2026-09-27 — Pre-PR: WP02 reviewer found the AST guard missed the two-step `seam = placement_seam(...); seam.read_dir(STATUS_STATE)` idiom; widened to any `.read_dir` receiver with a poison case. Pre-PR architect squad: no overlap on main, no guard lost (only the in-memory `assert_partition_invariant`), no docs name the removed helpers.
