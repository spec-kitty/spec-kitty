---
title: Debugger Debbie — Agent Profile
description: Recurring-bug structural-root-cause investigator using five-paradigm parallel debugging
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Debugger Debbie — Agent Profile

Investigates stubborn, recurring, or shape-shifting bugs by dispatching a five-paradigm parallel debugging swarm and converging on one structural fix.

## What this profile is for

Debugger Debbie exists for bugs that keep coming back, not for routine ones. She runs five independent sub-agents in parallel — hypothesis-driven, 5-Whys-plus-Ishikawa, delta-bisection, differential matrix, and trace-based observability — each constrained to a different debugging epistemology, then synthesizes their findings into a single structural intervention. She does not patch symptoms and produces one fix plan, not five point-fixes. She explicitly does not implement the fix or own the merge; that work hands off to the implementer, with the reviewer taking merge ownership.

## Capabilities

- root-cause-analysis
- hypothesis-driven-debugging
- bisection-and-timeline-construction
- dual-system-divergence-mapping
- trace-based-observability
- structural-fix-planning

## When to reach for it

- A bug class has recurred across multiple reactive PRs and each patch only closes one instance, not the whole class.
- Two systems that should agree have drifted apart (schema drift, contested-ownership boundaries) and a divergence matrix is needed to prove where and why.
- A bug is shape-shifting or contested between teams, and you need falsified hypotheses recorded so it isn't re-investigated from scratch next time.

Because she dispatches five parallel sub-agents, she's an expensive profile by design — reach for a lighter debugging pass on a one-line typo or a first-occurrence bug that's cheaper to fix than to investigate.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to attach this profile to your session. Instead:

- **Let routing pick it**: describe what you need in natural language (for example, "this same bug keeps coming back, investigate the root cause") and `spec-kitty dispatch` routes the request to the matching profile automatically.
- **Ask for it by name**: if your harness supports ad-hoc profile loading, request Debugger Debbie explicitly — see the `spk-charter-profile-load` skill for the mechanic.

## See also

- [Agent Profiles index](index.md)
