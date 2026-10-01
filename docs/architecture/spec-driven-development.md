---
title: Spec-Driven Development Explained
description: "Why Spec Kitty writes a full specification before any code: the spec becomes the executable contract that drives specify, plan, and tasks and enables parallel work packages."
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/architecture/execution-lanes.md
- docs/architecture/kanban-workflow.md
- docs/architecture/mission-system.md
---
# Spec-Driven Development Explained

Spec-driven development is the methodology at the heart of Spec Kitty. This document explains what it is, why it matters, and when to use it.

## What is Spec-Driven Development?

Spec-driven development is an approach where you write a detailed specification *before* writing any code. The specification becomes the source of truth that guides implementation.

**Traditional development**:
1. Developer has an idea
2. Developer writes code
3. Developer writes documentation (maybe)
4. Requirements drift as understanding evolves

**Spec-driven development**:
1. Developer writes specification
2. Specification is reviewed and refined
3. Implementation follows specification
4. Documentation already exists (the spec)

The key insight: AI agents need clear, unambiguous requirements to produce quality output. Specifications provide that clarity.

## Why Spec-First?

### AI Agents Need Clear Requirements

Human developers can fill in gaps, ask clarifying questions mid-task, and use intuition. AI agents work better with explicit requirements:

- **Ambiguity causes inconsistency**: "Make the button look better" produces different results each time
- **Specifications reduce rework**: "Button: 44px height, #007AFF background, 12px border-radius" produces consistent results
- **Context is bounded**: AI agents work within context windows; specifications provide focused context

### Specifications Become Executable

In Spec Kitty, specifications aren't just documentation—they drive the workflow:

- `/spec-kitty.specify` creates the spec
- `/spec-kitty.plan` creates implementation plan from the spec
- `/spec-kitty.tasks` generates work packages from the plan
- Each work package references back to the spec

The specification is the contract that all agents follow.

### Reduces Rework and Misunderstanding

When multiple agents (or humans) work on a feature:
- Without spec: Each person interprets requirements differently
- With spec: Everyone references the same document

This becomes critical in parallel development where multiple AI agents implement different work packages simultaneously.

## The Spec-Kitty Workflow

![Spec Kitty workflow: planning, implementation, and review phases](../assets/images/spec-driven-development-flow.svg)

Each phase produces artifacts that feed into the next phase.

Planning location and branch intent are separate. The planning phase runs in the repository root checkout, while the mission target branch can be the current branch or an explicit branch chosen during mission creation.

## How It Differs from Traditional Development

| Aspect | Traditional | Spec-Driven |
|--------|-------------|-------------|
| **Requirements** | Often implicit, evolve during coding | Explicit, written upfront |
| **Documentation** | Written after implementation (often skipped) | Built into the process |
| **Parallelization** | Difficult without clear boundaries | Natural work package boundaries |
| **AI-assisted development** | Agents need context each time | Agents reference specifications |
| **Rework** | Common when requirements misunderstood | Reduced by upfront clarity |
| **Scope creep** | Easy to add "just one more thing" | Spec defines boundaries |

## When to Use Spec-Driven Development

### Good Fit

**Features with clear boundaries**:
- "Add user authentication with OAuth"
- "Implement shopping cart functionality"
- "Create admin dashboard"

**Multi-agent or team projects**:
- Multiple AI agents working in parallel
- Human + AI collaboration
- Distributed teams

**Non-trivial features**:
- More than one work package
- Requires architectural decisions
- Has integration points with existing code

### Poor Fit

**Exploratory work**:
- Prototyping where requirements are unknown
- Research tasks (use Deep Research Kitty instead)
- "Try different approaches and see what works"

**Simple one-off changes**:
- Fix a typo
- Update a single constant
- Minor refactoring

**Emergency fixes**:
- Production is down
- Security patch needed immediately
- (Write the spec after, for documentation)

## The Three Phases in Detail

### Phase 1: Specification

The specification answers: **What are we building and why?**

A good spec includes:
- **Problem statement**: What problem does this solve?
- **User stories**: Who benefits and how?
- **Requirements**: What must the solution do?
- **Non-requirements**: What is explicitly out of scope?
- **Success criteria**: How do we know we're done?

### Phase 2: Planning

The plan answers: **How will we build it?**

A good plan includes:
- **Technical approach**: Architecture and design decisions
- **work package breakdown**: Discrete units of work
- **Dependencies**: What must be built first?
- **Risks and mitigations**: What could go wrong?

### Phase 3: Implementation

Implementation answers: **Building the actual solution.**

Each work package:
- References the spec and plan
- Has clear acceptance criteria
- Can be implemented independently
- Gets reviewed against the spec

## Why Specifications Enable Parallelization

Traditional development often becomes serial:
1. Developer A implements feature foundation
2. Developer B waits for A to finish
3. Developer B implements dependent feature
4. (Repeat)

Spec-driven development with Spec Kitty enables parallel work:
1. Specification defines all work packages upfront
2. Dependencies between WPs are explicit
3. Independent WPs can be implemented simultaneously
4. Each agent has clear scope boundaries

**Example**: A feature with 5 work packages:
- Sequential: 5 time units
- With Spec Kitty (2 parallel, 3 sequential): 3 time units

## See Also

- [Execution Lanes](execution-lanes.md) - How isolation enables parallelization
- [Kanban Workflow](kanban-workflow.md) - How work moves through lanes
- [Mission System](mission-system.md) - Different workflows for different needs

---

*This document explains the "why" behind spec-driven development. For "how" to create specifications, see the tutorials and how-to guides.*

## Try It

- [Claude Code Integration](../guides/tutorials/claude-code-integration.md)
- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## How-To Guides

- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)

## Reference

- [CLI Commands](../api/cli-commands.md)
- [Slash Commands](../api/slash-commands.md)
