---
title: 'User Journey: System Architecture Design'
description: 'User journey for system architecture design: how an architect drives architecture decisions through Spec Kitty, in a field-table record.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/archive/plans/user_journey/001-project-onboarding-bootstrap.md
---
# User Journey: System Architecture Design

> **Historical (2.x-era vision snapshot).** Written in early 2026 and not re-validated against the 4.x CLI; some steps have since shipped in a different form, and older "feature" wording means *mission*. Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

| Field | Value |
|---|---|
| **Status** | DRAFT |
| **Implementation Status** | VISION (target-state proposal; not current runtime reality) |
| **Date** | 2026-02-15 |
| **Primary Contexts** | Architecture, Design Decision-Making |
| **Supporting Contexts** | Governance, Feature Specification, Research |
| **Related Spec / ADR** | N/A (proposed new command — `/spec-kitty.design`) |

---

## Scenario

A team is building (or evolving) a system and needs to establish its architectural
foundations: who the stakeholders are, what quality attributes matter, what
constraints exist, and which architectural patterns best serve the system's goals.
This is not a per-feature activity — it's a cross-cutting design exercise that
produces living architecture documents consumed by all subsequent feature work.

The current spec-kitty flow (`specify` → `plan` → `tasks` → `implement`) handles
feature-level design within `plan.md`, but has no dedicated phase for **system-level
architectural design**: stakeholder identification, constraint capture, NFR
analysis, reference architecture selection, and pattern decisions (bounded contexts,
layered, ports-and-adapters, ACL boundaries, etc.).

The proposed `/spec-kitty.design` command fills this gap. It follows the same
discovery-interview pattern as all spec-kitty commands but produces architecture
artifacts rather than feature artifacts.

---

## Actors

| # | Actor | Type | Persona | Role in Journey |
|---|-------|------|---------|-----------------|
| 1 | Architect | `human` | [System Architect](../../../context/audience/internal/system-architect.md) | Provides domain knowledge, makes trade-off decisions, validates design outputs |
| 2 | AI Agent | `llm` | [AI Collaboration Agent](../../../context/audience/internal/ai-collaboration-agent.md) | Conducts structured discovery, researches patterns, produces architecture artifacts, checks alignment |
| 3 | Spec-Kitty CLI | `system` | [Spec Kitty CLI Runtime](../../../context/audience/internal/spec-kitty-cli-runtime.md) | Orchestrates phases, stores artifacts, manages architecture document lifecycle |
| 4 | Codebase | `system` | [Project Codebase](../../../context/audience/internal/project-codebase.md) | Provides evidence for alignment checks — existing patterns, module structure, dependency graph |

---

## Preconditions

1. Project has been initialized with `spec-kitty init`.
2. Project has been bootstrapped (`/spec-kitty.bootstrap`) — `vision.md` exists with project purpose and scope.
3. Charter exists (from bootstrap or standalone `/spec-kitty.charter`).
4. At least one supported AI agent is configured.
5. Git repository is initialized (architecture artifacts are version-controlled).

---

## Journey Map

| Phase | Actor(s) | System | Key Events |
|-------|----------|--------|------------|
| 1. Stakeholder Discovery | Architect ↔ AI Agent | AI interviews: who uses/operates/develops/pays for this system? | `DesignSessionStarted`, `StakeholderIdentified` |
| 2. Constraint & NFR Capture | Architect ↔ AI Agent | AI interviews: what quality attributes matter? what are hard constraints? | `ConstraintCaptured`, `QualityAttributeDefined` |
| 3. Functional Requirement Framing | Architect ↔ AI Agent | AI interviews: top-level capabilities (MoSCoW), domain boundaries | `FunctionalRequirementFramed` |
| 4. Codebase Alignment Scan | AI Agent ↔ Codebase | AI scans existing code for patterns, module boundaries, dependency structure | `CodebaseScanned`, `PatternDetected` |
| 5. Pattern Research | AI Agent | AI researches applicable architectural patterns based on constraints + NFRs | `PatternResearched`, `AlternativeEvaluated` |
| 6. Reference Architecture Selection | Architect ↔ AI Agent | AI proposes reference architecture with alternatives; architect decides | `ReferenceArchitectureProposed`, `ArchitectureDecisionRecorded` |
| 7. Design Pattern Decisions | Architect ↔ AI Agent | AI proposes specific patterns (bounded contexts, ACL, layers); architect validates | `DesignPatternSelected`, `ArchitectureDecisionRecorded` |
| 8. Artifact Generation | AI Agent ↔ CLI | CLI commits architecture artifacts; links to vision and charter | `DesignArtifactsGenerated`, `DesignSessionCompleted` |
| 9. Downstream Alignment | — | Subsequent `/spec-kitty.plan` commands reference architecture artifacts for per-feature design | `FeaturePlanAligned` |

