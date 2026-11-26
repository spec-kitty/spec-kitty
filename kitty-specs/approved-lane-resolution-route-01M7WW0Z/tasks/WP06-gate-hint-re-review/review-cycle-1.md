---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-25T10:23:25Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP06
---

# WP06 review cycle 1 (lane-f f5a0a46056): REJECT

Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

## Verified
- **Red-first:** 26 failed / 18 passed against the 62dc019384 verifier.
- **Post-fix:** 330 passed, 1 xfailed (attribution_hint and dependency-ref tests).
- **The hint stays a hint:**
  - verdicts, describe() and recovery_guidance() are unchanged;
  - _DEPENDENCY_REF_HINT is byte-pinned.
- **Item matching:** done by full ids.
- **Today's hint is kept** for canceled/removed-work clauses, for empty wp_ids, and for pre-WP04 claims.
- **attributes_source:** claim.excluded_window_base is the pre-run target tip (claim_inputs.py:424, target_base), which follows WP01 rule (a). A None base refuses a committed union (fail closed).
- **Docstrings and typed locals:** the FR-010 docstring is accurate, and the typed locals are accepted (campsite fix).
- **Accepted behaviour change:** a recorded tool merge that is dropped as unreviewed and carries auto-resolved content now gets the re-review hint. WP13 should state this.

## Must fix
1. **(MED, operator ruling) Partial match prints only the --dependency-ref hint.**
   - Where: _dropped_merges_covering / _with_attribution_hint. The current behaviour is pinned by test_partial_match_keeps_dependency_ref_hint and test_partial_match_on_one_shared_path_keeps_dependency_ref_hint.
   - Problem: an unreviewed hand merge explains part of the FAIL, and foreign content explains the rest. The operator is told only to declare a dependency ref. For the merge's content that is wrong, because --dependency-ref refuses Mission work. The operator ruling was to suppress that hint for this shape.
   - FIX: when at least one unattributable item is covered by a dropped merge, and no canceled or removed-work clause is present:
     - print the re-review sentences for the covering merges;
     - then print a dependency-ref sentence scoped to the remainder only, e.g. "For the remaining content (<n> item(s) no dropped merge explains): <_DEPENDENCY_REF_HINT>".
   - When nothing is covered, keep _DEPENDENCY_REF_HINT byte-identical.
   - Keep the wp_ids-empty rule: if a covering merge names no WP, fall back to today's hint.
   - Tests: update the two partial-match tests to assert both parts, and add one case where the covered part is a deletion.
   - WP12's real-git e2e must include this partial shape.
