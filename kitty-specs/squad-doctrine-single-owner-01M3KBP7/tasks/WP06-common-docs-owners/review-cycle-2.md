---
affected_files: []
cycle_number: 2
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T13:37:47Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review, cycle 2: CHANGES REQUESTED

Reviewer: claude (reviewer-renata). This was a focused delta review of 503abe00.

## What is resolved

- DIRECTIVE_042 no longer carries the dangling `common-docs-curation` reference, and a test pins that. The 13-section inline list in 042 and in the scaffold tactic now refers to the styleguide, which does hold the list at principle 1. No normative content was weakened.
- The docstrings, `ConfigError` messages and `--styleguide` help in `docs_structural_lint.py` now name `assets/docs_structural_lint.config.yaml` and describe the override accurately. Behaviour is unchanged, and tests/docs is green.
- The provenance baseline change from 20 to 19 is justified; the ratchet is green.
- M2 (delete "Run the live gates before handoff") and M3 (delete "File a new ADR under its era, with MADR status") are now caught by `_step_by_title`.
- Suites: 1820 passed and 8 skipped. The doctrine `-k` slice gives 262 passed, with only the expected `test_shipped_graph_is_fresh` red. The (A2)/(A3) labels are gone.

## Blocking

1. **M1 still survives, and the commit message claims otherwise.** I reproduced it in a scratch copy. In the scaffold step "File a new ADR under its era, with MADR status", I replaced
   `` `status` field (Proposed | Accepted | Deprecated | Superseded) — never ``
   with
   `` `doc_status` field (draft | active | superseded) — never ``.
   All 33 tests in `tests/doctrine/test_common_docs_single_owner.py` still pass. There are two reasons:
   - `test_no_adr_step_prescribes_doc_status_value` only matches `doc_status:\s*<value>`, with a colon. The drift written as prose ("`doc_status` field (draft | …)") has no colon.
   - `test_adr_era_and_status_step_carried_to_scaffold` asserts `"status" in text`. That is vacuous, because `doc_status` contains `status`, and the step always mentions `doc_status` as a contrast.

   Fix: pin the MADR status vocabulary in the ADR step. For example, assert the step names the MADR values (`Proposed`, `Accepted`, `Superseded`), or use a regex that requires a standalone `` `status` `` not preceded by `doc_`. Also make the A1 check reject any doc_status value vocabulary (`draft|active|deprecated|superseded|durable`, lowercase) attached to `doc_status` in an ADR step, whether or not a colon follows. The legitimate contrast "never `doc_status`" must still pass. Re-run M1 and record it truthfully.

2. **mypy is not clean on the touched test file.** The commit says "ruff check + mypy: clean", but mypy reports `tests/doctrine/test_common_docs_single_owner.py:91: error: Returning Any from function declared to return "dict[str, Any]" [no-any-return]`. The cause is `_step_by_title`'s `return step`. Fix it with a typed cast or an `isinstance` narrow, not a `# type: ignore`.

3. **The new formatter gate is red.** `ruff format --check` flags `tests/doctrine/test_common_docs_single_owner.py`, which was formatted before this commit, and `packs/built-in/assets/docs_structural_lint.py`. The lint file was already unformatted on base, but this commit adds a new unformatted hunk: the `ConfigError(f"Config file not found …")` split at about L285. CI runs `ruff format --check .` repo-wide. Run `ruff format` on both files.

## Non-blocking

- The scaffold step still says "never invent a fourteenth section". That is an implicit count restatement, and "an additional section" would be cleaner.
- `common-docs-find.tactic.yaml` L37/L45 carry "(WP04)" in consumer prose. This predates this WP, but the file is WP06-owned, so fix it while you are there (campsite rule).
