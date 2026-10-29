# Tracer: design decisions

- 2026-10-27: owned refusals use C2 strict `{ok:false, error:{code,message}}` + optional `context` + optional `spec_kitty_version` (operator rulings, Decision Moments in `decisions/`).
- 2026-10-27: renderer loses its `envelope` argument; the shape is fixed by construction from `json_contract.json_error`.
- 2026-10-27: redundant `result:"error"` / `success:false` dropped in favour of `ok:false`.
- 2026-10-27: the move-task owned catch-all keeps accepting any ActionContextError code (validation posture unchanged).
