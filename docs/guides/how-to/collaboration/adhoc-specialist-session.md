---
title: How to Start an Ad-Hoc Specialist Session
description: 'How to start an ad-hoc specialist session with Spec Kitty 3.2: How to Start an Ad-Hoc Specialist Session.'
doc_status: active
updated: '2026-09-30'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
---
# How to Start an Ad-Hoc Specialist Session

Use `spec-kitty dispatch "<request>"` to open a governed standalone Op without starting a full mission. Add `--profile <profile>` only when you intentionally want a specific specialist profile.

---

## When to use this

An ad-hoc specialist session is appropriate when:

- You have a question for a specific role ("how should I structure this API?")
- You want to explore an approach before committing to a feature
- You need a quick code review, a naming suggestion, or a small refactor
- You want to sanity-check a decision with a domain expert
- You are experimenting and do not yet know whether the result is worth keeping

It is **not** appropriate when:

- You need a tracked, reproducible workflow → use `/spec-kitty.specify` + the mission pipeline
- You want persistent state that advances work packages → use `/spec-kitty.implement`

---

## Starting a session

Open a governed standalone Op:

```
spec-kitty dispatch "How should I structure this API?" --profile architect
spec-kitty dispatch "Review this approach" --profile reviewer
spec-kitty dispatch "What prior art should I inspect?" --profile researcher
```

Spec Kitty opens an Op, loads governance context, and returns the selected profile. The host agent does the work under that context, then closes the Op with `spec-kitty profile-invocation complete`.

**Available profiles** (built-in): `architect`, `designer`, `implementer`, `planner`, `researcher`, `reviewer`, `curator`, `manager`

---

## What happens during a session

During the Op, the selected profile:

- Answers questions, proposes options, explains trade-offs, reviews code, or makes the requested change from its defined perspective
- May suggest involving another specialist ("this looks like it needs a Reviewer")
- Does **not** switch specialists automatically — any handoff requires your explicit approval
- Does **not** advance mission state, move work packages, or write to `kitty-specs/`

The system writes a local Op record in `kitty-ops/`. You stay in control throughout.

---

## Switching agents mid-session

To bring in a different perspective, invoke the command again with another profile:

```
spec-kitty dispatch "Review the architecture direction above." --profile reviewer
```

The previous agent's session context is checkpointed. The new specialist starts with the same conversation history available as background.

You can also switch based on an agent's own suggestion — but only if you agree:

> **Architect Alphonso:** This looks like it needs a security review. Would you like to bring in the Reviewer?
>
> **You:** Yes, switch to reviewer.

---

## Keeping or discarding the output

By default, standalone dispatch records what happened without advancing mission state. Nothing is committed or promoted automatically.

If the session produced something worth keeping — a decision, an approach, a pattern — you can request formalization:

> "Write down what we decided."
> "Formalize this approach."
> "Capture this as a recommendation."

The agent will produce a structured artifact. You then decide whether to commit it, file it as a doctrine candidate, or discard it.

**Nothing is promoted to doctrine without your explicit instruction.**

---

## The reasoning lifecycle

Ad-hoc sessions are the first layer in a three-layer model:

| Layer | Mode | Purpose |
|-------|------|---------|
| **Think** | Standalone governed Op | Explore, question, experiment |
| **Capture** | Formalization (on request) | Turn a finding into a repeatable artifact |
| **Execute** | Mission pipeline | Structured, tracked delivery |

A session never escalates to Capture or Execute automatically. You decide if and when to move forward.

---

## Example: quick architecture question

```
spec-kitty dispatch "I'm adding a new sync endpoint. Should it be synchronous or return a job ID?" --profile architect

[Architect Alphonso responds with trade-off analysis]

> Good point on the timeout risk. Let's go with job ID. Capture that decision.

[Architect Alphonso writes a short ADR-style note]
```

The decision note can then be committed to `architecture/` or used as input to the next `/spec-kitty.specify` run — at your discretion.

---

## Related

- [Slash Command Reference](../../../api/slash-commands.md)
- [AI Agent Architecture](../../../architecture/ai-agent-architecture.md)
- [Mission System](../../../architecture/mission-system.md)
