---
title: "spk-run-implement-review"
description: "Reference for the spk-run-implement-review skill: orchestrating the claim/implement/review loop across a mission's work packages."
doc_status: active
updated: '2026-07-21'
related:
- api/skills
---

# spk-run-implement-review

## What it does

Orchestrates the implement-review loop for one or more work packages (WPs) in
a mission: it dispatches implementation, reviews each WP independently, feeds
rejection feedback back into re-implementation, and continues until every WP
reaches a terminal outcome (`done`, `approved`, or correctly rejected). Under
the hood it drives `spk-run-next` to find the active WP/lane and
`spk-run-review-wp` for each review pass.

## When to reach for it

Use this skill any time you want the agent to run the claim → implement →
review cycle for you instead of driving `spec-kitty next` /
`spec-kitty agent action implement` by hand — for a single WP or a full
mission sprint across WP01…WP_N.

## Invocation

There is no CLI flag syntax for this skill — it is invoked by trigger phrase
inside your agent harness. The canonical `spk-run-implement-review` skill has
no declared `argument-hint`. Its detailed legacy alias,
`spec-kitty-implement-review`, documents the trigger phrases both names
respond to: "implement and review WPs", "run the implement-review loop",
"orchestrate WP implementation", "dispatch agents for WPs", "coordinate
implement and review", "sprint through WPs" — with `argument-hint:
"[WP_ID or 'all' for full feature sprint]"`.

## Sub-agent long-gate contract

`move-task --to for_review` runs a synchronous pre-review regression gate as
part of the transition. A dispatched implement/review sub-agent must poll
that command to completion rather than treating it as fire-and-forget. Pass
`--skip-pre-review-gate` to skip it for one invocation, or set
`SPEC_KITTY_SKIP_PRE_REVIEW_GATE` to disable it process-wide (the gate's own
opt-out name, #3980).

## What it does NOT do

Per the skill's own scope boundary, it does not handle the specify/plan/tasks
phases, setup or repair, glossary maintenance, or direct code editing by the
orchestrator itself — the orchestrator dispatches and monitors; it does not
implement.

## See also

For the full orchestration mechanics (agent dispatch by tier, parallel
sprints, arbiter mode after 3 rejection cycles, accept/merge sequencing), use
the detailed legacy alias `spec-kitty-implement-review` when it is available
in your agent's skill set.
