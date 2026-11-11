---
affected_files: []
cycle_number: 3
mission_slug: docsite-canary-01M74KM6
reproduction_command:
reviewed_at: '2026-11-11T07:07:44Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP01
---

# WP01 review, cycle 3 (claude-reviewer::reviewer-renata): changes requested

## Blocking

1. **The deadline still does not cover the status line and headers** (`http_fetcher.fetch`: `opener.open(request, timeout=min(timeout, limit))`).
   The chunked read closes the body path. But `getresponse()` reads the status line and headers with one fixed socket timeout per `recv`, so a server that trickles its headers carries a request past the deadline.
   This covers the 200 path, the 3xx `Location` path and every error path, because no body is read on any of them.

   Reproduced against a local socket server, with `budget=1.0` and `timeout=1`, one byte every 0.3 s:

   | Schedule | Elapsed | Verdict |
   |---|---|---|
   | trickled headers, then 200 | 12.0 s | fails ("budget exhausted while reading the body") |
   | trickled `Location` on a 301 | 7.2 s | fails (HTTP 301) |
   | trickled chunked body | 1.0 s | fails (budget exhausted), within the deadline |

   The verdicts are right, but the time bound is not. At the real settings, a header gap under 30 s keeps one request alive with no limit, so NFR-001 ("at most 5 minutes per URL") still does not hold by construction.

   Suggested fix, which closes every remaining path (headers, redirects, the body, a chunk-size line, and DNS) in one place: bound the whole fetch by wall clock.
   - Run each request in a worker thread, then `join(timeout=left)`. On overrun, return "budget exhausted" and abandon the daemon thread, closing its socket if reachable.
   - Alternatively, use a socket wrapper whose `recv` re-caps its timeout to the deadline before every call.

   Pin it with the trickled-headers schedule above, at a small budget.

## Low

- Coverage misses `site_live_probe.py:276` (the in-loop deadline return) and `:281`. These are hard to reach without an injectable clock in `http_fetcher`. If you adopt the wall-clock watchdog, the in-loop check may become redundant; otherwise inject `clock` into `http_fetcher` and test that branch with a fake response whose `read1` advances the clock.
- DNS residual: acceptable on a GitHub runner for `docs.spec-kitty.ai`. The watchdog above would also bound it, so the docstring residual can then go.

## Verified (no change needed)

- The trickle test is a real regression guard. Reverting only the chunked read, against the final test file, fails `test_a_trickled_body_fails_at_the_budget_instead_of_passing_late` and `test_a_body_over_the_size_cap_fails` on assertions, not on `TypeError`. The cycle-1 fetcher passes a trickled body late (cycle-2 repro).
- `test_site_live_probe.py`: 44 passed, 99% line coverage. `tests/docs`: 2335 passed, 2 skipped. ruff, format and `mypy --strict` are clean.
