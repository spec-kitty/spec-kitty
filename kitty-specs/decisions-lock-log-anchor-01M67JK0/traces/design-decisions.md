# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Kept the planned anchor-first lock order (C-004) after checking every existing holder: no path takes the ledger sidecar first and then waits for the anchor, and the only other anchor-lock user (state/retention.py) takes it non-blocking, so anchor -> sidecar -> status has no inversion. Consequence found in implementation: the pre-existing ratchet tests/specify_cli/decisions/test_service_terminal_concurrency.py::test_decisions_lock_waiter_times_out_and_writes_nothing pinned the LOCK_TIMEOUT error's lock_path to decisions/index.json.lock. With a lock taken ahead of it, the lock a waiter contends for first is the anchor, so that assertion now names event_log_lock_path(status.events.jsonl); every behavioural assertion (structured DecisionError, decision_id, retry hint, nothing written) is unchanged. This also pins the acquisition order through the observable error.
