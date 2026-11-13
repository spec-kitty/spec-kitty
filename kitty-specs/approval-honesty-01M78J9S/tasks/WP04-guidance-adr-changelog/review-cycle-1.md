---
affected_files: []
cycle_number: 1
mission_slug: approval-honesty-01M78J9S
reproduction_command:
reviewed_at: '2026-11-13T10:08:00Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP04
---

# WP04 review feedback, cycle 1 (reviewer claude::reviewer-renata)

Verdict: changes requested. Everything else checks out: the hint, the skill, the red test (4 failed on the parent), the changelog checks, the decision IDs and the regression runs. Four statements in the shipped prose do not match the code. Two of them block approval.

## Blocking

1. **"Jane Doe now refuses" is not true in general.**
   - Where: ADR `2026-10-04-5` Amendment 2026-11-12, Consequences, first bullet ("A name such as `"Jane Doe"` now refuses"), and `docs/changelog/unreleased/7569-approval-honesty.upgrade-notes.md` ("a free-text name such as `"Jane Doe"` now refuses").
   - What the code does: `--reviewer` is never checked for its form. It refuses only when another identity holds the review claim (`_claimant_mismatch`, `tasks_transition_core.py`). Probe: a WP in `for_review` with no claim, then `move-task WP01 --to approved --reviewer "Jane Doe" --note ok --json`. It exits 0 and records `Jane Doe` as the actor, `evidence.review.reviewer` and the `review_result` reviewer (the auto-walk claims the review as Jane Doe; residual (b)).
   - Fix: say that a `--reviewer` (free text included) that is not the claimant refuses with `APPROVER_NOT_CLAIMANT`, and that the value's form is not validated. Name the auto-walk case or point to residual (b).

2. **CLAUDE.md/AGENTS.md still describes the old behaviour as current.**
   - Where: the approval-stamp paragraph (`AGENTS.md:566`, "Approved claim is bounded by the approval stamp (#5668)"), in its #5721 residual.
   - What it says: "the synthetic `auto-approval:` token, or the `review-cycle://` pointer the approval's own auto-committed review-cycle artifact yields) and a reviewer name (auto-detected from `git config user.name`)".
   - What the code does since this Mission: `resolve_reviewer_of_record` never reads the git user and mints no token, and a forced move writes no cycle.
   - Fix: reword that clause in the past tense ("before #7569 …"), or replace it with a pointer to Amendment 2026-11-12. Keep the rule itself: a reference and a reviewer name never count.

## Non-blocking (please fix in the same pass)

3. **The claimant rule is not the same as consolidation's.**
   - Where: the ADR amendment's "The review claimant" bullet calls `latest_review_claim_identity` "the same rule as consolidation's `approved_bound._entered_review_by_claim`".
   - What the code does: `_entered_review_by_claim` (`approved_bound.py:239-247`) checks only `not entry.force`. It does not exclude `migration:` actors or the `user` placeholder.
   - Fix: say the rule is built on that one and is stricter.

4. **The no-alias sentence is ambiguous.**
   - Where: the ADR amendment's Shape bullet ends with "There is no `SINGLE_BRANCH_*` alias".
   - The problem: that sentence comes right after "like `REVIEW_NOT_INDEPENDENT`", and `REVIEW_NOT_INDEPENDENT` does have an alias on `single_branch` (`SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT`, `_mt_review_code`). The same applies to "refuses with the existing `REVIEW_NOT_INDEPENDENT`" in the reviewer-of-record bullet.
   - Fix: say that the four new codes have no alias.

## Verified as accurate

- The claimant rule (newest `in_review` entry only).
- The `APPROVER_NOT_CLAIMANT` `--json` diagnostic, with `code`, `review_claimant` and `requesting_agent`.
- The `REVIEW_CYCLE_CITATION_MISSING` `--json` shape (`{"error": "<CODE>: ..."}` with no `code` field).
- A forced move writes no cycle and records `force-override`.
- `approved -> done` carries the approval's reviewer and reference in `evidence.review` and refuses `REVIEW_NOT_INDEPENDENT` without `--agent`.
- The owned envelope's `error.code`.

## `src/kernel/__init__.py`

The docstring-only edit is accepted, with no version bump; record it in the PR.
