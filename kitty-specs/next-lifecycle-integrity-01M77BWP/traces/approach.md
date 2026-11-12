# Tracer: approach

Mission: next-lifecycle-integrity-01M77BWP. Append dated entries during implementation; assess at close.

- 2026-11-12: Research squad (3 grounding agents + second opinion) before specify; second squad (consumer + history lens) for the query-question ruling. Tidy-first IC-01 before the behaviour changes.
- 2026-11-12: Post-tasks squad (architecture + test lenses) found 5 blockers before implementation; three escalated (never-rewind widen, invariant by construction, acceptance freshness). Implementers and reviewers are separate subagents. Identity: `--agent claude` with profile `python-pedro` (implementer) vs `reviewer-renata` (reviewer), so the independence check passes with no model identifier recorded.
- 2026-11-12: WP01 was rejected because the WP Test Strategy listed `tests/runtime/next` but not the owning subsystem's `tests/runtime` directory. The construction-time invariant broke 6 fixtures there. Lesson: the test strategy must list the owning subsystem's whole test dir (CLAUDE.md test policy step 2).
