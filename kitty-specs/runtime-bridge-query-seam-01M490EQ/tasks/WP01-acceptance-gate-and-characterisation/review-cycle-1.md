---
affected_files: []
cycle_number: 1
mission_slug: runtime-bridge-query-seam-01M490EQ
reproduction_command:
reviewed_at: '2026-10-06T17:09:37Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 review cycle 1 — REJECT (reviewer-renata, opus)

Checks: 20 passed / 60 xfailed at 647514d4e; ruff clean; no runtime_bridge patches; _owner single lookup; fakes survive the move.

1. BLOCKING — T004 owned half missing: `_wrap_with_decision_git_log`'s `except CoordinationWorkspaceUnavailable: if owned is not None: raise` arm is untested anywhere. Add an owned test (mint_test_fact) with mission_context_for raising CoordinationWorkspaceUnavailable; assert same object propagates and fake ran.
2. SHOULD-FIX — T002 board step `accept` → decline case missing.
3. SHOULD-FIX — T003 query temp-run cleanup: covered at tests/next/test_query_mode_unit.py:608 (patches io, not the bridge); add or record waiver. Same for _map_wp_step_decision blocked reason.
4. SHOULD-FIX — self-mutation rows vacuous on base (clean engine already contains the bridge import); assert on the planted snippet alone.
5. NIT — §5 F401 has no row; say CI ruff covers it.
6. NIT — document scanner limits (importlib.import_module, attribute access, defs in if/try).
7. NIT — commit message arithmetic (60 failed / 7 passed).
8. NIT — contract file names the gate file wrongly.