---

## Coordination Rules

**Default posture**: Gated (architecture decisions require explicit human confirmation)

1. **Stakeholder and constraint phases are required** — design without knowing who it serves and what limits apply produces fantasy architecture.
2. **Codebase alignment scan is automatic** — the AI agent examines existing code whether or not the architect asks; findings are presented for review, not silently applied.
3. **Pattern research is evidence-based** — the AI agent must cite known patterns (Gang of Four, POSA, DDD, Hexagonal, etc.) with trade-off analysis, not invent novel architectures.
4. **Every architectural decision requires at minimum one alternative** — "we chose X" is insufficient; "we chose X over Y and Z because..." is required (per Traceable Decisions directive).
5. **The architect has final authority** — the AI proposes, the human disposes. This is a Human In Charge flow; the AI must not record a decision as final without explicit architect confirmation.
6. **Existing ADRs are checked before new decisions** — if the project has prior ADRs (in `docs/adr/2.x/`), the AI loads relevant ones and flags conflicts before proposing new patterns.
7. **NFRs must be measurable** — "the system should be fast" is rejected; "p95 response time < 200ms under 1000 concurrent users" is accepted.

---

## Responsibilities

### Spec-Kitty CLI (Local Runtime)

1. Detect existing architecture artifacts and offer update vs. create mode.
2. Orchestrate phase progression (gated — wait for human confirmation per phase).
3. Store outputs in `architecture/` directory at repository root.
4. Commit artifacts to the current branch with structured commit messages.
5. Ensure `plan.md` template references new architecture docs (downstream alignment).

### AI Agent (LLM Context)

1. Conduct phase-by-phase discovery interview with structured prompts.
2. Scan codebase for existing architectural patterns, module boundaries, and naming conventions.
3. Research applicable patterns from known catalogs (DDD, Hexagonal, Clean, CQRS, etc.).
4. Present alternatives with trade-off matrices for every significant decision.
5. Generate architecture artifacts using Doctrine-aligned templates.
6. Cross-reference proposed decisions against existing ADRs.
7. Produce stakeholder personas using the `stakeholder-persona-template.md`.
8. Apply Locality of Change discipline — verify the proposed architecture isn't over-engineered for the problem scale.

---

## Scope: MVP

### In Scope

1. **Stakeholder discovery**:
   - Identify stakeholder categories (users, operators, developers, business owners)
   - Capture lightweight personas inline (name, type, what they care about)
   - Optional: generate full persona files using `stakeholder-persona-template.md`

2. **Constraints & quality attributes**:
   - Hard constraints (regulatory, budget, team size, existing tech stack, timeline)
   - Quality attributes with measurable targets (performance, security, availability, maintainability)
   - "Do nothing" baseline — what happens if we don't invest in architecture?

