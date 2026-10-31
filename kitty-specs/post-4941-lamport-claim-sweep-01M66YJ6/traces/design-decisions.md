# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Guard design: a bounded living corpus (`AGENTS.md`, the two C4 pages, `docs/architecture/status-model.md`, the domain plan, `consolidation/preflight.py`), an affirmative `Lamport (reducer|reduction|wrapper)` regex evaluated per **sentence** with a negation allowance (the corrected `status-model.md` legitimately says "carry no Lamport clock"), a table of the exact retired strings, and ADR assertions that require both the historical D-5 sentence and the 2026-10-30 amendment.

2026-10-30 · python-pedro · Non-vacuity: the detector is fed a synthetic stale sentence (must report exactly one hit), a synthetic negated sentence (zero), and a hard-wrapped stale sentence (one), so a detector that stops working cannot pass. Every covered path must exist; a missing file fails rather than skipping, so the corpus cannot drain by attrition.

2026-10-30 · python-pedro · Documented leniency: a sentence that negates the claim anywhere counts as teaching the fact. That is why the exact removals are additionally pinned in `RETIRED_PHRASES` — the allowance cannot be used to smuggle one of them back.

2026-10-30 · python-pedro · Scope call: left `docs/operations/manual-test-plan.md` §2.2 and the `docs/context/system-events.md` "Lamport Clock" glossary alone. Neither is a claim about the CLI status path (the first documents the retired SaaS sync surface, the second defines an envelope field that other logs genuinely still carry). Both are named in the PR's `## Deferred`.
