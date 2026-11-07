---
affected_files: []
cycle_number: 1
mission_slug: owned-charter-status-custody-01M6TZKC
reproduction_command: spec-kitty agent tasks move-task WP01 --to approved --mission owned-charter-status-custody-01M6TZKC --agent 'Reviewer Renata (Kimi K3)'
reviewed_at: '2026-11-07T15:18:15Z'
reviewer_agent: Reviewer Renata (Kimi K3)
wp_id: WP01
---

Approved by Reviewer Renata (Kimi K3): approval:WP01

# WP01 independent review — APPROVE

Reviewer: reviewer-renata (distinct reviewer role/profile)

No findings.

## Spec-to-diff

- `src/specify_cli/core/owned_charter.py` keeps the primary resolved-path fast path and the owned `CharterScope.resolve` call unchanged.
- Only the unequal arm resolves `STATUS_STATE.read_dir` via the required owned `mission_context_for(... tolerate_unmaterialized_coord=True)` and compares resolved paths exactly.
- Foreign mismatch keeps `MISSION_CONTEXT_CONFLICT`; resolver errors are not swallowed.
- Runtime, e2e expectations, startup budget, #7206 assets, and neighboring PR scopes are unchanged.

## Red-first proof

- Test commit `89a7d0b` precedes production commit `e786baf`.
- The new integration class was RED 1 failed / 1 passed in 57.09s, with `ActionContextError: charter Mission differs from the validated owned checkout` on the positive case.
- Installed-CLI `[0]` was RED 1 failed in 105.34s before the fix with `MISSION_CONTEXT_CONFLICT`.

## Reviewer test evidence

- Full `tests/integration/test_owned_prompt_charter_scope.py`: 20 passed, 2 failed in 34.05s. Both failures are the same `StopIteration` nodes reproduced on unmodified `origin/main` source in 5.04s and already tracked under #7110; the new class passes 2/2.
- `tests/integration/test_owned_next_runtime.py`: 26 passed in 6.55s.
- Installed-CLI `[0]` after the fix: 1 passed in 43.78s.
- Implementer shared baseline: `make test-fast` — 2894 passed, 6 skipped in 29.68s.
- Scoped mypy: Success, 2 files. Ruff check/format: clean, 2 files. Changelog style: 0 errors; spelling: 0 findings.

Approve the WP implementation. The all-20 nightly matrix and umbrella suite recovery remain pending and are not claimed by this verdict.
