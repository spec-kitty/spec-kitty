# Design decisions

- 2026-11-02 — Measure the complete existing contract, not a reduced corpus or omitted controls. Keep the 180-second per-CLI bound and use a separately bounded diagnostic outer limit only to obtain uncensored CI evidence. A permanent test-local limit is selected only after independent review of that evidence.
- 2026-11-02 — Temporary instrumentation wraps existing calls to record elapsed times without replacing results, intercepting failures, or changing source behavior. No new production dependency or permanent config-value test is planned.
