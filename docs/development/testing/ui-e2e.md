---
title: UI End-to-End Tests (Playwright)
description: How to boot the synthetic dashboard fixture and write a Playwright e2e test that regression-guards Mission dashboard UI rendering.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/index.md
- docs/development/how-to/review-gates.md
- docs/development/testing/testing-parallel.md
---

# UI End-to-End Tests (Playwright)

`tests/ui/` is the framework-bootstrap home for browser-driven regression
guards against the dashboard's rendered DOM (mission
`playwright-ui-e2e-bootstrap-01KWX72W`, issue
[#1008](https://github.com/spec-kitty/spec-kitty/issues/1008)). It exists
because backend and API tests cannot catch a bug where the server responds
correctly but the browser renders it wrong — exactly what shipped in PR #970:
338 backend tests and every architectural test passed while the dashboard's
WP-card click-through modal silently dropped the agent identity, because no
test layer ever exercised the actual click-then-render flow.

`CLAUDE.md`'s "Never claim the frontend works without Playwright proof" rule
is enforced by this suite, not aspirational — the runnable proof is
[`tests/ui/test_dashboard_wp_modal.py`](../../../tests/ui/test_dashboard_wp_modal.py).

## Running the suite locally

```bash
# One-time: install the headless Chromium binary (never committed; cached
# under ~/.cache/ms-playwright).
uv run playwright install chromium

# Run the suite headless, matching CI exactly.
# NOT a bare `uv run` -- that re-syncs the environment and drops the extras,
# destroying a hand-built .venv. Use the venv's own interpreter:
PWHEADLESS=1 .venv/bin/python -m pytest tests/ui/ -q
```

No real `~/.spec-kitty`, no network access, and no git repository are
required — every test boots a hermetic, synthetic project root on an
ephemeral port (see below).

## How the hermetic fixture works

[`tests/ui/conftest.py`](../../../tests/ui/conftest.py) provides two fixtures
every test in this suite builds on:

- **`synthetic_project_root`** — materializes a temp directory containing one
  synthetic Mission and work package (`kitty-specs/<slug>/tasks/WP01.md` +
  a seeded `status.events.jsonl`) using the exact frontmatter shape
  `dashboard/scanner.py::_process_wp_file` decomposes: a **dict** `agent:
  {tool, model}` plus top-level `agent_profile`/`role` keys — not the
  colon-string `agent: 'tool:model:profile:role'` form, which the scanner
  does not decompose.
- **`dashboard`** — boots the real dashboard app **in-thread** against that
  synthetic root via `start_dashboard(project_dir, port,
  background_process=False)` (`src/specify_cli/dashboard/server.py:110`).
  This is the hermetic seam: it runs on a daemon thread bound to an
  ephemeral `find_free_port()` port and dies with the pytest process — no
  PID file, no sibling processes killed. It returns a dict with
  `base_url` plus the exact identity values the fixture wrote, so a test can
  assert against known values instead of guessing.

Deliberately **not** used: `cli/commands/dashboard.py`'s
`ensure_dashboard_running` singleton. That path detaches a PID'd child
process and kills siblings on the shared dashboard port range — the wrong
tool for a hermetic, parallel-safe test.

## Writing another e2e test (copy-template)

1. **Reuse the fixtures.** Add a test function to a new or existing module
   under `tests/ui/` that takes `page: Page` (from `pytest-playwright`) and
   `dashboard: dict[str, str]` as parameters — no manual server boot needed.
2. **Navigate and wait for the real state, never a fixed sleep.**
   ```python
   page.goto(dashboard["base_url"])
   ```
3. **Assert the pre-interaction baseline first.** If your flow reveals or
   changes a hidden element, assert it starts hidden — this is what proves
   the later "populated" assertion is a real transition, not a
   coincidentally-passing check against an always-visible element.
4. **Scope every assertion to the specific container you are testing**, never
   page-global. `test_dashboard_wp_modal.py`'s core lesson: several identity
   fields also render as always-visible card badges *before* any click, so a
   page-global `expect(page).to_contain_text(...)` would still pass even if
   the feature under test (the modal) dropped the field entirely — a
   non-vacuous test must scope its locator to the specific container
   (`page.locator("#prompt-modal .agent-identity-section")`, for example),
   not the whole page.
5. **If your scenario needs different fixture data** (a second work package,
   a different lane, a different agent identity), extend
   `tests/ui/conftest.py` rather than hand-rolling fixture data inline —
   keep the synthetic-mission shape as the single source of truth so every
   test in the suite stays consistent with what the scanner actually reads.
6. **Mark it `@pytest.mark.e2e`** (already applied at module scope in the
   existing test file via `pytestmark = pytest.mark.e2e`) so it is correctly
   selected/excluded by suites that filter on that marker.
7. **Prove non-vacuity before you commit.** Temporarily break the render
   path your test exercises (not the fixture data — breaking the data also
   reds the always-visible card badge and proves nothing about your new
   assertion) and confirm your test fails cleanly, then revert.

## CI

`tests/ui` is **nightly-only**. `.github/ci-module-registry.yml` records it as
deliberately excluded from the per-PR module shards, because no per-PR job
installs a browser. `ci-nightly.yml` collects it (the interpreter sweep and the
`-m e2e` lane, both with `PWHEADLESS=1`), but no workflow currently runs
`playwright install chromium`, so the browser-backed tests skip there rather
than run.

In practice, the proof for a UI change is a local run:
`PWHEADLESS=1 .venv/bin/python -m pytest tests/ui/ -q`. Record the command and
its result in the PR. The old dedicated `ui-e2e.yml` workflow no longer
exists.
