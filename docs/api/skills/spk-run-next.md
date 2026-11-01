---
title: "spk-run-next"
description: "Reference for the spk-run-next skill: driving the canonical spec-kitty next control loop and routing its decision kinds."
doc_status: active
updated: '2026-07-21T00:00:00Z'
related:
  - docs/api/skills/index.md
kind: Reference
---

# spk-run-next

## What it does

Drives the canonical `spec-kitty next --mission <handle>` control loop for
mission advancement and routes the returned decision — `query`, `step`,
`blocked`, `decision_required`, or `terminal` — to the correct next action.

## When to reach for it

Use it whenever you want to advance an active mission, ask what to do next,
or recover from a runtime decision. It is the everyday entry point for
driving a mission forward one step at a time from inside your agent harness.

## Invocation

- Query state: `spec-kitty next --mission <handle> --json`
- Advance state: `spec-kitty next --agent <name> --mission <handle> --result <success|failed|blocked>`

The skill's own frontmatter declares no fixed trigger phrase; its detailed
legacy alias documents the natural-language requests that route here — "run
the next step," "what should runtime do next," "advance the mission," "what
is the next task," "continue the workflow," "what step comes next."

## Flow

1. `query` — inspect only; do not execute a prompt or mark a result.
2. `step` — execute the generated prompt file.
3. `decision_required` — answer with `--answer`, `--result`, `--agent`, and
   `--decision-id` when multiple decisions are pending.
4. `blocked` — fix guard failures before retrying.
5. `terminal` — route to `spk-gate-accept`.

## Legacy alias

For detailed runtime semantics — the decision algorithm, WP iteration logic,
guard primitives, the prompt-file contract, and known issues — use
`spec-kitty-runtime-next` when it is available in your agent's skill set.
