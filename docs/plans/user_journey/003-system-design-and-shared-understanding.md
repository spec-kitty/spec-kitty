---
title: 'User Journey: System Design & Shared Understanding'
description: 'User journey for system design and shared understanding: how a team builds shared design context through Spec Kitty, in a field-table record.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/plans/user_journey/001-project-onboarding-bootstrap.md
---
# User Journey: System Design & Shared Understanding

> **Historical (2.x-era vision snapshot).** Written in early 2026 and not re-validated against the 4.x CLI; some steps have since shipped in a different form, and older "feature" wording means *mission*. Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

| Field | Value |
|---|---|
| **Status** | DRAFT |
| **Implementation Status** | VISION (target-state proposal; not current runtime reality) |
| **Date** | 2026-02-15 |
| **Primary Contexts** | Architecture, Domain Modeling, Shared Understanding |
| **Supporting Contexts** | Governance, Feature Specification |
| **Related Spec / ADR** | N/A (proposed — `/spec-kitty.design` command) |

---

## Scenario

A team has bootstrapped their project — vision and charter are established.
They now need to build shared understanding of the system before diving into
feature work: who the stakeholders are, what language the domain uses, how the
system is structured, and what architectural decisions have been made.

Without this step, feature specifications drift from intent. Different agents
and contributors use different terms for the same concept. Architectural decisions
are made implicitly and forgotten. Stakeholder needs are assumed rather than
captured.

The `/spec-kitty.design` command addresses this by guiding a structured design
session that produces living architecture artifacts — not a one-shot document,
but a set of continuously-referenced resources that downstream commands
(`/spec-kitty.specify`, `/spec-kitty.plan`, `/spec-kitty.review`) consume.

---

## Actors

| # | Actor | Type | Persona | Role in Journey |
|---|-------|------|---------|-----------------|
| 1 | Architect | `human` | [System Architect](../../context/audience/internal/system-architect.md) | Provides domain knowledge, names concepts, validates boundaries, makes trade-off decisions |
| 2 | AI Agent | `llm` | [AI Collaboration Agent](../../context/audience/internal/ai-collaboration-agent.md) | Conducts structured discovery, extracts terminology, researches patterns, produces artifacts, checks consistency |
| 3 | Spec-Kitty CLI | `system` | [Spec Kitty CLI Runtime](../../context/audience/internal/spec-kitty-cli-runtime.md) | Orchestrates phases, manages artifact lifecycle, links design outputs to downstream commands |
| 4 | Codebase | `system` | [Project Codebase](../../context/audience/internal/project-codebase.md) | Provides evidence for alignment checks — existing naming, module structure, implicit patterns |

---

## Preconditions

1. Project has been initialized with `spec-kitty init`.
2. Bootstrap completed — `.kittify/memory/vision.md` exists with project purpose and scope.
3. Charter exists — `.kittify/charter/charter.md` with technical standards and governance.
4. At least one supported AI agent is configured.
5. Git repository is initialized.

---

## Journey Map

| Phase | Actor(s) | System | Key Events |
|-------|----------|--------|------------|
| 1. Stakeholder Discovery | Architect ↔ AI Agent | AI interviews: who uses, operates, develops, funds, is affected by this system? | `DesignSessionStarted`, `StakeholderIdentified` |
| 2. Language Harvesting | AI Agent ↔ Codebase | AI scans code, docs, vision, charter for domain terms; presents candidate glossary | `TerminologyExtracted`, `GlossaryDraftCreated` |
| 3. Glossary Refinement | Architect ↔ AI Agent | Architect validates, corrects, and enriches terms; AI detects conflicts and ambiguities | `TermDefined`, `AmbiguityDetected`, `BoundaryHinted` |
| 4. Context Mapping | Architect ↔ AI Agent | Based on glossary conflicts, AI proposes bounded context boundaries; architect validates | `ContextBoundaryProposed`, `ContextMapCreated` |
| 5. User Journey Capture | Architect ↔ AI Agent | AI interviews for key cross-boundary flows; produces journey artifacts | `JourneyCaptured` |
| 6. Constraint & NFR Capture | Architect ↔ AI Agent | AI interviews: quality attributes, hard constraints, performance expectations | `ConstraintCaptured`, `QualityAttributeDefined` |
| 7. Decision Formalization | Architect ↔ AI Agent | AI proposes ADRs for significant decisions surfaced during Phases 1-6; architect confirms | `ArchitectureDecisionRecorded` |
| 8. Artifact Generation | AI Agent ↔ CLI | CLI commits all design artifacts; links to vision and charter | `DesignArtifactsGenerated`, `DesignSessionCompleted` |
| 9. Downstream Integration | — | Subsequent spec-kitty commands reference design artifacts for consistency | `FeatureSpecAligned` |

