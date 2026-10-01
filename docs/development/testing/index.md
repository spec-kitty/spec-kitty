---
title: Testing the Spec Kitty codebase
description: How to run and write tests against the Spec Kitty codebase — the flakiness policy, parallel runs, local mutation testing, Playwright UI e2e, and time-dependent test discipline.
doc_status: active
updated: '2026-08-10'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/development/index.md
- docs/development/how-to/index.md
- docs/development/reference/index.md
---
# Testing the Spec Kitty codebase

Everything about running the suite and writing tests that stay honest: the
never-retry-to-green flakiness policy, the one correct parallel-run command,
local mutation testing, browser regressions, and time-dependent test discipline.

- [Test-flakiness handling policy](testing-flakiness.md) — detection tiers and the never-retry-to-green rule.
- [Running the test suite in parallel](testing-parallel.md) — the parallel-run workflow and volume gates.
- [Run mutation tests locally](run-mutation-tests.md) — `mutmut`-based assertion-quality checks.
- [UI end-to-end tests (Playwright)](ui-e2e.md) — the browser-regression pattern (its dashboard targets were removed with the bundled dashboard).
- [Write time-dependent tests](write-time-dependent-tests.md) — inject stable clocks; avoid wall-clock reads in assertions.

## See also

- [Development home](../index.md)
- [Coverage signals](../reference/coverage-signals.md)
