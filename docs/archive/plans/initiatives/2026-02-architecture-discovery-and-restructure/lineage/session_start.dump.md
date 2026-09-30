---
title: 1. What “Ad-Hoc Agent Profile Interaction” Actually Is
description: Raw lineage dump of the 2026-02-17 exploratory design brainstorm session opener, preserved as provenance for the architecture-discovery initiative.
doc_status: deprecated
updated: '2026-09-30'
---
2026-02-17:11:49

Mode: exploratory design brainstorm
Confidence: high
Scope: conceptual framing + structural risks + integration options

This is a strong instinct.

You’re sensing something important:

* Missions are **structured, outcome-oriented, reproducible**.
* Real work is often **messy, conversational, lateral, exploratory**.

If Spec Kitty only supports missions, it becomes a workflow machine.
If it only supports ad-hoc interaction, it becomes a chat wrapper.

The real value is in allowing both — without making them compete.

---

# 1. What “Ad-Hoc Agent Profile Interaction” Actually Is

Let’s define it clearly so we don’t drift.

Ad-hoc mode means:

* The user explicitly chooses an **agent profile** (Architect, QA, Writer, etc.)
* The interaction is **freeform**
* No mission step progression is enforced
* No recipe is required
* Outputs are optionally structured

It’s not workflow-driven.
It’s persona-driven.

This maps directly to your Doctrine stack concept of specialist agents.

---

# 2. Why This Is Valuable (Not Just “Nice to Have”)

### A. It mirrors real cognition

Before formal execution, people think:

* “Let me think like an architect.”
* “Let me sanity-check this as a reviewer.”
* “Let me stress-test this as QA.”

That mental gear shift is extremely powerful.

Formal missions are for production.
Ad-hoc mode is for thinking.

---

### B. It lowers friction

A mission implies:

* Structure
* Commitment
* File generation
* Event emission
* State transitions

Sometimes you just want:

> “Architect, what’s wrong with this idea?”

Ad-hoc makes Spec Kitty usable as a thinking partner, not just a delivery engine.

---

### C. It becomes a feeder into missions

Here’s the powerful part:

Ad-hoc interaction can generate:

* Refined spec
* Risk register
* Architecture outline
* Research findings

Then you transition into a mission with better clarity.

Ad-hoc is pre-mission thinking fuel.

---

# 3. The Core Architectural Question

Should ad-hoc mode be:

A) Separate from missions
B) A special “mission type”
C) A mode toggle inside the CLI

The cleanest design is:

> Ad-hoc mode is orthogonal to missions.

It lives parallel, not underneath.

---

# 4. A Clean Model That Won’t Rot

## Two execution modes

### 1) Structured Mode (Mission)

* Uses recipe
* Emits events
* Produces artifacts
* Progress tracked
* Boundaries enforced

### 2) Interactive Mode (Agent Profile Session)

* No recipe
* No required artifacts
* Optional structured output
* No step transitions
* Can later spawn a mission

Both share:

* Agent profiles
* Doctrine packs
* Templates
* Directives

That reuse is key.

---

# 5. What Makes Ad-Hoc Powerful (Not Gimmicky)

To avoid it becoming “just persona-flavored chat”, it needs:

### A. Named Agents with Identity

Each agent profile should include:

* Domain scope
* Thinking style
* Blind spots
* Typical output artifacts
* Preferred tactics
* Escalation suggestions (“this should become a mission”)

Now you have real specialists.

---

### B. Multi-Agent Switching

Ad-hoc becomes truly valuable when you can do:

```
> architect: critique this API
> qa: what edge cases?
> manager: what's the delivery risk?
```

That’s not gimmickry.
That’s structured perspective-shifting.

---

### C. Optional Transcript Capture

Here’s where it connects beautifully to your Doctrine:

Ad-hoc sessions can:

* Be ephemeral
* Or be promoted to a tracked artifact
* Or spawn a User Journey
* Or spawn a Mission

Now you’ve created a thinking → structuring → executing gradient.

---

# 6. The Real Risk (And It’s Subtle)

If you add ad-hoc mode carelessly:

Spec Kitty becomes:

* Chat wrapper
* Persona simulator
* Less opinionated
* Harder to reason about

The guardrail must be:

> Ad-hoc mode never mutates mission state directly.

It can suggest.
It can propose.
It can draft.
But it does not advance workflow automatically.

That boundary preserves integrity.

---

# 7. The Deep Opportunity

This is where it gets interesting.

If you combine:

* Ad-hoc agent sessions
* Structured missions
* Doctrine packs
* User Journeys
* Event logging

You could create:

### “Conversation-to-Structure” conversion

Example:

1. Architect session identifies system boundaries.
2. User types `/user-journey`
3. System pre-fills Actors, Boundaries, Events from conversation.
4. Mission recipe later consumes that.

That is real leverage.

---

# 8. Positioning This as a Contributor

Do not pitch it as:
“Let’s add chat mode.”

Pitch it as:

> “Introduce Specialist Agent Sessions to support early-stage reasoning and perspective shifting, without interfering with mission workflows.”

Frame it as:

* Cognitive scaffolding
* Pre-mission discovery
* Expert consultation layer

That’s a product evolution, not feature creep.

---

# 9. Design Sketch (Minimal)

CLI examples:

```
kitty agent architect
kitty agent qa
kitty agent researcher
```

Optional flags:

```
--pack audit-grade
--capture transcript
--promote-to mission
```

That’s enough to test viability.

---

# 10. The Hard Question

Before going further, I want to challenge you:

Is this primarily about:

A) Human cognition support
B) Demonstrating specialist AI agents
C) Enhancing product differentiation
D) Your deeper philosophy of perspective plurality

Your answer affects how deeply this should integrate into core.

Be honest here.
