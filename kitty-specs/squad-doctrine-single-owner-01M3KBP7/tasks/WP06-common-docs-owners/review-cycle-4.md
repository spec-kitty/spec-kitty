---
affected_files: []
cycle_number: 4
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T14:05:18Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review, cycle 4: CHANGES REQUESTED (one blocking item, one-line fix)

Reviewer: claude (reviewer-renata). This is a focused delta review of 53c8c082.

## Blocking

1. **Regression: the broadened regex no longer catches the single-value `doc_status: <value>` form.** That form is DIRECTIVE_042's original drift bug. The new pattern is `\bdoc_status\b.{0,40}?[:(]\s*[A-Za-z]+(?:\s*\|\s*[A-Za-z]+)+`. It requires at least one `|`, so a lone `doc_status: draft` is never matched. The code comment still says it "Matches `doc_status: <value>` (the original colon form)", which is now false.

   I checked this with scratch mutations of the scaffold ADR step description, keeping the MADR list and replacing the "— never `doc_status`." tail:
   - `; set doc_status: draft until the ADR is accepted.` → **33 passed** (should fail)
   - `; also set `doc_status: active` once accepted.` → **33 passed** (should fail)
   - The cycle-3 regex fails both mutations, so this is a regression and not a gap that was already there.

   **Fix (one line).** In `test_no_adr_step_prescribes_doc_status_value`, replace the pattern with an alternation that keeps both forms:

   ```python
   r"\bdoc_status\b(?:`?\s*(?:field)?\s*[:(]\s*[A-Za-z]+|.{0,40}?[:(]\s*[A-Za-z]+(?:\s*\|\s*[A-Za-z]+)+)"
   ```

   (Keep `re.IGNORECASE | re.DOTALL`.) I verified this pattern in a scratch copy:
   - the unmodified pack gives 33 passed;
   - the reviewer phrase "uses `doc_status` to track state (Proposed | Accepted | Superseded)" fails;
   - `doc_status: draft` fails;
   - `` `doc_status: active` `` fails.

   The legitimate "doc_status schema above: file it under…" and "never `doc_status`." mentions do not match it. Update the comment to match the new pattern.

## Verified (no action)

- The provenance ratchet gives 4 passed. The baseline diff removes only the `tactics/common-docs-find.tactic.yaml: provenance: 2` entry.
- The phrase "uses `doc_status` to track state (Proposed | Accepted | Superseded)" makes `test_no_adr_step_prescribes_doc_status_value` fail, so the cycle-3 should-fix is resolved.
- The trio (single_owner, provenance ratchet, no_legacy_terminology) gives 133 passed. `ruff format --check .` reports 2597 files already formatted.

## Non-blocking (accepted residual)

- A bare "it also uses `doc_status` to track state." with no value list still passes. I accept this residual because the step's own "never `doc_status`" contrast and the MADR-list checks make a silent bare mention unlikely. It is optional hardening only.
