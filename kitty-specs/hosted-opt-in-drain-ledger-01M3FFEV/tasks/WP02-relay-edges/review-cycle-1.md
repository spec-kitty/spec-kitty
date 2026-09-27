---
affected_files: []
cycle_number: 1
mission_slug: hosted-opt-in-drain-ledger-01M3FFEV
reproduction_command:
reviewed_at: '2026-09-27T01:07:42Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review — cycle 1: changes requested (reviewer-renata)

The core gating work is sound. Every relay edge is gated before any opener, thread or credential read. All 8 CLI commands and all 7 MCP tools pre-flight `require_drain("relay")` first. The exit codes, the drill skip and D8 are correct. `budget.py` is untouched. Seven gate mutants were all killed by the new tests. Three small issues block approval.

**Issue 1 (blocking): the production `assert` in `_report_drain_disabled` (commit bd9ae5b9) games the dead-symbol gate. Remove it.**
`src/specify_cli/cli/commands/zeitgeist.py` `_report_drain_disabled` imports `DRAIN_GUIDANCE_LINE` only so it can `assert DRAIN_GUIDANCE_LINE.split("{reason}", 1)[0] in message`. Reverting bd9ae5b9 puts `hosted_posture::DRAIN_GUIDANCE_LINE` back on the `test_no_dead_symbols.py` offender list (verified), so this import exists only to satisfy the gate. The claim that it is a "wording-drift guard" does not hold:
- The check is tautological. `require_drain` builds `str(exc)` from that same constant in the same process. `test_drain_disabled_message_reuses_the_hosted_posture_guidance_constant` already pins the wording.
- Python strips it under `-O`.
- If it ever fired, the operator would see a raw `AssertionError` traceback on exactly the path the DoD and FR-012 say must never show one.

Fix: delete the assert and the `DRAIN_GUIDANCE_LINE` import. The constant's real runtime consumer is WP08 (`moments drain status`, which depends on WP02). The symbol gate is red at HEAD anyway for six other WP01 symbols that wait on WP03/WP08 callers (`DrainPosture`, `LedgerPosture`, `drain_posture`, `ledger_posture`, `set_personal_drain`, `set_repo_drain`), so this symbol can wait for WP08 like they do. Record that in the PR's Tests run section instead of adding a synthetic caller.

**Issue 2 (blocking): the MCP campsite extraction changed the published tool schemas. The docstring says "the registered tool's schema is unchanged", which is not true.**
`_bind_tool` copies `fn.__name__`, so FastMCP now titles every argument and output model `_tool_zeitgeist_*Arguments` / `_tool_zeitgeist_*DictOutput`. Before, they were `zeitgeist_*Arguments` / `zeitgeist_*DictOutput`. I diffed `list_tools()` from base 356be89b against HEAD: properties, defaults, `seed_window_s` `minimum: 0` and the exclusion of `resolved` are all identical. The only change is 14 `title` values, which now leak private function names into agent-facing JSON schemas. Fix: set `bound.__name__ = fn.__name__.removeprefix("_tool_")`. Add a test that asserts each tool's `inputSchema["title"] == f"{name}Arguments"`, or compares against a pinned schema, so the "behaviour-preserving" claim is checked.

**Issue 3 (blocking, T008 step 0 / Sonar "every new helper needs tests"): the extracted helpers have no direct tests.**
T008 step 0 requires each extracted helper to get a direct test. None of these do: `history._validate_read_history_args`, `FilteredStream._poll_with_deadline`, `zeitgeist._print_watch_frame`, `zeitgeist._print_watch_summary`, `mcp_stdio._bind_tool`, and the `_tool_zeitgeist_*` bodies.
Diff coverage over the touched source is 91% overall, but `mcp_stdio.py` is at 81%. The uncovered lines are the `repos_filter` withheld branches and the `read`/`inbox` tool bodies (lines 206, 292, 305-309, 324, 338-343). `filtered_stream.py` misses lines 505, 511 and 513 (the queue-timeout and `TimeoutError` exits of `_poll_with_deadline`). `zeitgeist.py` misses line 324, the non-event frame branch of `_print_watch_frame`.
Add narrow direct tests for each helper, including the `_poll_with_deadline` early-exit branches and the drain-on MCP `read`/`inbox`/withheld paths.

**Non-blocking (fix if cheap):**
- The guidance "one line" is one logical line, but rich soft-wraps it at 80 columns (seen in a manual run). Consider `console.print(message, markup=False, soft_wrap=True)`. The CLI test also never asserts exactly one line. Add that assertion.
- `operability drill-timeout` renders `skipped: drain off` in red because the colour logic is `green if pass else red`. A clean skip should not render in the failure colour (#4737 is exactly this misdiagnosis class). Consider yellow or dim for the skip. This is in your owned CLI file.
- The docstring of `test_outbox_list_show_reject_revoke_are_not_pre_flighted` names reject/revoke, but the test only exercises list/show and asserts no exit codes.
- New `# type: ignore[attr-defined]` on `resp.readline()`/`resp.close()` in `_poll_with_deadline`. This matches the existing `_read_frames` pattern, so it is acceptable, but a small `Protocol` (`readline() -> bytes`, `close() -> None`) for `resp` would remove both.
- `tasks.md` is generated from `wps.yaml` and has no subtask checkboxes, so `mark-status T006..T010` has nothing to record. This is a tooling or format gap, not yours. It is noted here so a later reviewer does not chase it.