---

## Coordination Rules

**Default posture**: Gated (design decisions require explicit human confirmation)

1. **Language-first**: Phases 2-3 (glossary) run before Phase 4 (context mapping) — you cannot draw boundaries without shared vocabulary.
2. **Glossary is never "done"**: Phase 3 produces a living artifact. Subsequent `/spec-kitty.specify` and `/spec-kitty.review` commands may add terms, flag drift, or propose refinements.
3. **Ambiguity is a feature, not a bug**: When the AI detects the same term used differently (e.g., "Order" meaning different things in different modules), this is surfaced as a bounded context hint, not forced to resolution.
4. **Every decision requires at least one alternative**: Per Traceable Decisions directive — "we chose X" is insufficient; "we chose X over Y because..." is required.
5. **The architect has final authority**: Human In Charge — the AI proposes terminology, boundaries, and decisions; the human disposes.
6. **Existing ADRs are checked before new decisions**: If prior ADRs exist in `docs/adr/2.x/`, the AI loads them and flags conflicts.
7. **Codebase scan is automatic**: The AI examines existing code for naming patterns whether or not the architect asks — findings are presented for review.
8. **NFRs must be measurable**: "The system should be fast" is rejected; "p95 < 200ms under 1000 concurrent users" is accepted.

---

## Responsibilities

### Spec-Kitty CLI (Local Runtime)

1. Detect existing design artifacts and offer update vs. create mode.
2. Orchestrate phase progression (gated — wait for human confirmation per phase).
3. Store outputs in `architecture/` directory at repository root.
4. Manage glossary lifecycle (create, update, validate against code).
5. Commit artifacts to the current branch with structured commit messages.
6. Ensure downstream commands (`plan`, `specify`, `review`) reference design artifacts.

### AI Agent (LLM Context)

1. Conduct phase-by-phase discovery interview with structured prompts.
2. Scan codebase for domain terms: variable names, class names, comments, existing docs.
3. Detect terminology conflicts (same word, different meanings across modules).
4. Present bounded context hypotheses based on linguistic analysis.
5. Generate stakeholder personas using `stakeholder-persona-template.md`.
6. Generate user journey artifacts using `user-journey-template.md`.
7. Draft ADRs with alternatives and rationale per Traceable Decisions directive.
8. Cross-reference proposed decisions against existing ADRs.
9. Apply Locality of Change — verify proposed structure isn't over-engineered for the problem scale.

---

## Scope: MVP

### In Scope

1. **Stakeholder discovery**:
   - Identify stakeholder categories (users, operators, developers, business owners)
   - Capture lightweight personas inline (name, type, what they care about)
   - Optional: generate full persona files using `stakeholder-persona-template.md`

2. **Living glossary**:
   - Harvest terms from codebase (class names, method names, comments, existing docs)
   - Harvest terms from vision.md and charter.md
   - Present candidate glossary for architect validation
   - Detect conflicts: same term with different implicit meanings
   - Flag missing terms: concepts in code without explicit vocabulary
   - Store as `glossary/README.md` (or update existing)
   - Tag terms with bounded context affinity where clear

3. **Context mapping**:
   - Propose bounded context boundaries from glossary conflicts
   - Lightweight context map (which terms belong to which context)
   - Integration patterns between contexts (ACL, shared kernel, published language)
   - Not a full strategic DDD exercise — proportional to project scale

4. **User journeys**:
   - Capture 1-3 key cross-boundary flows
   - Use `user-journey-template.md` format (actors, phases, events, coordination rules)
   - Link to stakeholder personas
   - Store in `docs/plans/user_journey/`

