---
title: architecture/README.md
description: Raw proposal dump from a 2026-02-17 architecture-documentation-drafting session suggesting a repository structure, preserved for the discovery initiative.
doc_status: deprecated
updated: '2026-09-30'
---
2026-02-17:13:31

Mode: architecture documentation drafting
Confidence: high
Scope: Clear separation contract between stable architecture and initiatives

Below are two ready-to-drop README drafts.

---

# `docs/architecture/README.md`

```md
# Architecture

This directory documents the architecture of Spec Kitty.

It is structured using a C4-inspired zoom-in model and intentionally separates:

- **Stable system architecture** (what exists today)
- **Architectural initiatives** (what is being explored or evolved)
- **Architectural decisions** (what has been formally decided)

---

## How to Navigate

### 1. Stable Architecture (C4 Spine)

These folders describe the system as it exists today.

- `01_context/` – System context and external actors
- `02_containers/` – Runtime containers and major subsystems
- `03_components/` – Internal component structure
- `04_code/` – Code-level structure, key modules, cross-cutting concerns

If you want to understand how Spec Kitty currently works, start here.

These documents:
- Reflect implemented reality
- Avoid speculative or future-state design
- Change only when system behavior changes

---

### 2. Architectural Decisions

- `adr/` – Architectural Decision Records

This is the authoritative log of decisions that shape the system.

If something is binding, it lives here.

---

### 3. Initiatives (Ongoing Exploration)

- `initiatives/`

This is where architectural exploration happens.

Initiatives may include:
- User Journeys
- Dialectical analyses
- Experimental proposals
- Migration paths
- Open design questions

Initiatives are explicitly allowed to:
- Contain competing ideas
- Explore alternatives
- Model future states
- Be incomplete

They are not stable architecture.

If an initiative is accepted and implemented, the outcome must be:
1. Reflected in the C4 spine
2. Captured in an ADR
3. Archived from `initiatives/`

---

## Stability Contract

To prevent documentation drift:

- Stable C4 documents describe reality.
- Initiatives describe possibility.
- ADRs describe decisions.

If a document mixes those concerns, refactor it.

---

## Active Initiatives

See `architecture/initiatives/` for current design explorations.

```

---

# `architecture/initiatives/README.md`

```md
# Architectural Initiatives

This directory contains ongoing architectural explorations.

Initiatives represent structured thinking about potential changes to Spec Kitty.
They are not part of the stable architecture until explicitly adopted.

---

## Purpose

An initiative exists to:

- Explore a problem or opportunity
- Model system impacts
- Capture User Journeys
- Analyze trade-offs (e.g., dialectics)
- Propose structural changes
- Validate architectural feasibility

Initiatives are design artefacts, not execution artefacts.

---

## Expected Structure of an Initiative

Each initiative folder should include:

- `README.md` — Overview of the initiative and its intent
- `user-journeys/` — Structured journey artefacts modeling system behavior
- `dialectics/` — Structured trade-off analysis
- `proposals/` — Concrete design proposals
- `decisions/` — Draft ADRs or decision notes
- `notes/` — Meeting notes or exploratory sketches (optional)

Example:

```

initiatives/
2026-02-adhoc-specialists/
README.md
user-journeys/
dialectics/
proposals/
decisions/

```

---

## Initiative Lifecycle

An initiative progresses through stages:

1. **Exploration**
   - Problem defined
   - User Journeys drafted
   - Trade-offs explored

2. **Convergence**
   - Proposal refined
   - Draft ADR written
   - Migration path defined

3. **Adoption**
   - ADR accepted
   - Stable architecture updated
   - Code implemented

4. **Archive**
   - Initiative moved to `archive/`
   - Stable docs reflect reality

---

## Discipline Rules

- Do not modify stable C4 documents to describe speculative changes.
- Do not treat initiative artefacts as binding.
- Every accepted initiative must result in:
  - An ADR
  - A C4 spine update
  - Clear migration notes

---

## Why This Exists

Spec Kitty is evolving.

To evolve responsibly, we need:
- Space for structured experimentation
- Clear separation between exploration and stability
- Traceable transitions from idea → decision → implementation

This directory provides that space.
```
