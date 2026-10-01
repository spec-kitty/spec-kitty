---
title: UI End-to-End Tests (Playwright)
description: Lessons for browser-driven UI regression tests; the in-repo dashboard Playwright suite was removed with the dashboard (#5530).
doc_status: active
updated: '2026-10-01'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/index.md
- docs/development/how-to/review-gates.md
- docs/development/testing/testing-parallel.md
---

# UI End-to-End Tests (Playwright)

> **Status (2026-10-01):** the bundled local web dashboard was removed from the
> CLI ([#5530](https://github.com/spec-kitty/spec-kitty/issues/5530)), together
> with the `tests/ui/` Playwright suite, its fixtures and the `pytest-playwright`
> test dependency. The CLI has no web UI to test. A replacement UI built on the
> planned Mission Status Read API
> ([#5528](https://github.com/spec-kitty/spec-kitty/issues/5528)) will live in its
> own repository and carry its own browser-driven suite. Restore the old suite
> from git history (mission `playwright-ui-e2e-bootstrap-01KWX72W`, issue
> [#1008](https://github.com/spec-kitty/spec-kitty/issues/1008)) if it is useful there.

## Why browser-driven tests

Backend and API tests cannot catch a bug where the server responds correctly
but the browser renders it wrong. That is exactly what shipped in PR #970: 338
backend tests and every architectural test passed while the dashboard's WP-card
click-through modal silently dropped the agent identity, because no test layer
exercised the click-then-render flow. `CLAUDE.md`'s "Never claim the frontend
works without Playwright proof" rule comes from that incident.

## Lessons to carry into any future UI suite

1. **Boot the app hermetically.** Run it in-thread on an ephemeral port against
   a synthetic project root; never reuse a singleton that detaches a process or
   kills siblings on a shared port range.
2. **Seed fixture data in the exact shape the reader consumes**, and keep that
   synthetic shape in one shared fixture so every test agrees with it.
3. **Wait for real state, never a fixed sleep.**
4. **Assert the pre-interaction baseline first**, so a later "populated"
   assertion proves a real transition.
5. **Scope every assertion to the container under test**, never page-global:
   a field that also renders elsewhere on the page makes a page-global check
   pass even when the feature under test is broken.
6. **Prove non-vacuity before committing**: break the render path (not the
   fixture data) and confirm the test fails, then revert.
7. **Run headless** (`PWHEADLESS=1`) and record the command and result in the PR.