5. **Constraint & NFR capture**:
   - Hard constraints (technology locks, team size, compliance)
   - Quality attributes with measurable targets
   - "Do nothing" baseline — what if we skip architectural design?

6. **Decision formalization**:
   - ADRs for significant decisions surfaced during the session
   - Each ADR: context, decision, alternatives (min 2), consequences
   - Store in `docs/adr/2.x/`

7. **Artifact generation**:
   - `glossary/README.md` — living glossary (new or updated)
   - `docs/context/audience/internal/*.md` or `docs/context/audience/external/*.md` — persona files (optional)
   - `docs/plans/user_journey/*.md` — user journey maps
   - `docs/adr/2.x/YYYY-MM-DD-N-*.md` — decision records
   - `architecture/design-vision.md` — system context, quality attributes, solution overview (optional)

### Out of Scope (Deferred)

- Automated glossary enforcement (PR-time checks, CI integration)
- Full strategic DDD (event storming, aggregate design, saga patterns)
- C4 model diagramming
- Technology selection / vendor evaluation
- CI/CD architecture
- Detailed feature specifications (use `/spec-kitty.specify`)

---

## Phase Details

### Phase 1: Stakeholder Discovery

**Interview questions** (AI Agent asks):
1. "Who will use this system day-to-day?"
2. "Who develops and maintains it?"
3. "Who pays for it or decides its future?"
4. "Who is affected if it fails?"
5. "Are there regulatory or compliance stakeholders?"

**Evidence gate**: At least 3 distinct stakeholder types identified.

**Output**: Stakeholder table + optional persona files.

### Phase 2: Language Harvesting

**Automated analysis** (AI Agent performs):
1. Scan source code: class names, method names, module names, constants
2. Scan existing docs: README, vision.md, charter.md, any existing glossary
3. Scan git history: commit messages for domain vocabulary
4. Extract candidate terms with frequency and source location
5. Group by apparent domain area

**Evidence gate**: At least 15 candidate terms extracted.

**Output**: Raw term list with sources, presented for validation.

### Phase 3: Glossary Refinement

**Interactive dialogue** (Architect validates each term group):
1. AI presents term cluster: "These terms seem related to [domain area]"
2. Architect confirms, renames, merges, or splits terms
3. AI flags: "The term 'session' appears in auth module (meaning: login session) and in billing module (meaning: subscription period) — is this intentional?"
4. Architect decides: same concept (merge) or different concepts (boundary hint)
5. Each confirmed term gets: name, definition, bounded context affinity, status (canonical/candidate/deprecated)

**Evidence gate**: At least 10 terms validated with definitions.

**Output**: `glossary/README.md` updated with structured term entries.

### Phase 4: Context Mapping

**Based on Phase 3 findings** (AI proposes, Architect decides):
1. Terms with conflicting meanings across modules → proposed context boundaries
2. AI presents lightweight context map: "Based on terminology, I see N distinct areas"
3. For each boundary: proposed integration pattern (ACL, shared kernel, etc.)
4. Architect validates, adjusts, or defers ("too early to decide")

**Evidence gate**: This phase is optional — small projects may have a single context.

**Output**: Context map section in `architecture/design-vision.md` or standalone artifact.

### Phase 5: User Journey Capture

**Interactive dialogue** (AI interviews for key flows):
1. "What are the 2-3 most important things users do with this system?"
2. For each: walk through actors, phases, system interactions
3. AI generates journey using `user-journey-template.md`
4. Architect reviews and refines

**Evidence gate**: At least 1 journey captured.

**Output**: `docs/plans/user_journey/NNN-journey-name.md` files.

### Phase 6: Constraint & NFR Capture

**Interview questions**:
1. "What technologies are you committed to?"
2. "What are your performance expectations?"
3. "What security or compliance requirements exist?"
4. "What is the team size and skill profile?"
5. "What would happen if we skipped architectural design?" (do-nothing baseline)

**Evidence gate**: At least 2 quality attributes with measurable targets.

**Output**: Quality attributes section in `architecture/design-vision.md`.

