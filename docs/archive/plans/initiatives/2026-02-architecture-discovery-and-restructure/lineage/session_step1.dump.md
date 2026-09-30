---
title: 1. Specialist Handoff as a First-Class Mechanism
description: Raw lineage dump of a 2026-02-17 deep architectural-synthesis brainstorm step, preserved as provenance for the architecture-discovery initiative.
doc_status: deprecated
updated: '2026-09-30'
---
> I was also thinking we can have the specialist agents suggest follow-ups / handoffs to other specialists and guide the user forwards, keeping the human in charge. I see this as a powerfull approach to maintain consistency in doctrine between both modes, and a way to enable "quick tasks", such as bugfixing, questions, brainstorming, ci updates, small refactors. An additional use case would be "process refinement", where a user interactively guides the kitty agent crew through a novel approach, then wraps up with "now, formalize this approach, so it is repeatable"

2026-02-17:12:04

Mode: deep architectural synthesis
Confidence: high
Scope: validating concept, identifying design invariants, surfacing risks

You’re circling something genuinely powerful now.

This is no longer “chat mode.”

This becomes:

> A guided, doctrine-consistent specialist collaboration layer
> that can evolve ad-hoc reasoning into structured, repeatable process.

That’s a serious architectural feature.

Let’s break it down cleanly.

---

# 1. Specialist Handoff as a First-Class Mechanism

The key innovation is not “multiple agents.”

It’s:

> Agents suggesting structured handoffs — without taking control away from the human.

That preserves:

* Human in charge
* Doctrine continuity
* Perspective plurality
* Structured escalation

Example:

```
Architect:
"I see API boundary risk. I suggest we consult QA before finalizing."

QA:
"I recommend an edge-case review pass."

Manager:
"This impacts delivery timeline."
```

But critically:

* The system suggests.
* The human approves.
* Nothing auto-executes.

That’s governance-aligned.

---

# 2. Why This Solves Real Workflow Gaps

Your missions are excellent for:

* New feature dev
* Research flows
* Document creation

But real work includes:

* “Quick fix this null pointer.”
* “Can you review this PR?”
* “Why is CI failing?”
* “Help me brainstorm naming.”
* “Refactor this test suite.”

These don’t justify spinning up a full mission.

Ad-hoc specialist mode fills that gap.

---

# 3. Doctrine Consistency Across Modes

This is the critical architectural win.

If:

* Both mission steps
* And ad-hoc sessions

Pull from the same:

* Agent profiles
* Directives
* Tactics
* Templates
* Strategy packs

Then you’ve avoided the split-brain problem.

Doctrine becomes the spine.

Mission mode = structured orchestration
Ad-hoc mode = perspective-driven reasoning

Same doctrine engine underneath.

That’s clean.

---

# 4. The Process Refinement Use Case (This Is the Big One)

This is not minor.

You’re proposing:

1. User experiments interactively.
2. Specialists discuss.
3. A novel workflow emerges.
4. User says:

   > “Now formalize this so it’s repeatable.”

That means:

* Extract steps
* Identify boundaries
* Identify artifacts
* Identify events
* Identify doctrine pack
* Create a mission recipe
* Possibly create a user journey

You’ve just enabled:

> Emergent workflow crystallization.

That’s extremely aligned with your philosophy.

It turns experimentation into product evolution.

---

# 5. The Critical Architectural Guardrails

If you build this, you must enforce three invariants.

---

## Invariant 1: No Silent Transitions

Specialists can suggest:

* “Consult QA”
* “Create mission”
* “Formalize process”

But never auto-switch.

Human must confirm.

---

## Invariant 2: Clear Mode Separation

Ad-hoc mode:

* No persistent mission state
* No automatic artifact mutation
* Optional capture

Mission mode:

* Structured
* Stateful
* Event-driven

Blurring these will cause chaos.

---

## Invariant 3: Explicit Escalation Path

There must be a clear command like:

```
/formalize
/promote-to-mission
/user-journey
```

And the system translates conversation into structure.

This is where your `/user-journey` command becomes extremely powerful.

---

# 6. The Meta-Level Opportunity

If done right, you get a three-phase lifecycle:

### Phase 1 – Think (Ad-Hoc Specialist Mode)

Unstructured, exploratory, perspective shifting.

### Phase 2 – Structure (Formalization)

Generate:

* User Journey
* Mission Recipe
* Step Draft
* Doctrine Pack

### Phase 3 – Execute (Mission Mode)

Structured, event-driven, reproducible.

This is not feature creep.

This is lifecycle support.

---

# 7. The Real Design Question Now

Do specialists:

A) Only respond when invoked explicitly
B) Or can they suggest passive interjections
C) Or can they operate in collaborative swarm mode

Be careful here.

Swarm mode sounds attractive, but:

* It increases cognitive load.
* It can overwhelm users.
* It may conflict with human-in-charge philosophy.

My bias:

Start with explicit invocation and suggestion-only handoffs.

No swarm.

---

# 8. Quick Task Enablement

You mentioned:

* Bugfix
* CI update
* Small refactor
* Brainstorming

These become:

Micro-structured sessions with specialist discipline.

This prevents “chat sloppiness.”

Even quick tasks benefit from:

* QA mindset
* Reviewer mindset
* Architect boundary awareness

That’s doctrine scaling down.

---

# 9. Where This Could Go Wrong

Three subtle failure modes:

### 1. Persona Gimmickry

If profiles are shallow, it feels theatrical.

Profiles must encode:

* Trade-off biases
* Blind spots
* Decision posture
* Escalation patterns

---

### 2. Over-Nudging

If specialists constantly suggest handoffs, it becomes annoying.

