---
affected_files: []
cycle_number: 1
mission_slug: decisions-lock-timeout-refusal-01M66YMG
reproduction_command:
reviewed_at: '2026-10-30T19:04:35Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# Review feedback — WP01 (round 1, reviewer-renata)

Verdict: changes requested (1 item).

## F1 — the human-mode refusal is unproven (SC-002)

`test_repair_lock_timeout_is_a_structured_refusal` drives `--json` only. SC-002 requires
`DECISION_LOCK_TIMEOUT` "in every output mode the command supports", and the human branch
of the new renderer (`console.print(f"[red]Error:[/red] {exc}")`, exit 1, no JSON) has no
test at all — a regression there (e.g. printing a partial report first, or exiting 0)
would pass every existing test.

Add `test_repair_lock_timeout_refusal_human_mode` on the same `_diverged_mission`
fixture: hold the lock, shorten the wait through the module constant, invoke
`doctor decisions --mission <m> --repair` (no `--json`), and assert exit 1, no
`LockAcquireTimeout` escaping, exactly one `Error:` line carrying the code's remedy
("Nothing was written; retry the command."), no JSON document on stdout, and a
byte-identical decisions tree.

Everything else in the diff is accepted as-is: the single translation seam, the deleted
duplicated wait constant, the widened `mission_slug` annotation, and the catch placed
before every `_emit_*` call.
