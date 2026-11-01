---
title: "Skill: spk-gate-mission-review"
description: Post-merge Spec Kitty mission review — spec-to-code fidelity, FR coverage, drift, risk, and final verdict.
doc_status: active
updated: '2026-07-21'
related:
- api/skills
---
# spk-gate-mission-review

Runs a post-merge review of a fully merged mission: every work package is
`done`/`approved` and the feature branch has landed. The skill traces each
functional requirement from spec to test to code, checks for drift against
locked decisions and non-goals, hunts for risks the per-WP reviews missed
(dead code, silent failure paths, cross-WP integration gaps), runs a security
pass, and produces a structured report ending in a `PASS` / `PASS WITH NOTES`
/ `FAIL` verdict. It does not fix anything it finds — it documents findings
with cited evidence for a human or a follow-up mission to act on.

## When to reach for it

- After `spec-kitty merge --mission <slug>` completes and all WPs show `done`
- Before tagging a release that depends on the mission's changes
- When a downstream team needs sign-off on spec-to-code fidelity
- When a WP review looks too narrow and cross-WP holes are suspected

This is not the pre-merge acceptance gate (`spec-kitty accept`) and it is not
per-WP review during implementation — use `spk-run-review-wp`
for that, and [spk-run-implement-review](spk-run-implement-review.md) for
orchestrating the implement/review loop itself.

## Invoking it

Trigger phrases include "review the merged mission", "post-merge mission
review", "verify the completed mission", "is this mission releasable", and
"final review before tagging" — the agent matches these against the skill's
description and loads it automatically; there is no separate CLI command to
run it. `spk-gate-mission-review` is the current name; detailed review
mechanics live under its legacy alias, `spec-kitty-mission-review`, which the
skill defers to for the full step-by-step procedure.
