---
affected_files: []
cycle_number: 1
mission_slug: docsite-canary-01M74KM6
reproduction_command:
reviewed_at: '2026-11-11T06:40:18Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP01
---

# WP01 review, cycle 1 (claude-reviewer::reviewer-renata): changes requested

## Blocking

1. **NFR-001: the CLI ranges allow a run longer than the stated bound** (`scripts/docs/site_live_probe.py:83-84, 272-281, 300-302`).
   NFR-001 says one URL takes under 5 minutes in the worst case. The accepted ranges do not keep that:
   - A stub probe makes two requests per attempt: the key, then its target (`_check_target`).
   - At the maximum flags (`--attempts 6 --timeout 30 --delay 120`), one URL can take 6 x 2 x 30 + 5 x 120 = 960 s.
   - Even with `--delay 0` it is 360 s.
   - With the defaults it is 5 x 2 x 15 + 4 x 10 = 190 s, which is within the bound. So the defaults are fine; the accepted ranges are not.

   Fix options:
   - (a) A per-URL wall-clock deadline in `run()`: stop retrying once the next attempt could overrun 300 s.
   - (b) Tighten the ranges so that attempts x 2 x timeout + (attempts - 1) x delay <= 300 s is guaranteed, and refuse a combination that breaks it.

   Either way, add a test that pins the bound, for example an injected clock or sleep that fails when the budget is exceeded.

## Low (fix or leave, your call)

- `_own_page_key` re-states rule 1 (`target == key.removesuffix(".html") + "/"`) as a selection filter. That is acceptable as a class definition, but a comment saying it selects rather than decides would keep "one authority" obvious.
- `RETIRED_ROUTE` is a constant, not derived. ADR D-5 names it, and the derivation refuses it if it ever enters the ledgers, so this is fine. Mention D-5 at the constant (it is already in the comment).

## Verified (no change needed)

- The red commit `6cec6e16f` alone gives 32 failed.
- `tests/docs/test_site_live_probe.py`: 35 passed, 99% line coverage. `tests/docs`: 2326 passed, 2 skipped.
- ruff, format and `mypy --strict` are clean.
- The mutants fail their class: wrong stub target, 404 on a live URL, 200 on the retired route, non-stub at a key, stub target that is itself a stub, a 3xx not followed.
- The derivation reuses `load_baseline`, `load_moves` and `redirect_stub_target`.
- Against a local build of `site/dist` served by `python3 -m http.server`, all 8 probes pass (8/8, exit 0).
