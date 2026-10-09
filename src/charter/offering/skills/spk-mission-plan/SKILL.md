---
name: spk-mission-plan
description: "Operate the Spec Kitty plan phase: convert a completed spec into architecture, data flow, risks, and implementation strategy."
---

# spk-mission-plan

Use this skill when a mission has a spec and needs an implementation plan.

## Flow

1. Invoke `/spec-kitty.plan` against the active mission.
2. Ground the plan in the spec and existing repo architecture.
3. Make tradeoffs explicit: interfaces, data flow, migration needs, tests,
   rollout, and risks.
4. Route research gaps to `spk-mission-research`.
5. Route unclear mission type or workflow questions to `spk-mission-types`.
6. For non-trivial architecture, data/control flow, boundaries, migrations, or
   risky interactions, load `spk-practice-show-me` and use diagrams where they
   materially reduce prose.

## Guardrail

Do not let the plan silently change functional requirements. If the plan
discovers a spec issue, return to `spk-mission-specify`.
