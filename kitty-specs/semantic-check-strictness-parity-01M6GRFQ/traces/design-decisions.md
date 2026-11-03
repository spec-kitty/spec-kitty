# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · One resolution path beats patching the event: resolve_context_strictness() now owns the global->mission->step->runtime chain, called by the gate, the semantic-check middleware and (as a last resort) the emitter. The event is written before the gate runs, so a post-hoc patch of the persisted JSONL was rejected -- the log is append-only and the contract has no 'unknown' strictness.

2026-11-03 · python-pedro · The event's blocked flag now uses should_block(), the gate's own predicate, instead of 'strictness != off'. That closes the second half of #7065: a medium-policy run with a medium-severity conflict was recorded as blocked while the gate proceeded. Clarification still runs between check and gate, so the event records the decision for the conflicts present at check time; documented in the spec and the how-to.
