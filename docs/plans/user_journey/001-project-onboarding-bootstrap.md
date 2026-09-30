---
title: 'User Journey: Project Onboarding & Bootstrap'
description: 'User journey for project onboarding and bootstrap: how a new project is initialized and brought to a working Spec Kitty state, in a field-table record.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# User Journey: Project Onboarding & Bootstrap

> **Historical (2.x-era vision snapshot).** Written in early 2026 and not re-validated against the 4.x CLI; some steps have since shipped in a different form, and older "feature" wording means *mission*. Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

| Field | Value |
|---|---|
| **Status** | DRAFT |
| **Implementation Status** | VISION (target-state proposal; not current runtime reality) |
| **Date** | 2026-02-15 |
| **Primary Contexts** | Project Initialization, Governance |
| **Supporting Contexts** | Mission Selection, Feature Specification |
| **Related Spec / ADR** | N/A (proposed new feature — would become `kitty-specs/04X-bootstrap-command/`) |

---

## Scenario

A developer starts a new project with spec-kitty. They need to go from an empty
directory (or existing repo) to a fully contextualized project where AI agents
understand the project's purpose, technical constraints, and governance rules —
and where the first feature can be specified with full project context.

The current flow (`init` → optional `charter` → `specify`) leaves a gap:
project-level intent ("what are we building and why?") is never captured. The
proposed `/spec-kitty.bootstrap` command fills this gap by wrapping vision capture
and charter into a single guided onboarding, replacing the standalone
`/spec-kitty.charter` command.

---

## Actors

| # | Actor | Type | Persona | Role in Journey |
|---|-------|------|---------|-----------------|
| 1 | Project Owner | `human` | [Project Owner](../../context/audience/external/project-owner.md) | Answers vision and governance questions; makes scope decisions |
| 2 | AI Agent | `llm` | [AI Collaboration Agent](../../context/audience/internal/ai-collaboration-agent.md) | Conducts discovery interview; generates vision.md and charter.md |
| 3 | Spec-Kitty CLI | `system` | [Spec Kitty CLI Runtime](../../context/audience/internal/spec-kitty-cli-runtime.md) | Scaffolds project structure; validates prerequisites; stores artifacts |

---

## Preconditions

1. Developer has spec-kitty CLI installed and available on PATH.
2. A target directory exists (empty or existing repo).
3. At least one supported AI agent is configured (e.g., Claude Code, Copilot, Gemini).
4. Git is available (optional but recommended).

---

## Journey Map

| Phase | Actor(s) | System | Key Events |
|-------|----------|--------|------------|
| 1. Init | Project Owner | CLI scaffolds `.kittify/`, agent dirs, git repo, context files | `ProjectInitialized`, `AgentConfigured` |
| 2. Vision Discovery | Project Owner ↔ AI Agent | AI conducts interview: purpose, outcomes, scope, stakeholders | `VisionInterviewStarted`, `VisionCaptured` |
| 3. Agent Customization | Project Owner ↔ AI Agent | AI presents available approaches; user selects practices for specialist agents | `AgentCustomizationStarted`, `ApproachSelected` |
| 4. Technical Standards | Project Owner ↔ AI Agent | AI asks about languages, testing, performance, deployment | `CharterPhaseCompleted` |
| 5. Code Quality (optional) | Project Owner ↔ AI Agent | AI asks about PR requirements, review gates, documentation standards | `CharterPhaseCompleted` |
| 6. Tribal Knowledge (optional) | Project Owner ↔ AI Agent | AI asks about team conventions, lessons learned, known pitfalls | `CharterPhaseCompleted` |
| 7. Governance (optional) | Project Owner ↔ AI Agent | AI asks about amendment process, compliance, escalation rules | `CharterPhaseCompleted` |
| 8. Bootstrap Complete | — | CLI commits vision.md + charter.md; displays next steps | `BootstrapCompleted` |
| 9. First Feature | Project Owner | Owner runs `/spec-kitty.specify` — discovery interview now has vision.md context | `FeatureSpecificationStarted` |

---

## Coordination Rules

**Default posture**: Gated (each phase requires human answers before proceeding)

