---
affected_files: []
cycle_number: 1
mission_slug: exit-zero-data-intact-01M3KDAS
reproduction_command:
reviewed_at: '2026-09-28T11:21:56Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (reviewer-renata) — changes requested

What already works (keep it): the fold handles both orders and both are tested. Red-first holds: 7 of the 8 new tests fail on base and the healthy control passes. The diagnose path stays read-only. `--repair --json` emits exactly one JSON document and then exits 1. The doctor help text and docstring are updated. The service's TERMINAL_CONFLICT behaviour is unchanged (tests/specify_cli/decisions/test_service_terminal.py is green). ruff, ruff format and mypy --strict are clean, and complexity is at most 15. The lane passes: tests/decisions + tests/specify_cli/decisions give 203 passed and 8 skipped; the doctor-decisions consumers plus 4 architectural gates give 369 passed.

## Blocking

1. **The transition rule is defined twice (plan D3; WP review guidance: "One transition-rule definition, used by service and fold").**
   - Where: `src/specify_cli/decisions/index_fold.py:259-263`. `_select_terminal_event` hard-codes `{TerminalOutcome.DEFERRED, TerminalOutcome.RESOLVED}` and never consults `ALLOWED_TERMINAL_REOPEN` / `is_allowed_terminal_reopen`. The comment even calls it a "mirror", which makes it a second copy.
   - Only the service delegates today. If someone adds a pair to `ALLOWED_TERMINAL_REOPEN`, the write path will accept it while the fold still marks it malformed. That is exactly the drift D3 is meant to remove.
   - Required change: derive the pair acceptance from the shared rule. Map each envelope's outcome to a status via `_OUTCOME_TO_STATUS`. Accept exactly two envelopes with distinct outcomes (a, b) when `is_allowed_terminal_reopen(status(a), status(b))` holds, or the reverse for the other order. Fold the envelope whose status is the reopen *target*.
   - Keep the check order-independent, and keep the file free of service imports.

2. **No test pins the "anything else is malformed" half of the rule (T008 step 3; data-model: "Any other multi-outcome set is malformed").**
   - I probed `_select_terminal_event` directly. It raises FoldError for (resolved, resolved), (resolved, canceled), (deferred, deferred), (deferred, canceled) and (deferred, resolved, resolved), so the behaviour is correct today. But no test in the repo asserts any of these.
   - A mutation that accepts any pair and picks the resolved one would survive the whole suite.
   - Required change: in `tests/decisions/test_defer_resolve_repair_4919.py`, add a parametrised test covering at least two-resolved, resolved+canceled and a 3-event set. Hand-write those extra `DecisionPointResolved` envelopes into the log, copying a real CLI-emitted envelope shape.
   - For each case, assert that read-only diagnose reports the id in `malformed_folds` with `clean: false`.
   - Also assert that `--repair` exits 1, leaves the index entry byte-identical and leaves the log untouched.
   - Include a fold-level unit assertion that the FoldError message names the outcomes.

3. **The stale-status test never asserts what diagnose reports (FR-003).**
   - Where: `tests/decisions/test_defer_resolve_repair_4919.py:415-423`. The read-only run at :416 uses `json_output=True`, but the test takes no `capsys` and asserts only `exit_code == 0`. Nothing checks `clean is False` or the `status_mismatch` item (`decision_id`, `index_status == "deferred"`, `folded_status == "resolved"`).
   - The `--repair` call at :419-420 also never asserts its exit code, which should be 0.
   - Required change: capture and parse the diagnose JSON and assert those fields, assert that diagnose left the index unchanged, and assert the repair exit code.

4. **A `--json` refusal carries no remedy text, and no test asserts one (contract `failure-surface.md` row 1; NFR-003).**
   - The contract says a `doctor decisions --repair` refusal must include the decision id(s), "left in place", and how to inspect the event log.
   - Under `--json`, the only output is the report (`_emit_json`, `src/specify_cli/cli/commands/_decisions_doctor.py:427-440`). It has the ids but no "left in place" and no inspection pointer. The JSON refusal test (`test_fr004_repair_refuses_malformed_decision_with_existing_entry`, around :337-339) asserts only the id.
   - Required change: when `malformed_folds` is non-empty, put the remedy in the single JSON document. For example, add a `remedy` / `next_action` string field naming `spec-kitty agent decision list --mission <m>` and `status.events.jsonl`, and stating that the entries were left in place. It must stay one document on stdout.
   - Assert that field in the JSON test.
   - Also assert "left in place" in the human-mode test (`test_fr004_repair_refuses_malformed_decision_with_no_prior_entry`, around :383-385). It currently checks only the id, `agent decision list` and `status.events.jsonl`.

## Non-blocking (fix while you're there)

5. **FR-001 uses the sub-apps, not the root app.** `tests/decisions/test_defer_resolve_repair_4919.py:42-43` invokes `agent_app` / `doctor_app`. T007 asks for `CliRunner` on the root app. Switch to the root Typer app so top-level registration and the callback are exercised too.

6. **New `# type: ignore[type-arg]` lines lack a rationale.** They are at `_decisions_doctor.py:266` and test file :80 and :85. They copy an existing pattern in the file. Prefer `dict[str, Any]`, or at least use the typed form in new code.

7. **Diagnose does not use the T009 loop shape for slot_key-origin entries.** T009 says to reuse the `_rebuild_index_from_log` loop shape and send `_is_unrecoverable_slot_key_origin` entries to `lossy_attribution`. `_fold_diagnostics` folds them anyway. This is harmless for status comparison, but say so in the docstring or align it.
