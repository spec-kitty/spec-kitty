---
name: spk-gate-mission-review
description: "Run post-merge Spec Kitty mission review for spec-to-code fidelity, FR coverage, drift, risk, and final verdict."
---

# spk-gate-mission-review

Use this skill after a mission has merged or when the user asks for a mission
review.

## Flow

1. Compare spec, plan, tasks, WPs, reviews, and merged code.
2. Trace functional requirements to implementation evidence.
3. Identify drift, missing tests, security concerns, and follow-up issues.
4. Produce a final verdict and record follow-ups.

Save the review as `kitty-specs/<slug>/mission-review.md`. The path
`kitty-specs/<slug>/mission-review-report.md` belongs to the machine report
`spec-kitty review` writes; that command refuses to overwrite any other file
there (`MISSION_REVIEW_REPORT_PATH_OCCUPIED`).

## Legacy Alias

For detailed review mechanics, use `spec-kitty-mission-review` when available.
