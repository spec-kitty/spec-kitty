# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi/deepseek-v4.1-flash-1017 · Chose a dedicated COORD-partition kind (MISSION_EVENT_LOG) over borrowing STATUS_STATE: is_status_state_path is deliberately narrow (status.events.jsonl/status.json) and is consumed by claim-commit bundling and coord planning staging, which must not widen to an event log the claim never wrote. Fixing the classifier fixes every consumer; an accept-local special case would leave the file None for the residue gates and contradict the router's derived-partition rule.
