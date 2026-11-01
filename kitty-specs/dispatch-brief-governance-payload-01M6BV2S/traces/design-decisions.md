# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · Brief mode is a command-layer rendering concern: the executor still assembles governance every call, and InvocationPayload/_serialize_slots are untouched, so the Op record, glossary scan and close contract cannot drift.

2026-11-01 · claude · Brief JSON sets governance_context_text null and adds governance_context_reference; a new key plus a null, never a removed or renamed key. When there is no text, brief mode leaves the payload exactly as today.

2026-11-01 · claude · fetch_command carries --json because only the JSON text field is byte-identical to the embedded payload; the console render wraps to terminal width.