1. Vision phase (Phase 2) is **required** — bootstrap cannot be skipped entirely.
2. Agent Customization (Phase 3) is **recommended** — users may accept defaults, pick-and-choose from available approaches, or define custom practices.
3. Technical Standards (Phase 4) is **recommended** — skippable with confirmation.
4. Phases 5-7 are **optional** — each can be skipped independently.
5. AI Agent proposes answers based on repo analysis; Project Owner confirms or corrects.
6. If `charter.md` already exists, bootstrap enters **update mode** (merge, don't overwrite).
7. If `vision.md` already exists, bootstrap asks whether to revise or skip Phase 2.

---

## Responsibilities

### Spec-Kitty CLI (Local Runtime)

1. Validate prerequisites (`spec-kitty check`-equivalent before bootstrap).
2. Detect existing artifacts (vision.md, charter.md) and offer update vs. create.
3. Store outputs in `.kittify/memory/` (vision.md, charter.md).
4. Commit artifacts to the current branch.
5. Display post-bootstrap guidance (next command: `/spec-kitty.specify`).

### AI Agent (LLM Context)

1. Conduct phase-by-phase discovery interview with skip options.
2. Analyze existing repo structure for context (if bootstrapping an existing project).
3. Generate vision.md from interview answers using Doctrine VISION.md structure.
4. Present available approaches for agent customization with clear descriptions and examples.
5. Record selected approaches in charter.md under a dedicated section.
6. Generate or update charter.md from interview answers using existing template.
7. Propose sensible defaults where Project Owner skips questions.

---

## Scope: MVP (Phase 1)

### In Scope

1. **Vision capture**:
   - Purpose statement ("What is the purpose of this repository?")
   - Problem statement (optional follow-up — only when purpose implies solving something)
   - Desired outcomes, scope boundaries
   - Lightweight stakeholder identification (names and roles, not full personas)
   - Role of AI agents in this project

2. **Agent customization**:
   - Present available approaches from `doctrine/approaches/` with descriptions
   - Three paths: accept defaults, pick-and-choose from catalog, define custom practices
   - Example selections: TDD (Directive 017), test-first bug fixing, locality-of-change
   - Selected approaches stored in charter.md under "Agent Practices" section
   - Approaches shape how specialist agent profiles (e.g., Python Pedro) behave during implementation

3. **Charter** (existing functionality, repackaged):
   - Technical standards (languages, testing, deployment)
   - Code quality gates (optional)
   - Tribal knowledge (optional)
   - Governance rules (optional)

3. **Artifact generation**:
   - `.kittify/memory/vision.md` (new)
   - `.kittify/charter/charter.md` (existing format)

### Out of Scope (Deferred)

- Full stakeholder personas (use design mission for deep profiles)
- Architecture decision records (captured per-feature, not at bootstrap)
- CI/CD pipeline generation (use `init` flags or manual setup)
- Multi-repo or monorepo orchestration
- Team/organization-level governance (bootstrap is per-project)

---

## Required Event Set

| # | Event | Emitted By | Phase |
|---|-------|-----------|-------|
| 1 | `ProjectInitialized` | CLI | 1 |
| 2 | `AgentConfigured` | CLI | 1 |
| 3 | `VisionInterviewStarted` | AI Agent | 2 |
| 4 | `VisionCaptured` | AI Agent | 2 |
| 5 | `AgentCustomizationStarted` | AI Agent | 3 |
| 6 | `ApproachSelected` | AI Agent | 3 |
| 7 | `CharterPhaseCompleted` | AI Agent | 4-7 |
| 8 | `BootstrapCompleted` | CLI | 8 |
| 9 | `FeatureSpecificationStarted` | AI Agent | 9 |

---

## Acceptance Scenarios

1. **Fresh project bootstrap**
   Given an empty directory and spec-kitty installed,
   when the user runs `spec-kitty init` followed by `/spec-kitty.bootstrap`,
   then `.kittify/memory/vision.md` and `.kittify/charter/charter.md` are created
   and committed to the current branch.

2. **Vision informs feature specification**
   Given a bootstrapped project with `vision.md` containing "CLI tool for X",
   when the user runs `/spec-kitty.specify "add Y feature"`,
   then the discovery interview references the project vision for context alignment.

3. **Minimal bootstrap (skip optional phases)**
   Given a user who wants to start quickly,
   when they complete Phase 2 (Vision) and skip Phases 3-7,
   then `vision.md` is created and `charter.md` contains sensible defaults
   with a note that phases were skipped.

4. **Agent customization with TDD**
   Given a user bootstrapping a Python project,
   when they reach Phase 3 (Agent Customization) and select "TDD" and "test-first bug fixing",
   then `charter.md` records these as active approaches under "Agent Practices",
   and subsequent `/spec-kitty.implement` sessions instruct specialist agents
   (e.g., Python Pedro) to follow the TDD RED→GREEN→REFACTOR cycle.

5. **Agent customization with defaults**
   Given a user who accepts the default agent practices during Phase 3,
   when bootstrap completes,
   then `charter.md` records the default approach set
   and agents operate with standard behavior (no TDD mandate, no specific refactoring discipline).

6. **Agent customization with custom practice**
   Given a user who defines a custom practice ("always use property-based testing"),
   when they describe it during Phase 3,
   then bootstrap records it as a custom approach in `charter.md`
   alongside any selected catalog approaches.

7. **Approach selection changes CLI behavior (trunk-based development)**
   Given a user who selects "trunk-based development" during Phase 3,
   when they later run `spec-kitty implement WP01`,
   then spec-kitty uses short-lived branches (<24h) instead of long-lived feature branches,
   and `spec-kitty merge` uses direct-to-main merge strategy,
   because the approach is modeled in the Python codebase as an execution hook,
   not just recorded as text.

9. **Existing project bootstrap (update mode)**
   Given an existing project with a `charter.md`,
   when the user runs `/spec-kitty.bootstrap`,
   then bootstrap detects the existing charter and offers to update rather than overwrite,
   and creates `vision.md` without affecting charter content.

10. **Charter deprecated gracefully**
   Given a user who runs `/spec-kitty.charter` after bootstrap exists,
   then the command displays guidance to use `/spec-kitty.bootstrap` instead
   and offers to redirect.

---

## Design Decisions

| Decision | Rationale | ADR |
|----------|-----------|-----|
| Vision is a separate file from charter | Vision captures *what/why*, charter captures *how* — different lifecycles and audiences | pending |
| Bootstrap runs after init, not merged into init | Init is non-interactive scaffolding; bootstrap is interactive discovery — different concerns | pending |
| Charter command deprecated, not removed | Backward compatibility; existing projects may have workflows depending on it | pending |
| Phase 2 (Vision) is required, Phases 3-7 optional | A project without stated intent is more harmful than a project without governance rules | pending |
| Events emitted via EventBridge (Feature 040) | Bootstrap is a lane transition-equivalent lifecycle event; use existing infrastructure | pending |
| Opening question is purpose-first, not problem-first | "What is the purpose of this repository?" accommodates non-solution repos (creative writing, exploration, research, worldbuilding) — problem statement is a conditional follow-up only when purpose implies solving something | pending |
| Vision questions are mission-agnostic | Bootstrap must not assume software development — future missions include creative writing, exploration, design, and other non-engineering endeavours | pending |
| Approaches selected at bootstrap shape CLI execution, not just agent style | Some approaches (e.g., trunk-based development) change how spec-kitty itself operates — branching strategy, worktree lifecycle, merge patterns. This means Agents, Approaches, and Tactics must be modeled as first-class concepts in the Python codebase, not just recorded as text in charter.md. See Implementation Note below. | pending |

---

## Implementation Note: Modeling Agents, Approaches, and Tactics in Python

> **Status**: Architectural observation — not yet designed or specified.

The Agent Customization phase (Phase 3) has deeper implications than recording
preferences in a markdown file. Some approach selections directly change how
spec-kitty's CLI commands behave:

| Approach | Spec-Kitty Execution Impact |
|----------|----------------------------|
| **TDD** | `/spec-kitty.implement` instructs agents to follow RED→GREEN→REFACTOR cycle; task prompts include test-first guidance |
| **Test-first bug fixing** | `/spec-kitty.implement` on bug-fix features mandates failing test before code change |
| **Trunk-based development** | Changes branching strategy: short-lived branches (<24h), direct-to-main merges, feature flags instead of long-lived branches. Affects `spec-kitty implement` (worktree lifetime), `spec-kitty merge` (merge strategy), and potentially removes the workspace-per-WP model in favor of direct commits. |
| **Locality of change** | `/spec-kitty.review` enforces evidence-based problem assessment; rejects over-engineering |

This means the current model — recording approaches as prose in `charter.md` —
is **insufficient**. The Python codebase needs:

1. **`Approach` as a data model** — Not just markdown, but a structured object with:
   - Identity (name, description, source file)
   - Execution hooks (what CLI behavior changes when this approach is active)
   - Compatible missions (TDD applies to software-dev, not creative-writing)
   - Prerequisite approaches (test-first bug fixing implies TDD awareness)

2. **`AgentProfile` as a data model** — Already partially modeled in the glossary
   (dataclass with `required_directives`), but needs to be loadable from
   `doctrine/agents/*.agent.md` and queryable at runtime.

3. **`Tactic` as a data model** — Referenced by approaches, consumed by agents,
   but the CLI doesn't need to model them deeply. Tactics remain agent-facing
   execution guides. The CLI only needs to know which tactics an approach implies,
   so it can include them in agent context.

4. **Approach registry** — A mechanism for `spec-kitty` to discover available
   approaches, know which are active for this project, and adjust CLI behavior
   accordingly. Likely stored in `.kittify/config.yaml` alongside the existing
   agent configuration.

This is a significant evolution of the spec-kitty data model — it transforms the
charter from a passive document into an active behavioral configuration that
the CLI reads and acts upon.

---

## Product Alignment

1. **Every spec-kitty command leads with discovery** — bootstrap continues this pattern at the project level.
2. **Charter is governance, not vision** — separating them clarifies the purpose of each artifact.
3. **Agents need project context** — vision.md gives every subsequent agent interaction a "north star" reference.
