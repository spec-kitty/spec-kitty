# Design decisions

- 2026-11-20 — No `CoordState.REMOTE_ONLY` member: 49 uses / 14 probe callers; the split is decided at the single ref-read failure point instead.
- 2026-11-20 — Remote-only error is a subtype of the unreadable-ref error so ~60 existing catch/relay sites keep working and `next` relays the new code.
- 2026-11-20 — Classification only on the failure path (NFR-001), keyed on the local head not resolving; a corrupt local ref keeps the unreadable code.
- 2026-11-20 — `policy._missing_destination_remedy` (#7726) left as is (different semantics).
