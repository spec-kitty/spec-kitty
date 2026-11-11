---
affected_files: []
cycle_number: 2
mission_slug: docsite-canary-01M74KM6
reproduction_command:
reviewed_at: '2026-11-11T06:54:32Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP01
---

# WP01 review, cycle 2 (claude-reviewer::reviewer-renata): changes requested

## Blocking

1. **A slow response still overruns the per-URL budget** (`scripts/docs/site_live_probe.py`, `http_fetcher.fetch`: `opener.open(request, timeout=min(timeout, limit))` then `answer.read()`).
   The urllib/socket `timeout` bounds each blocking socket operation, not the whole request. A server that answers 200 and then sends one body byte every few seconds (each gap under the timeout) keeps `read()` going past the deadline. The URL then **passes**, because the late answer is judged as a normal 200.

   Reproduced with a local `ThreadingHTTPServer` that sends a 10-byte body at one byte every 0.4 s:
   - settings: `URL_BUDGET` patched to 1 s, `timeout=1`, `attempts=1`;
   - result: elapsed 3.6 s, `ok=True`, `detail=HTTP 200`.

   At the real settings the same trickle exceeds 300 s, so the module docstring's "whatever the options" and the 5-minute limit in NFR-001 do not hold over real HTTP. The fake-clock tests cannot see this, because the injected fetch returns instantly.

   Fix options:
   - Read the body in chunks inside `fetch` and stop at the deadline. The fetch knows `limit`, so compute `deadline = monotonic() + limit` and check it between chunks. Each chunk read is bounded by the socket timeout, so overshoot is at most one socket timeout, which is never more than the time left.
   - Then report an overrun as a failure ("per-URL budget ... exhausted"), never as a pass.
   - Pin it with a test against a trickling local server and a small budget. Make the budget injectable in `run()` or in the fetcher, so the test takes about a second.

   Optional: name the remaining unbounded step (DNS resolution happens outside the socket timeout) in the docstring as a known residual.

## Verified (no change needed)

- Red evidence: the red commit `2412cfa28`'s tests, and the final test file, each give 8 failed against the cycle-0 code. The later helper change did not weaken it.
- Fake-clock schedules (hangs, stub second request, retries, pauses) stay within 300 s. The budget failure names the URL and gives "after N of M tries".
- `test_site_live_probe.py`: 41 passed, 99% line coverage. `tests/docs`: 2332 passed, 2 skipped. ruff, format and `mypy --strict` are clean.
- The cycle-1 Low items are addressed (selection comment, D-5 source).