3. **Functional requirement framing**:
   - Top-level feature list with MoSCoW prioritization
   - Domain boundary identification (what belongs together, what doesn't)
   - Not detailed FRs — those come from `/spec-kitty.specify` per feature

4. **Codebase alignment**:
   - Module/package structure analysis
   - Existing pattern detection (repository pattern, service layer, event-driven, etc.)
   - Dependency graph overview
   - Naming convention inventory

5. **Reference architecture selection**:
   - Propose 2-3 candidate architectures with trade-off analysis
   - Examples: layered monolith, hexagonal/ports-and-adapters, microservices, modular monolith, event-driven
   - Record selection as ADR with rationale

6. **Design pattern decisions**:
   - Domain modeling approach (bounded contexts, aggregates, value objects, or simpler alternatives)
   - Integration patterns (ACL, shared kernel, published language, open-host)
   - Cross-cutting concerns (logging strategy, error handling approach, configuration management)
   - Data flow patterns (CQRS, event sourcing, or traditional CRUD)
   - Record each as ADR or decision marker

7. **Artifact generation**:
   - `architecture/design-vision.md` — high-level vision, quality attributes, solution overview
   - `architecture/functional-requirements.md` — stakeholder table, top-level FRs with MoSCoW
   - `docs/adr/2.x/YYYY-MM-DD-N-*.md` — one ADR per significant decision
   - `docs/context/audience/internal/` and `docs/context/audience/external/` — optional persona files for key stakeholder types

### Out of Scope (Deferred)

- Detailed feature specifications (use `/spec-kitty.specify` per feature)
- Implementation planning (use `/spec-kitty.plan` per feature)
- CI/CD architecture (separate concern, could be a future design session topic)
- Infrastructure-as-code or deployment topology (operational concern)
- Full C4 model diagramming (could be a future enhancement)
- Technology selection / vendor evaluation (adjacent but distinct activity)

---

## Phase Details

### Phase 1: Stakeholder Discovery

**Interview questions** (AI Agent asks):

1. "Who will use this system day-to-day?" → end users, operators
2. "Who develops and maintains it?" → developers, DevOps, QA
3. "Who pays for it or decides its future?" → product owners, sponsors
4. "Who is affected if it fails?" → dependent systems, SLA holders
5. "Are there regulatory bodies or compliance stakeholders?" → auditors, legal

**Outputs**: Stakeholder table in `functional-requirements.md`, optional persona files.

**Evidence gate**: At least 3 distinct stakeholder types identified before proceeding.

### Phase 2: Constraint & NFR Capture

**Interview questions**:

1. "What technologies are you committed to?" → language, framework, database locks
2. "What are your performance expectations?" → latency, throughput, concurrency targets
3. "What security or compliance requirements exist?" → auth, encryption, audit trails
4. "What is the team size and skill profile?" → capacity constraints affect architecture choices
5. "What is the deployment target?" → cloud, on-prem, edge, hybrid
6. "What is the budget and timeline?" → constrains solution complexity

**Outputs**: Quality attributes section in `design-vision.md`, constraints table.

**Evidence gate**: At least 2 quality attributes have measurable targets.

### Phase 3: Functional Requirement Framing

**Interview questions**:

1. "What are the 5-10 most important capabilities?" → MoSCoW list
2. "Which capabilities are related to each other?" → domain boundary hints
3. "Which capabilities are independent?" → potential bounded context boundaries
4. "What data does each capability work with?" → entity/aggregate hints

**Outputs**: FR table in `functional-requirements.md` with MoSCoW and status columns.

**Evidence gate**: Must-haves identified; domain groupings proposed.

### Phase 4: Codebase Alignment Scan

**Automated analysis** (AI Agent performs):

1. Scan directory structure → detect layering (if any)
2. Scan imports/dependencies → detect coupling patterns
3. Scan naming conventions → detect domain language consistency
4. Check for existing ADRs → load and index
5. Check for existing architecture docs → detect format and coverage

**Outputs**: `codebase-alignment.md` (internal working document, may not persist).

**Evidence gate**: Patterns detected are presented to architect for validation ("Is this intentional?").

### Phase 5: Pattern Research

**AI Agent research** (evidence-based, not generative):

1. Given constraints + NFRs, identify candidate architectural styles
2. For each candidate, provide: description, when to use, when to avoid, trade-offs
3. Cross-reference with codebase scan — which patterns already exist? which would require significant refactoring?
4. Apply Locality of Change: is the proposed architecture proportional to the problem?

**Outputs**: Alternatives section in draft ADR(s).

**Evidence gate**: Minimum 3 alternatives evaluated; "do nothing" included.

### Phase 6: Reference Architecture Selection

**Decision point** (architect decides, AI proposes):

- AI presents trade-off matrix: candidate architectures × quality attributes
- Highlights which architecture best serves each quality attribute
- Flags conflicts (e.g., "microservices improve scalability but increase operational complexity for a 2-person team")
- Architect selects or modifies

**Outputs**: ADR recording the reference architecture decision.

### Phase 7: Design Pattern Decisions

**Iterative decisions** (one per significant concern):

For each design area (domain modeling, integration, cross-cutting, data flow):
1. AI proposes pattern with rationale
2. Architect confirms, modifies, or rejects
3. Decision recorded as ADR or decision marker

**Pattern catalog** (examples, not exhaustive):

| Design Area | Pattern Options |
|-------------|----------------|
| **Domain modeling** | Bounded contexts + aggregates, transaction scripts, table module, domain model (Evans) |
| **Integration** | Anti-corruption layer (ACL), shared kernel, published language, open-host service |
| **Architecture style** | Layered, hexagonal (ports & adapters), clean architecture, vertical slices |
| **Data flow** | CQRS, event sourcing, traditional CRUD, saga/choreography |
| **Module boundaries** | Package by layer, package by feature, package by component |

**Outputs**: ADRs for each significant decision, updated `design-vision.md`.

### Phase 8: Artifact Generation

**CLI commits**:
- `architecture/design-vision.md` (new or updated)
- `architecture/functional-requirements.md` (new or updated)
- `docs/adr/2.x/YYYY-MM-DD-N-*.md` (one per decision)
- `docs/context/audience/internal/*.md` or `docs/context/audience/external/*.md` (if full personas requested)

### Phase 9: Downstream Alignment

**Post-design integration**:
- Subsequent `/spec-kitty.plan` commands detect architecture artifacts
- `plan.md` "Technical Context" section references architecture decisions
- Per-feature `plan.md` cross-references relevant ADRs
- Pattern decisions inform task decomposition (e.g., "implement port interface before adapter")

---

## Required Event Set

| # | Event | Emitted By | Phase |
|---|-------|-----------|-------|
| 1 | `DesignSessionStarted` | CLI | 1 |
| 2 | `StakeholderIdentified` | AI Agent | 1 |
| 3 | `ConstraintCaptured` | AI Agent | 2 |
| 4 | `QualityAttributeDefined` | AI Agent | 2 |
| 5 | `FunctionalRequirementFramed` | AI Agent | 3 |
| 6 | `CodebaseScanned` | AI Agent | 4 |
| 7 | `PatternDetected` | AI Agent | 4 |
| 8 | `PatternResearched` | AI Agent | 5 |
| 9 | `AlternativeEvaluated` | AI Agent | 5 |
| 10 | `ReferenceArchitectureProposed` | AI Agent | 6 |
| 11 | `ArchitectureDecisionRecorded` | AI Agent | 6, 7 |
| 12 | `DesignPatternSelected` | AI Agent | 7 |
| 13 | `DesignArtifactsGenerated` | CLI | 8 |
| 14 | `DesignSessionCompleted` | CLI | 8 |
| 15 | `FeaturePlanAligned` | AI Agent | 9 |

---

## Acceptance Scenarios

1. **Greenfield project architecture**
   Given a bootstrapped project with no existing architecture documents,
   when the architect runs `/spec-kitty.design`,
   then the AI conducts a structured interview across Phases 1-7,
   and produces `design-vision.md`, `functional-requirements.md`,
   and at least one ADR in `docs/adr/2.x/`.

2. **Existing project architecture evolution**
   Given a project with existing `architecture/design-vision.md` and 3 ADRs,
   when the architect runs `/spec-kitty.design`,
   then the AI loads existing documents, presents current state,
   and asks what aspect of the architecture needs revisiting,
   without overwriting existing decisions.

3. **Codebase alignment detects mismatch**
   Given a codebase organized as a flat module structure,
   when the AI scans in Phase 4 and the architect selects "hexagonal architecture" in Phase 6,
   then the AI flags the gap between current and target architecture,
   and produces an ADR documenting the migration path.

4. **Quality attributes drive pattern selection**
   Given the architect defines "p95 latency < 50ms" and "offline-capable",
   when the AI researches patterns in Phase 5,
   then the alternatives matrix weighs each pattern against these specific NFRs,
   and the recommendation cites which NFRs each pattern satisfies or compromises.

5. **Bounded context identification**
   Given the architect identifies 3 domain groups in Phase 3
   (e.g., "user management", "billing", "content delivery"),
   when the AI proposes domain modeling patterns in Phase 7,
   then it presents bounded context boundaries aligned with the domain groups,
   and proposes integration patterns (ACL, shared kernel) between them.

6. **Locality of Change gate**
   Given a 2-person team building a simple CLI tool,
   when the AI proposes a microservices architecture with event sourcing,
   then the Locality of Change check flags this as disproportionate,
   and the AI re-proposes with simpler alternatives ranked first.

7. **ADR conflict detection**
   Given an existing ADR that says "all communication is synchronous REST",
   when the architect selects event-driven integration in Phase 7,
   then the AI flags the conflict with the existing ADR,
   and asks the architect to either supersede the old ADR or reconsider.

8. **Downstream plan alignment**
   Given a completed design session that selected ports-and-adapters,
   when the architect later runs `/spec-kitty.plan` for a new feature,
   then `plan.md` references the architecture ADRs,
   and the plan's "Technical Context" section includes the selected patterns.

9. **Minimal design session (skip optional phases)**
   Given an architect who wants to focus only on stakeholders and NFRs,
   when they complete Phases 1-2 and skip Phases 3-7,
   then `design-vision.md` is created with stakeholders and quality attributes,
   and no pattern decisions are recorded (deferred to future sessions).

10. **Stakeholder persona generation**
    Given the architect identifies "DevOps Engineer" as a key stakeholder,
    when they request a full persona during Phase 1,
   then the AI generates `docs/context/audience/internal/devops-engineer.md`
    using the `stakeholder-persona-template.md` format.

---

## Design Decisions

| Decision | Rationale | ADR |
|----------|-----------|-----|
| Design outputs live in `architecture/` not `kitty-specs/` | Architecture is project-wide, not per-feature; `kitty-specs/` is for feature-scoped work | pending |
| ADRs use existing `docs/adr/2.x/` directory | Aligns with versioned architecture structure | pending |
| Codebase scan is always performed (not opt-in) | Architecture decisions without codebase awareness produce ivory-tower designs | pending |
| Minimum 3 alternatives required per decision | Per Traceable Decisions directive; prevents anchoring on first idea | pending |
| NFRs must be measurable | Vague quality attributes ("fast", "secure") cannot guide pattern selection | pending |
| "Do nothing" is always an alternative | Per Locality of Change; the current state may be acceptable | pending |
| Phases 1-2 required, 3-7 optional | Knowing stakeholders and constraints is the minimum viable architecture; pattern selection can happen incrementally | pending |
| Design session is repeatable (not one-shot) | Architecture evolves; the command should support revisiting decisions, not just initial capture | pending |
| Downstream alignment is passive (reference, not enforce) | `/spec-kitty.plan` reads architecture docs but doesn't block if decisions are missing; advisory, not gated | pending |

---

## Relationship to Other Journeys

| Journey | Relationship |
|---------|-------------|
| [001 — Project Onboarding & Bootstrap](001-project-onboarding-bootstrap.md) | Bootstrap captures project *purpose*; design captures project *structure*. Bootstrap should run first. |
| Feature specification (`/spec-kitty.specify`) | Features reference architecture decisions; design provides the structural context features fit into. |
| Feature planning (`/spec-kitty.plan`) | Plan's "Technical Context" section cross-references ADRs. Pattern decisions inform task decomposition. |

---

## Relationship to Design Mission Implementation

This journey captures the **user experience** of architectural design. The
`kitty-specs/041-design-mission/spec.md` (planned; not currently present on this branch)
captures the **system implementation** for adding a `design` mission type to the
spec-kitty mission system (mission.yaml, templates, migrations, domain enum).

The two artifacts are complementary:
- This journey answers: **What does the architect experience?**
- The feature specification answers: **How does spec-kitty implement it?**

When the design mission is implemented as a kitty-specs feature, this journey
becomes the acceptance test specification.

---

## Implementation Note: Relationship to Approach Modeling

The bootstrap journey's [Implementation Note](001-project-onboarding-bootstrap.md#implementation-note-modeling-agents-approaches-and-tactics-in-python)
identifies that Approaches, Agents, and Tactics need Python data models. This
design journey adds a further dimension: **architectural pattern decisions** should
be queryable at runtime, similar to how selected approaches shape CLI behavior.

For example, if the architect selects "ports-and-adapters" during a design session:
- `/spec-kitty.plan` could suggest organizing WPs by port/adapter boundaries
- `/spec-kitty.tasks` could include port interface definition before adapter implementation
- `/spec-kitty.review` could check that new code follows the port/adapter contract

This is a future consideration — the MVP design command would produce static
documents. The active behavioral integration (like approach execution hooks)
is a subsequent evolution.

---

## Product Alignment

1. **Every spec-kitty command leads with discovery** — design continues this pattern at the architecture level.
2. **Design complements, doesn't replace, plan.md** — feature-level design stays in `plan.md`; system-level design lives in `architecture/`.
3. **Traceable Decisions is the core discipline** — every design decision gets an ADR with alternatives and rationale.
4. **Locality of Change prevents over-architecture** — the AI must check proportionality before recommending complex patterns.
5. **Human In Charge** — the architect decides; the AI researches, proposes, and documents.