### Phase 7: Decision Formalization

**AI reviews all decisions surfaced during Phases 1-6**:
1. Terminology decisions (e.g., "we call it X, not Y")
2. Boundary decisions (e.g., "billing is a separate context from auth")
3. Pattern decisions (e.g., "ACL between contexts, not shared kernel")
4. Constraint-driven decisions (e.g., "monolith because 2-person team")
5. For each: AI drafts ADR, architect confirms or modifies

**Evidence gate**: At least 1 ADR if any significant decision was made.

**Output**: `docs/adr/2.x/YYYY-MM-DD-N-*.md` files.

### Phase 8: Artifact Generation

CLI commits all artifacts produced during the session.

### Phase 9: Downstream Integration

Post-design, the artifacts are passively consumed:
- `/spec-kitty.specify` — discovery interview references glossary and stakeholders
- `/spec-kitty.plan` — "Technical Context" section cross-references ADRs
- `/spec-kitty.review` — checks terminology consistency against glossary
- `/spec-kitty.tasks` — uses stakeholder personas for acceptance criteria context

---

## Required Event Set

| # | Event | Emitted By | Phase |
|---|-------|-----------|-------|
| 1 | `DesignSessionStarted` | CLI | 1 |
| 2 | `StakeholderIdentified` | AI Agent | 1 |
| 3 | `TerminologyExtracted` | AI Agent | 2 |
| 4 | `GlossaryDraftCreated` | AI Agent | 2 |
| 5 | `TermDefined` | AI Agent | 3 |
| 6 | `AmbiguityDetected` | AI Agent | 3 |
| 7 | `BoundaryHinted` | AI Agent | 3 |
| 8 | `ContextBoundaryProposed` | AI Agent | 4 |
| 9 | `ContextMapCreated` | AI Agent | 4 |
| 10 | `JourneyCaptured` | AI Agent | 5 |
| 11 | `ConstraintCaptured` | AI Agent | 6 |
| 12 | `QualityAttributeDefined` | AI Agent | 6 |
| 13 | `ArchitectureDecisionRecorded` | AI Agent | 7 |
| 14 | `DesignArtifactsGenerated` | CLI | 8 |
| 15 | `DesignSessionCompleted` | CLI | 8 |
| 16 | `FeatureSpecAligned` | AI Agent | 9 |

---

## Acceptance Scenarios

1. **Greenfield design session**
   Given a bootstrapped project with vision.md and charter.md but no architecture artifacts,
   when the architect runs `/spec-kitty.design`,
   then the AI conducts Phases 1-7 and produces a glossary, at least one journey, and at least one ADR.

2. **Glossary detects terminology conflict**
   Given a codebase where `session` means "login session" in `auth/` and "subscription period" in `billing/`,
   when the AI harvests terms in Phase 2 and presents findings in Phase 3,
   then the conflict is surfaced as an `AmbiguityDetected` event
   and the architect can either unify the term or acknowledge a bounded context boundary.

3. **Bounded context emergence from linguistic analysis**
   Given a glossary with 3 terms that have dual meanings across module boundaries,
   when the AI proposes context boundaries in Phase 4,
   then the context map shows distinct areas aligned with the term clusters
   and proposes integration patterns between them.

4. **Living glossary update on subsequent design session**
   Given a project with an existing `glossary/README.md` from a prior design session,
   when the architect runs `/spec-kitty.design` again,
   then the AI loads the existing glossary, harvests new terms from recent code changes,
   and presents only deltas (new terms, changed usage, deprecated terms).

5. **Downstream spec uses glossary**
   Given a completed design session with a glossary containing "WorkPackage" (not "task bundle"),
   when the architect later runs `/spec-kitty.specify`,
   then the discovery interview uses "WorkPackage" consistently
   and flags if the architect uses a non-canonical synonym.

6. **Locality of Change gate**
   Given a 2-person team building a simple CLI tool,
   when the AI proposes 5 bounded contexts with ACLs between them,
   then the Locality of Change check flags this as disproportionate
   and suggests a single-context model with a note to revisit at scale.

