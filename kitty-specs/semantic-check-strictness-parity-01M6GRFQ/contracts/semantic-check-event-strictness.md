# Contract invariant: the strictness a `SemanticCheckEvaluated` event records

**Status**: preserved by #7065 (no payload change)

## Payload

`SemanticCheckEvaluated.effective_strictness` is one of `off`, `medium`, `max` — the
`spec_kitty_events.glossary.GlossaryStrictness` enum, validated on write by
`spec_kitty_events.persistence.build_record`. The field is required and non-optional; there
is no "unknown" member, so a producer that has not resolved a strictness cannot write one.

## Invariant

For a given step execution, the value persisted in the event equals the value the generation
gate resolved for that execution, and `blocked` equals `should_block()` applied to that value
and the check's conflicts.

Both sides reach it through one function, `glossary.strictness.resolve_context_strictness`,
so the invariant is structural rather than test-only:

| Producer / consumer | What it does with the value |
| --- | --- |
| `SemanticCheckMiddleware` (layer 2) | resolves it, stores it on the context, passes it to the emitter |
| `emit_semantic_check_evaluated` | records the explicit value, else the context's, else resolves it through the same function |
| `GenerationGateMiddleware` (layer 4) | resolves it and enforces it with `should_block` |
| `specify_cli glossary conflicts --strictness` | filters the persisted events by it |

## What must not change

- No producer may substitute a policy literal when a strictness is unresolved; the fallback
  is the resolution chain's documented default (`medium` when nothing is configured), not a
  constant in the emitter.
- The gate's own decisions must stay independent of the event: the event records, it does not
  decide.
- A malformed or unrecognised value is ignored in favour of the configured policy; the write
  path never raises because of it.

## Known limitation (by design)

Clarification (layer 3) runs after the check and before the gate, so `blocked` is the gate's
decision for the conflicts present **at check time**. A conflict resolved interactively is
recorded as found-and-then-resolved, not as never found. Patching the persisted event
afterwards is not an option: the ledger is append-only.