There must be a threshold rule:
Only suggest when:

* Risk increases
* Scope expands
* Boundary crosses

---

### 3. Infinite Conversation

You need termination signals:

* “Ready for execution?”
* “Shall we formalize?”
* “Is this exploratory only?”

Otherwise it drifts.

---

# 10. Strategic Framing for Spec Kitty

Pitch this as:

> Specialist Agent Sessions for Structured Reasoning and Workflow Discovery.

Not chat.
Not AI personas.
Not multi-agent gimmicks.

Structured reasoning.

That resonates.

---

# 11. Now I’ll Push You

This direction meaningfully increases product complexity.

So ask yourself:

Is Spec Kitty:

* A workflow runner?
* Or a structured reasoning environment?

If it becomes both, you need a clean internal architecture.

Are you willing to defend that complexity publicly in the repo?

If yes — this is a strong direction.

If not — scope it tightly.

---

If you want, next we can:

* Draft a concrete CLI spec for specialist sessions
* Define agent profile schema
* Or simulate a real “bugfix” ad-hoc flow with handoffs to test viability

Your call.

> To clarify: User Journeys are a design artefact, to be used for myself and other contributors to reason about the spec kitty architectural direction. They are not a first-tier SK execution concept. I thaught you the template so we can refine the ideas in this brainstorm session and capture them as UJs

2026-02-17:12:18

Mode: recalibration + alignment
Confidence: high
Scope: clarifying conceptual layers before we formalize anything

Good clarification. That changes the framing.

So:

* **User Journeys are architectural reasoning artefacts**
* They are not runtime concepts
* They are not exposed to end users
* They are for contributor-level design thinking

That’s important.

We’re not designing CLI features yet.
We’re designing internal architectural direction.

Perfect.

---

Now, given that, your “ad-hoc specialist interaction” idea is not a feature proposal.

It’s an **architectural capability exploration**.

So let’s reason at the right level.

---

# Step 1 — What Architectural Question Are We Actually Exploring?

It is not:

> “Should we add chat?”

It is:

> “Should Spec Kitty support two modes of structured reasoning: recipe-driven and profile-driven?”

That’s a product identity question.

---

# Step 2 — Restating the Proposal Precisely

Spec Kitty currently centers around:

* Mission (structured recipe)
* Deterministic progression
* Clear state transitions

You are proposing adding:

* Specialist agent sessions
* Human-approved handoffs
* Conversational evolution
* Optional formalization into mission recipes

This introduces a second reasoning axis:

* Structural axis (mission recipes)
* Perspective axis (specialist viewpoints)

That’s cleanly conceptual.

---

# Step 3 — The Architectural Tension

There is a core tension here:

Spec Kitty today is deterministic and step-oriented.

Ad-hoc specialist mode introduces:

* Non-linear flow
* Emergent structure
* Deferred formalization

The question is:

Can Spec Kitty support both without eroding its identity?

That’s what we should model in a User Journey.

---

# Step 4 — The Real Value Hypothesis

Your hypothesis is:

1. Specialist sessions improve doctrine consistency even in small tasks.
2. They provide quick-task support without full mission overhead.
3. They enable emergent workflow crystallization.
4. They preserve Human-In-Charge.
5. They strengthen consistency between structured and unstructured modes.

That’s a serious hypothesis.

It deserves architectural modeling.

---

# Step 5 — Yes, This Is Exactly the Right Use Case for a User Journey

Because this involves:

* Human
* LLM specialist
* Possibly mission engine
* Possibly telemetry
* Possibly artifact promotion
* Multiple boundaries

It crosses system boundaries.
It involves coordination rules.
It has observability implications.
It affects governance posture.

That is textbook User Journey material.

---

# Step 6 — What Journey(s) Should We Capture?

We should not lump everything into one journey.

There are at least three distinct architectural explorations here:

1. **Quick Task Specialist Interaction**

   * Human invokes specialist
   * Specialist suggests refinement
   * Possibly suggests handoff
   * Human resolves task
   * No mission created

2. **Specialist → Mission Promotion**

   * Interactive reasoning
   * Decision to formalize
   * Recipe created
   * Mission executed

3. **Process Refinement Loop**

   * Interactive experimentation
   * Specialist-guided iteration
   * Formalization of repeatable approach
   * New mission or step definition created

Each one stresses the system differently.

We should capture them separately.

---

# Step 7 — Important Clarifying Question Before We Write a UJ

In this architecture:

Is ad-hoc interaction:

A) Stateless and ephemeral
B) Session-based but not persisted
C) Persisted and observable like missions
D) First-class event emitting

This matters because it determines whether:

* Observability Guarantees must be as strong as mission mode
* Coordination posture must exist
* Event contracts are required

Be precise here.

---

# Step 8 — Strategic Recommendation

Before writing a UJ, decide:

Is the goal:

* Lightweight reasoning layer
* Or eventual parity with mission governance
* Or a transitional layer only

Because each produces a different architecture.

---

Now I suggest this next step:

Let’s capture **User Journey: Ad-Hoc Specialist Session (Quick Task)** first.

Keep it constrained.
No mission promotion yet.
No formalization yet.

We reason about:

* Boundaries
* Actors
* Coordination
* Observability
* Promotion boundary

Then we evaluate architectural strain.

If you agree, say:

`/user-journey Ad-Hoc Specialist Session (Quick Task)`

And I’ll generate it and we’ll refine it together at contributor-level depth.

> Answer to your core question: the ad-hoc agent interactions are session based by default. Events and "memory-dump files" are emitted as usual, but no specific tracing exists. Formalization happens when the user instructs the system to do so "write down what we did", "formalize", ...
