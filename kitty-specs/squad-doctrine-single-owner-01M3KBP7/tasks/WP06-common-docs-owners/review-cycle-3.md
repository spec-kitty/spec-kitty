---
affected_files: []
cycle_number: 3
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T13:53:17Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review, cycle 3: CHANGES REQUESTED (one blocking item)

Reviewer: claude (reviewer-renata). This was a focused delta review of a32e14b5.

## Blocking

1. **The provenance ratchet is red.** `pytest tests/architectural/test_builtin_pack_provenance_ratchet.py -q` gives 1 failed and 3 passed:

   ```
   test_builtin_pack_residue_baseline_is_tight
   tactics/common-docs-find.tactic.yaml: provenance baseline 2, live 0
   ```

   Removing the two "(WP04)" references from `common-docs-find.tactic.yaml` was correct, but the baseline must be lowered in the same change. Delete the `tactics/common-docs-find.tactic.yaml:` / `provenance: 2` entry at about L218 of `tests/architectural/_builtin_pack_provenance_baseline.yaml`, because the live count is 0. This file is outside `owned_files`, but WP06 already edited it in cycle 1 (20 to 19). Add the usual one-line out-of-map rationale to the Activity Log, then re-run the ratchet until it is green.

## Verified as resolved (no action)

- **M1 is caught.** In a scratch copy I rewrote the scaffold ADR step to `` `doc_status` field (draft | active | superseded) — never ``. Both `test_no_adr_step_prescribes_doc_status_value` and `test_adr_era_and_status_step_carried_to_scaffold` fail. With the step restored, all 33 pass.
- **mypy** is clean on the test file and `docs_structural_lint.py`, with no `type: ignore`. `ruff format --check .` reports 2597 files already formatted. `docs_structural_lint.py` is in the format-exclude ratchet at pyproject L265. `ruff check` passes on the touched files.
- **Suites:** tests/doctrine/test_common_docs_single_owner.py, tests/docs and test_no_legacy_terminology give 1816 passed and 8 skipped. The doctrine `-k` slice gives 262 passed, with only the expected `test_shipped_graph_is_fresh` red.
- **The common-docs-find edit** only removes the "(WP04)" parentheticals. It is in owned_files and loses nothing normative.

## Non-blocking

- The M1 regex is still narrow on prose drift. The mutation `` uses `doc_status` to track state (Proposed | Accepted | Deprecated | Superseded) — never `` passes all 33 tests. It keeps the MADR values but renames the field, and the step's title and examples still supply a standalone `status`. Consider requiring that a backticked `` `status` `` appears in the description itself and not only in the title or examples. Another option is to reject any `doc_status` mention in the ADR step description other than the "never `doc_status`" contrast.
- The "fourteenth section" wording from cycle 2 is still optional.
