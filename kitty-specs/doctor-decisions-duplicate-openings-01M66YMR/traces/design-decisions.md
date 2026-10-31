# Design decisions — doctor-decisions-duplicate-openings-01M66YMR (#6764)

- **[2026-10-30][plan] The finding is a report FIELD, not a `findings` code.** `clean` is computed as `base and not self.findings`, so a code such as `DECISION_DUPLICATE_OPENINGS` would flip `clean: false` and change the exit-code contract. `duplicate_openings_tolerated: list[str]` sits beside `malformed_folds` / `status_mismatch` and is excluded from `clean` (FR-003).

- **[2026-10-30][plan] The duplicate predicate lives in `index_fold`, not the doctor.** `tolerated_duplicate_openings()` reuses `_opened_identity()` / `_OPENED_VOLATILE_FIELD`, so the report cannot drift from what `_select_opened_event` accepts; it returns `0` (never raises) for differing payloads, because that refusal belongs to `fold_events` and is reported as `malformed_folds`.

- **[2026-10-30][implement] The collector runs inside `_fold_diagnostics` after `fold_events` succeeds.** That makes the two findings disjoint by construction and costs no second log read or fold pass (NFR-001); a decision missing from the index is still reported, because the property is of the log.

- **[2026-10-30][implement] The human line is `cyan` and spells out "informational".** A tolerated condition must not read as a failure, and typer's red is the existing signal for the three real findings.

- **[2026-10-30][implement] The reference update re-splices the generated section instead of regenerating the file.** Regenerating would have swept 1,014 unrelated stale lines into this PR; the section text is still produced by `build_cli_reference` (written to a temp file), so it is generator output, not hand-written prose. Filed #6835 for the staleness itself.
