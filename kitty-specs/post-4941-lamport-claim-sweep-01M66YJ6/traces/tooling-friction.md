# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · `docs/architecture/event-ledger-writers-and-readers.md` is frozen by `tests/architectural/test_events_import_frozen.py` (ADR 2026-10-29-1 D-9), so its G-3 gap-table row cannot be edited by a docs sweep without re-pinning `_FROZEN_OBJECTS` (operator approval) or editing the copy in `spec-kitty/spec-kitty-events`. Reverted the page byte-for-byte, dropped it from the guard corpus (its G-3 row still carries an affirmative "Lamport reduction" claim), and filed #6822 for the row.

2026-10-30 · python-pedro · `make sync-packs` / `uv sync` were already done in this clone; no friction. `spec-kitty next --agent X` re-issues the review step when the WP approval was refused for a missing issue verdict, which is the intended remedy path but reads as a stuck loop until the verdict is recorded.

2026-10-30 · python-pedro · The single-branch review gate requires `--agent <reviewer>` on `move-task --to approved`; without it the approval is refused as `SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT` with the placeholder `user`. Fine once known, but the first attempt reads like a review-state error rather than a missing flag.

2026-10-30 · python-pedro · The pre-review regression gate reported `source_mismatch` (baseline captured under `DeclaredCommandScopeSource/text`, head under `DeclaredCommandScopeSource/junit_xml`) for WP02 and WP03, so its comparison was skipped. No test regressed; the mismatch is a harness comparability artefact worth a look.
