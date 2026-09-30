---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T12:31:16Z'
reviewer_agent: claude
wp_id: WP16
---

# WP16 review, cycle 1 (reviewer-renata): changes requested

Two gate-level findings; everything else in the focus list holds.

- [MEDIUM] src/specify_cli/cli/commands/agent/mission_check_prerequisites.py:552 -- 90f668383 introduced a new mypy --strict error, `Returning Any from function declared to return "dict[str, object]" [no-any-return]`, because `_with_cli_version` is untyped under the module's follow_imports=skip. Base: 24 errors, head: 25, and this is the only difference. Required fix: bind the call to an annotated local (`enriched: dict[str, object] = _with_cli_version(flat_error_envelope(code, message))`; `return enriched`), with no ignore. Re-run the same `--strict --explicit-package-bases` invocation on base and head and show 0 new errors.
- [MEDIUM] tests/integration/test_explicit_checkout_commands.py:143 (`test_flagless_check_prerequisites_from_inside_owned_checkout_adopts`) -- the T088 ruling requires each FR-021 adoption row to assert exactly one validation. The move-task and mark-status rows count via `claim_counter`; the check-prerequisites row asserts only exit code and feature_dir. Required fix: add the `claim_counter` fixture, clear the caches and counter before the run (as in the sibling rows), and assert `len(claim_counter) == 1`. Keep it red-on-base and green-on-head.
- [LOW] src/specify_cli/cli/commands/agent/tasks_mark_status.py:616 -- the docstring names `tasks_shared.resolve_task_owned`, which does not exist; the edge helper is `tasks._resolve_task_owned`. Fix the reference.
- [LOW, informational, no action required unless the orchestrator wants it pinned] Human-mode text and stream for ownership refusals at the Typer edge (stderr `Error: [CODE] msg`) and the JSON whitespace (indent=2) now come from emit_owned_refusal, whereas move-task, spec-commit and check-prerequisites used to print `[red]CODE: msg[/red]` on the console and compact JSON. JSON keys are identical (verified). No test pins the human form.

Verified OK: the red-first commit 440954755 precedes the fix (4 tests red on that tree); adoption rows are non-vacuous (adoption-off mutation turned 4 red); owned-arm resolver pins fail when a get_main_repo_root call is re-introduced; dce4d02db is identical to lane-m c3ede8181 (src identical); TRANSITIONAL(WP18) added by this WP is 0; `bridging: WP16` is gone; the two remaining bridging markers name WP17; out-of-map hunks are declared; ruff check and C901 are clean; the 5 red tests are red at the mission merge-base and on the lane base and green on origin/main (test fixes 2622c38bc and b506749dd exist only on main), so none are WP16's.
