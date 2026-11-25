---
affected_files: []
cycle_number: 1
mission_slug: issue-matrix-over-matching-01M81KK0
reproduction_command:
reviewed_at: '2026-11-22T13:06:48Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review — cycle 1: changes requested

Reviewer: `claude::reviewer-renata`. Range: `cf136b73..6339a2b7` (code commit `a19bc320`).

## Verdict

Reject on one blocking finding: the #7808 colour filter opens a new fail-open path inside
the gating scope, against NFR-002 and the ADR amendment's own guarantee. #5297, #5516 and
FR-006 hold up. The scope rule is an allowlist (`_in_gating_scope` accepts only `spec.md`
and direct `tasks/*.md` files), the persisted `GatingClass` vocabulary is unchanged, and the
red-first claim reproduces: 29 failed / 22 passed when the new test file runs against the
pre-fix source at `cf136b73`.

## B1 (blocking) — `_CSS_COLOUR_DECLARATION_PREFIX` drops real references, in spec.md too

The prefix has no left boundary and no declaration-start anchor, so any lower-case
colour-bearing word that ends right before `: #N` matches, even inside a longer word. The
match makes `_matched_issue_number` return `None`. The reference is then not demoted to
cited: it disappears from discovery and from the audit trail. This happens in `spec.md`
and `tasks/` as well. Reproduced with `issue_numbers_in_text` on this branch (each returns
`[]`; it should return `[4521]`):

| Line | Why it matches |
|------|----------------|
| `Border-color: #4521 tracks this` | `order-color`. This contradicts the claim that a capitalised label stays a reference. |
| `Recolor: #4521 is broken` | `ecolor` (mid-word) |
| `Fix text color: #4521` | prose `color:` |
| `See the outline: #4521` | prose `outline:` |
| `Fix the shadow: #4521 rendering` | prose `shadow:` |
| `- shadow: #4521 follow` | list bullet |
| `--note: #4521` | custom-property arm |
| `fill: #12345` | 5 digits, which is not a valid hex colour length |

NFR-002 says no new fail-open path inside the gating scope. The ADR amendment says nothing in
`spec.md`/`tasks/` stops gating "unless it is a colour". None of these lines is a colour.

**Fix asked for:**
1. Anchor the property at a declaration start: the start of the line (optional indentation),
   or right after `{`, `;` or a backtick. Put a left boundary on the property name, for
   example `(?<![\w-])`, so `Recolor` and `Border-color` cannot match on a suffix. The #7808
   fixtures still pass under this rule: `.btn { color: …`, `{ --brand: …`, `` `border-color: … ``,
   `background-color:#445566` after `;`/space inside the `{ }` block. If an inside-block
   declaration after a plain space is needed, allow it only when a `{` opens earlier on the
   line.
2. Apply the filter only to valid hex-colour digit counts (3, 4, 6, 8).
3. Add a regression test for every row in the table above, asserting `[4521]`, including
   `Border-color: #4521`.
4. Update the ADR amendment's "Number filter" bullet to state the anchor. Note the deviation
   from plan.md D1: the plan's regex was case-insensitive and unanchored, which is wider still.

## Non-blocking (fold if cheap, otherwise state the disposition)

- **N1 — `Fixes:#4521` (no space) is no longer a source issue.** The old
  `_CLOSING_KEYWORD_PATTERN` accepted it. The canonical detector requires whitespace before
  `#`, so the converged path drops it. This is a minor behaviour change: disclose it in the
  ADR, or accept it explicitly.
- **N2 — The commit-SHA rule fires on all-letter hex words.** Words like `` `defaced` `` or
  `` `deadbeef` `` within 16 characters demote a citation in `spec.md`
  (`Implements #4521, see `defaced` flag` → `pr_or_commit_ref`). Consider requiring at least
  one digit as well as one letter. Real abbreviated SHAs almost always have both.
- **N3 — Negation coverage is unchanged from before.** "Never fixes #N" and "does not close
  or fix #N" still read as closing statements. Inside the gating scope this only keeps the
  fail-safe default, so nothing to do now; it is recorded here for completeness.

## Anti-pattern checklist

1. Dead code: PASS. `issue_citations_in_line` and `_closing_keyword_leads_into` have
   production callers in `issue_reference_discovery.py`.
2. Synthetic fixture: PASS. The tests drive `discover_issue_references`, `classify_occurrence`
   and the source-issue derivation.
3. Silent empty return: FAIL, which is B1. `_matched_issue_number` returns `None` for
   non-colours. The other new returns are documented.
4. FR coverage: PASS for FR-001 and FR-003 to FR-007. FR-002 is covered, but the tests miss
   the false-positive side.
5. Frozen surface: PASS.
6. Locked decision: FAIL. NFR-002 is violated (B1).
7. Shared-file ownership: N/A, one WP.
8. Production fragility: PASS. No new `raise`.

Out-of-matrix test changes: none. The diff adds only
`tests/tasks/test_issue_matrix_over_matching.py` and modifies no existing test.
