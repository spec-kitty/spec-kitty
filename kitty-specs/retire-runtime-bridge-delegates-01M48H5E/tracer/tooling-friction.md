# Tracer: tooling friction

Append one entry per friction point met while running this mission (command, what happened, workaround, upstream issue if filed).

- 2026-10-06 (plan): `gh issue view --json` fails in cloud sessions (GraphQL blocked); used `gh api repos/.../issues/<n>` (REST) to verify assignees.
- 2026-10-06 (WP01): any pytest invocation over `tests/runtime/` takes ~90 s wall time here (collection and conftest import cost, with another pytest running in the tree); foreground commands hit the 120 s tool timeout and were moved to the background. Workaround: run in the background and wait on the output file. No upstream issue filed.
- 2026-10-06 (WP01): `mypy tests/runtime/...` follows imports and reports a pre-existing `tests/lane_test_utils.py:85` no-any-return; the module-as-`RequirementGrammarLike` argument is also rejected by mypy (existing `test_bridge_cores.py` has the same error). Used `cast` in the new file instead of a suppression.
- 2026-10-06 (WP03): the gate file takes ~85 s on a cold run (it reads every `src/` module); the same file is ~4 s warm. Not a failure.
- 2026-10-06 (WP05): a foreground `python -m pytest ... | tail` on `tests/runtime/` hit the 120 s tool timeout again and was auto-backgrounded; a pipe without a newline between two commands then merged them into one background job. Workaround: write pytest output to a file in the scratchpad and wait with Monitor.
- 2026-10-06 (close-out): every commit made through spec-kitty's own commit path (`safe-commit`, `spec-commit`, status transitions, `issue-verdict`, `accept`, `consolidate`) is unsigned although the global git config sets `commit.gpgsign=true`, so GitHub shows them Unverified. Worked around by re-signing the compacted history at close-out.
- 2026-10-06 (accept): `acceptance-matrix.json` is seeded with placeholder criteria ("Verify FR-00x is satisfied", notes "TODO: replace…"). `acceptance-verdict` records result/evidence but offers no way to set the description or clear the note, and the accept prompt forbids hand-editing the JSON, so the placeholders ship. Evidence strings carry the real proof.
- 2026-10-06 (implement): `analysis_report_required` reports the analysis stale after any spec.md edit, including a Deferred-list addition made by a close-out WP; re-recording is cheap but the gate cannot tell a scope change from a bookkeeping edit.
