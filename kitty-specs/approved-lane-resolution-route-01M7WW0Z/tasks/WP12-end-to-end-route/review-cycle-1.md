---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-25T21:17:32Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP12
---

# WP12 review cycle 1 (lane-l 54bb2db99f): REJECT (two LOW)
Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

## Binding DoD verified
- (a) git < 2.40: the `--attr-source` flag is dropped and a "cannot neutralise attributes" line is printed.
- (b) MERGE_PROBE_CONFIG_PINS are passed as -c flags.
- (c) The target tip is used as the attribute source; the test for this was red first.
- (d) git < 2.36: the cannot-show form is used.
- `--no-ext-diff` and `--no-textconv` are always passed.
- Probes run only when needed (NFR-001).

Re-runs:
- red-first: ImportError at collection
- post-fix: 882 passed, 8 skipped
- no_dead_symbols + layer_rules: 117 passed

## Questions answered
1. Halt-reason wording: accepted.
2. N3 forced -> REJECTED_REVIEW_ARTIFACT_CONFLICT is accepted as the e2e verdict (see must-fix 2).
3. N3 self -> REVIEW_NOT_INDEPENDENT: accepted.
4. Merge line read from the review prompt file and matched by SHA: accepted.
5. Partial shape reached through a written tool record: accepted. In the docstring, call it a "tool-merge simulation (same writer)", not "forged", and keep the shape assertion (parents [before, mission tip]).

## Must fix
1. (LOW) Unsafe fallback source in context_block._attributes_source / wp_range._target_tip.
   - Problem: when the target cannot be read, the code falls back to --attr-source=<range base>. That base can hold a lane-committed merge=union, which reopens case (c).
   - Fix: fall back to the empty tree instead, and update the note text to match.
   - Test: with an unreadable target and a union committed before the window base, the printed command uses the empty tree and lists the path.
2. (LOW) The claim-level proof for N3 forced is missing.
   - Fix: add a claim-level test, either in the route module or as recorded leeway in WP05's test_resolution_merge_unreviewed.py. Start from the route's incorporation-merge state and record a forced in_review->approved (or a forced approval without an approved review result), so that REJECTED_REVIEW_ARTIFACT_CONFLICT does not fire first.
   - Assert: build_approved_wp_set refuses RESOLUTION_MERGE_UNREVIEWED, and the approval stamp is unchanged (_is_forced_review_approval does not restamp).
   - If such a test already exists in WP05's file, point to it and this item is closed.