7. **ADR conflict detection**
   Given an existing ADR that says "all storage is file-based",
   when the architect discusses using PostgreSQL during Phase 6,
   then the AI flags the conflict with the existing ADR
   and asks the architect to either supersede it or reconsider.

8. **Minimal design session (glossary only)**
   Given an architect who wants to focus only on terminology,
   when they complete Phases 2-3 and skip Phases 4-7,
   then `glossary/README.md` is created/updated
   and no context maps, journeys, or ADRs are produced.

9. **User journey links to stakeholder personas**
   Given a journey captured in Phase 5 with actor "DevOps Engineer",
   when a full persona was generated in Phase 1,
   then the journey's actor table links to the persona file
   via the Persona column.

10. **Design session is repeatable**
    Given a project that has run `/spec-kitty.design` twice,
    then the second session updates existing artifacts (glossary terms, ADRs)
    rather than overwriting them,
    and new terms/decisions are appended, not replaced.

---

## Design Decisions

| Decision | Rationale | ADR |
|----------|-----------|-----|
| Language-first: glossary before boundaries | You cannot draw context boundaries without shared vocabulary — terminology conflicts *are* the boundary signals | pending |
| Glossary is a living artifact, not a deliverable | Static glossaries become stale instantly; living glossaries evolve with code and are enforced downstream | pending |
| Design outputs live in `architecture/` not `kitty-specs/` | Architecture is project-wide, not per-feature; `kitty-specs/` is for feature-scoped work | pending |
| Bounded context mapping is optional | Small projects may have a single context; forcing boundaries creates artificial complexity | pending |
| Downstream integration is passive (reference, not enforce) | MVP: commands read design artifacts but don't block if they're missing; enforcement is a future phase | pending |
| Design session is repeatable, not one-shot | Architecture evolves; the command supports incremental refinement, not just initial capture | pending |
| Minimum 2 alternatives per ADR | Per Traceable Decisions directive; prevents anchoring on first idea | pending |
| "Do nothing" is always an alternative | Per Locality of Change; the current state may be acceptable | pending |

---

## Relationship to Other Journeys

| Journey | Relationship |
|---------|-------------|
| [001 — Project Onboarding & Bootstrap](001-project-onboarding-bootstrap.md) | **Precondition** — bootstrap captures purpose and charter; design captures structure and language. Bootstrap must run first. |
| Feature specification (`/spec-kitty.specify`) | **Downstream consumer** — specs reference glossary terms, stakeholder personas, and ADRs for consistency. |
| Feature planning (`/spec-kitty.plan`) | **Downstream consumer** — plan's "Technical Context" cross-references ADRs; uses context map for WP decomposition. |
| Feature review (`/spec-kitty.review`) | **Downstream consumer** — review checks terminology consistency against glossary. |

---

## Implementation Note: Glossary as Connective Tissue

The glossary is the most important artifact this mission produces. It serves as
connective tissue between all other spec-kitty activities:

```
                        ┌─────────────┐
                        │   Glossary  │
                        │  (living)   │
                        └──────┬──────┘
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
      ┌───────────┐   ┌──────────────┐   ┌───────────┐
      │  specify   │   │    plan      │   │  review    │
      │ (uses      │   │ (references  │   │ (checks    │
      │  terms)    │   │  ADRs)       │   │  drift)    │
      └───────────┘   └──────────────┘   └───────────┘
```

Terms defined during design become the **canonical vocabulary** for all
subsequent work. When an agent writes a spec using "task bundle" but the
glossary says "WorkPackage", that's a reviewable inconsistency.

This is the agentic feasibility shift described in Doctrine's Living Glossary
Practice: continuous linguistic monitoring was historically infeasible, but
LLM-powered agents make it operationally viable.

---

## Product Alignment

1. **Every spec-kitty command leads with discovery** — design continues this pattern at the architecture level.
2. **Ambiguity is the enemy** — the design mission exists to reduce it before feature work begins.
3. **Language shapes architecture** — per Language-First Architecture, terminology conflicts predict system problems.
4. **Human In Charge** — the architect decides terminology, boundaries, and trade-offs; the AI harvests, proposes, and documents.
5. **Living over static** — glossary and design artifacts evolve with the project; they are not one-shot deliverables.
