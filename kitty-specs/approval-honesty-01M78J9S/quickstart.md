---
type: how-to
updated: 2026-11-12
audience: reviewers verifying the mission by hand
---

# Quickstart: verify approval honesty

In a scratch Mission whose repository has a distinctive `git config user.name` (for example
"Pat Example"):

1. Claim the review: `spec-kitty agent action review WP01 --mission <m> --agent claude:sonnet:reviewer-renata`.
2. Approve without `--agent`: `spec-kitty agent tasks move-task WP01 --to approved --mission <m>`.
3. Read the last event: `tail -1 kitty-specs/<m>/status.events.jsonl`. "Pat Example" and
   `auto-approval:` must not appear anywhere in it. `actor`, `review_result.reviewer`,
   `evidence.review.reviewer` and `policy_metadata.tool` all name `reviewer-renata`.
4. Confirm the reference: it is `review-cycle://…/review-cycle-1.md`, and that file exists.
5. Non-claimant: repeat on WP02 with `--agent claude:sonnet:supervisor`. Expect exit 1 with
   `APPROVER_NOT_CLAIMANT` and the event log unchanged.
6. Missing citation: approve WP03 with `--note "cycle 4 APPROVE"` while only cycle 1 exists. Expect
   `REVIEW_CYCLE_CITATION_MISSING`.
7. Adoption: after claiming WP04, write a valid `review-cycle-1.md` attributed to the claimant,
   then approve. Expect no `review-cycle-2.md`.
