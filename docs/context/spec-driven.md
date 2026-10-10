---
title: Specification-Driven Development (SDD)
description: Specification-Driven Development methodology behind Spec Kitty — how executable specifications and implementation plans generate code, inverting the code-first power structure.
doc_status: active
updated: '2026-10-10'
audience: docs/context/audience/internal/system-architect.md
type: explanation
---
# Specification-Driven Development (SDD)

> This guide is maintained as part of Spec Kitty, inspired by GitHub's [Spec Kit](https://github.com/github/spec-kit). We preserve attribution to the original authors while expanding the methodology.

## The Power Inversion

For decades, code has been king. Specifications served code—they were the scaffolding we built and then discarded once the "real work" of coding began. We wrote PRDs to guide development, created design docs to inform implementation, drew diagrams to visualize architecture. But these were always subordinate to the code itself. Code was truth. Everything else was, at best, good intentions. Code was the source of truth, and as it moved forward, specs rarely kept pace. As the asset (code) and the implementation are one, it's not easy to have a parallel implementation without trying to build from the code.

Spec-Driven Development (SDD) inverts this power structure. Specifications don't serve code—code serves specifications. The Product Requirements Document (PRD) isn't a guide for implementation; it's the source that generates implementation. Technical plans aren't documents that inform coding; they're precise definitions that produce code. This isn't an incremental improvement to how we build software. It's a fundamental rethinking of what drives development.

The gap between specification and implementation has plagued software development since its inception. We've tried to bridge it with better documentation, more detailed requirements, stricter processes. These approaches fail because they accept the gap as inevitable. They try to narrow it but never eliminate it. SDD eliminates the gap by making specifications and their concrete implementation plans born from the specification executable. When specifications and implementation plans generate code, there is no gap—only transformation.

This transformation is now possible because AI can understand and implement complex specifications, and create detailed implementation plans. But raw AI generation without structure produces chaos. SDD provides that structure through specifications and subsequent implementation plans that are precise, complete, and unambiguous enough to generate working systems. The specification becomes the primary artifact. Code becomes its expression (as an implementation from the implementation plan) in a particular language and framework.

In this new world, maintaining software means evolving specifications. The intent of the development team is expressed in natural language ("**intent-driven development**"), design assets, core principles and other guidelines. The **lingua franca** of development moves to a higher level, and code is the last-mile approach.

Debugging means fixing specifications and their implementation plans that generate incorrect code. Refactoring means restructuring for clarity. The entire development workflow reorganizes around specifications as the central source of truth, with implementation plans and code as the continuously regenerated output. Updating apps with new features or creating a new parallel implementation because we are creative beings, means revisiting the specification and creating new implementation plans. This process is therefore a 0 -> 1, (1', ..), 2, 3, N.

The development team focuses in on their creativity, experimentation, their critical thinking.

## The Spec Kitty Philosophy: Code as Source of Truth

**This is where Spec Kitty diverges from traditional spec-driven development.**

In Spec Kitty, **CODE IS THE SOURCE OF TRUTH** - it represents what exists NOW. The specification is NOT a comprehensive digital twin of the codebase. Instead, specifications are **CHANGE REQUESTS** that describe the DELTA between current reality and desired future state.

### Why This Matters

**For LLMs working with Spec Kitty:**
- **Always read the code** to understand current implementation
- The specification tells you WHAT TO CHANGE, not what currently exists
- Don't assume the spec documents the entire system
- Code truth > spec documentation

**For developers:**
- Specs describe "we want to ADD authentication" not "the system includes authentication"
- Specs are forward-looking change requests, not backward-looking documentation
- Keep specs focused on the delta, not comprehensive system documentation
- After merging, the code becomes the new truth; the spec is now historical context

### The Philosophical Break from Spec Kit

**Traditional Spec-Driven Development (Spec Kit approach):**
- Specification attempts to be comprehensive documentation
- Spec describes the entire system state
- Updates try to keep spec in sync with code
- Spec serves as system documentation

**Spec Kitty Philosophy:**
- Code is always the definitive source of truth
- Specifications are change requests (deltas)
- LLMs read code to understand NOW, read specs to understand FUTURE
- Specs become historical record after merge, not living documentation

### Why This Approach Works Better for AI Agents

AI agents have a superpower: **they can read and understand code instantly**. Traditional specs tried to save humans from reading code by documenting everything. But LLMs don't need that protection - they can read thousands of lines of code in seconds.

**Benefits:**
- ✅ Specs stay focused and concise (describe only what changes)
- ✅ No spec drift (specs don't try to track current state)
- ✅ LLMs always work from ground truth (the actual code)
- ✅ Faster development (no comprehensive system documentation needed)
- ✅ Specs accurately describe intent (the delta) not current state

**Example:**

**Traditional approach (Spec Kit):**
```
Specification: "The system has user authentication with email/password,
session management, and password reset. It uses JWT tokens stored in
httpOnly cookies. The UserService handles authentication logic..."
[... 500 lines documenting entire auth system ...]
```

**Spec Kitty approach:**
```
Specification: "Add OAuth2 social login (Google, GitHub) alongside
existing email/password authentication. Keep current JWT session
management unchanged."

Implementation: LLM reads current auth code, understands JWT system,
adds OAuth2 providers as delta to existing system.
```

**The difference:** Spec Kitty specs are concise change requests. LLMs read the codebase to understand context, then implement the specified delta.

## Progress Tracking with Kanban Lanes

Spec Kitty pairs specification rigor with a **lane-based workflow** that keeps the entire team aligned. Every lane transition is appended to the Mission's status event log, giving product owners, reviewers, and AI assistants a single source of truth for progress. Agents coordinate through structured lane commands, and `spec-kitty agent tasks status` highlights blockers, review requests, and idle work packages. This **status board** becomes the heartbeat of the project—drive agent coordination from one place, rebalance workloads, and archive the full timeline for compliance.

## The SDD Workflow in Practice

### Interactive Discovery Comes First

Spec Kitty treats specification and planning as co-creation activities. Every command starts with a mandatory interview that collects goals, users, constraints, quality bars, and risks before any documents are generated. The workflow pauses whenever answers are missing—no assumptions are made on your behalf without explicit confirmation.

**Discovery Gates Enforce Completeness:**

- `/spec-kitty.specify` enters a discovery interview on first invocation, asking one question at a time and blocking with `WAITING_FOR_DISCOVERY_INPUT` until all answers are provided and an Intent Summary is confirmed
- `/spec-kitty.plan` follows the same pattern with `WAITING_FOR_PLANNING_INPUT`, interrogating tech stack, architecture, non-functional requirements, and operational constraints before generating artifacts
- Proportional depth: lightweight features receive lightweight questioning, while complex platform builds demand exhaustive interrogation
- No markdown tables rendered to users—agents track coverage internally and present one focused question per turn

The workflow begins with an idea—often vague and incomplete. Through iterative dialogue with AI, this idea becomes a comprehensive PRD. The AI asks clarifying questions, identifies edge cases, and helps define precise acceptance criteria. What might take days of meetings and documentation in traditional development happens in hours of focused specification work. This transforms the traditional SDLC—requirements and design become continuous activities rather than discrete phases. This is supportive of a **team process**, where team-reviewed specifications are expressed and versioned, created in branches, and merged.

When a product manager updates acceptance criteria, implementation plans automatically flag affected technical decisions. When an architect discovers a better pattern, the PRD updates to reflect new possibilities.

Throughout this specification process, research agents gather critical context. They investigate library compatibility, performance benchmarks, and security implications. Organizational constraints are discovered and applied automatically—your company's database standards, authentication requirements, and deployment policies seamlessly integrate into every specification.

From the PRD, AI generates implementation plans that map requirements to technical decisions. Every technology choice has documented rationale. Every architectural decision traces back to specific requirements. Throughout this process, consistency validation continuously improves quality. AI analyzes specifications for ambiguity, contradictions, and gaps—not as a one-time gate, but as an ongoing refinement.

Code generation begins as soon as specifications and their implementation plans are stable enough, but they do not have to be "complete." Early generations might be exploratory—testing whether the specification makes sense in practice. Domain concepts become data models. User stories become API endpoints. Acceptance scenarios become tests. This merges development and testing through specification—test scenarios aren't written after code, they're part of the specification that generates both implementation and tests.

The feedback loop extends beyond initial development. Production metrics and incidents don't just trigger hotfixes—they update specifications for the next regeneration. Performance bottlenecks become new non-functional requirements. Security vulnerabilities become constraints that affect all future generations. This iterative dance between specification, implementation, and operational reality is where true understanding emerges and where the traditional SDLC transforms into a continuous evolution.

## Why SDD Matters Now

Three trends make SDD not just possible but necessary:

First, AI capabilities have reached a threshold where natural language specifications can reliably generate working code. This isn't about replacing developers—it's about amplifying their effectiveness by automating the mechanical translation from specification to implementation. It can amplify exploration and creativity, support "start-over" easily, and support addition, subtraction, and critical thinking.

Second, software complexity continues to grow exponentially. Modern systems integrate dozens of services, frameworks, and dependencies. Keeping all these pieces aligned with original intent through manual processes becomes increasingly difficult. SDD provides systematic alignment through specification-driven generation. Frameworks may evolve to provide AI-first support, not human-first support, or architect around reusable components.

Third, the pace of change accelerates. Requirements change far more rapidly today than ever before. Pivoting is no longer exceptional—it's expected. Modern product development demands rapid iteration based on user feedback, market conditions, and competitive pressures. Traditional development treats these changes as disruptions. Each pivot requires manually propagating changes through documentation, design, and code. The result is either slow, careful updates that limit velocity, or fast, reckless changes that accumulate technical debt.

SDD can support what-if/simulation experiments: "If we need to re-implement or change the application to promote a business need to sell more T-shirts, how would we implement and experiment for that?"

SDD transforms requirement changes from obstacles into normal workflow. When specifications drive implementation, pivots become systematic regenerations rather than manual rewrites. Change a core requirement in the PRD, and affected implementation plans update automatically. Modify a user story, and corresponding API endpoints regenerate. This isn't just about initial development—it's about maintaining engineering velocity through inevitable changes.

## Core Principles

**Specifications as the Lingua Franca**: The specification becomes the primary artifact. Code becomes its expression in a particular language and framework. Maintaining software means evolving specifications.

**Executable Specifications**: Specifications must be precise, complete, and unambiguous enough to generate working systems. This eliminates the gap between intent and implementation.

**Continuous Refinement**: Consistency validation happens continuously, not as a one-time gate. AI analyzes specifications for ambiguity, contradictions, and gaps as an ongoing process.

**Research-Driven Context**: Research agents gather critical context throughout the specification process, investigating technical options, performance implications, and organizational constraints.

**Bidirectional Feedback**: Production reality informs specification evolution. Metrics, incidents, and operational learnings become inputs for specification refinement.

**Branching for Exploration**: Generate multiple implementation approaches from the same specification to explore different optimization targets—performance, maintainability, user experience, cost.

## Implementation Approaches

Today, practicing SDD requires assembling existing tools and maintaining discipline throughout the process. The methodology can be practiced with:

- AI assistants for iterative specification development
- Research agents for gathering technical context
- Code generation tools for translating specifications to implementation
- Version control systems adapted for specification-first workflows
- Consistency checking through AI analysis of specification documents

The key is treating specifications as the source of truth, with code as the generated output that serves the specification rather than the other way around.

## Streamlining SDD with Commands

The SDD methodology is significantly enhanced through three powerful commands that automate the specification → planning → tasking workflow:

### The `/spec-kitty.specify` Command

This command transforms a simple feature description (the user-prompt) into a complete, structured specification with automatic repository management:

1. **Automatic Feature Numbering**: Scans existing specs to determine the next feature number (e.g., 001, 002, 003)
2. **Branch Creation**: Generates a semantic branch name from your description and creates it automatically
3. **Dedicated Worktree**: Spawns an isolated checkout under `.worktrees/<feature-slug>` so each feature has its own sandbox without disturbing other branches
4. **Template-Based Generation**: Copies and customizes the feature specification template with your requirements
5. **Directory Structure**: Creates the proper `kitty-specs/[branch-name]/` structure for all related documents

After the command finishes, switch your shell into the new worktree (e.g., `cd .worktrees/003-chat-system`) before running planning or implementation commands. If your environment can’t access the `.worktrees/` directory, the CLI falls back to the legacy single-worktree flow so you can keep working.

### The `/spec-kitty.plan` Command

Once a feature specification exists, this command creates a comprehensive implementation plan:

1. **Specification Analysis**: Reads and understands the feature requirements, user stories, and acceptance criteria
2. **Charteral Compliance**: Ensures alignment with project charter and architectural principles
3. **Technical Translation**: Converts business requirements into technical architecture and implementation details
4. **Detailed Documentation**: Generates supporting documents for data models, API contracts, and test scenarios
5. **Research Kickoff**: Generates and extends `research.md` itself during Phase 0 (any discovery findings captured earlier via `/spec-kitty.research` are extended, not replaced), so Phase 0 artifacts exist before task generation
6. **Agent Context Refresh**: Reminds you to run `.kittify/scripts/bash/update-agent-context.sh __AGENT__` so Claude, Cursor, Gemini, and other assistants receive the latest architectural decisions
7. **Quickstart Validation**: Produces a quickstart guide capturing key validation scenarios

### The `/spec-kitty.tasks` Command

After a plan is created **and Phase 0 research is complete**, this command analyzes the plan and related design documents to generate both the executable task list *and* the kanban-ready prompt bundles:

1. **Inputs**: Reads `plan.md` (required) and, if present, `data-model.md`, `contracts/`, `research.md` (captured during discovery and extended by the plan step), and `quickstart.md`.
2. **Task Derivation**: Converts contracts, entities, and scenarios into fine-grained subtasks (`Txxx`), marking safe parallelization with `[P]`.
3. **Work-package grouping**: Rolls the subtasks into at most ten work packages (`WPxx`), each aligned with a user story or cohesive subsystem so teams can deliver in independent slices.
4. **Prompt Generation**: Creates work package prompt files in flat `tasks/` directory using the bundle template (complete with metadata and implementation detail), sets `lane: "planned"` in frontmatter, and links each package from `tasks.md`.
5. **Outputs**: Produces `tasks.md` plus WP prompt files in flat `tasks/` directory with `lane: "planned"` so implementers can use workflow commands to start building.

### The `/spec-kitty.review` Command

Provides a structured hand-off gate for work packages with `lane: "for_review"`:

1. **Selection**: Auto-detects first WP with `lane: "for_review"` (or accepts an explicit WP ID passed through the slash command).
2. **Auto-move to doing**: Moves WP to `lane: "doing"` and displays full prompt with review instructions.
3. **Deep Review**: Agent reviews prompt, supporting docs, and code changes before rendering findings.
4. **Decision Flow**: Agent uses workflow commands to update `lane` to "done" (approved) or "planned" (changes requested), which records the transition (with agent + PID data) in `status.events.jsonl`.
4. **Automation Hooks**: Invokes helper scripts to flip task checkboxes in `tasks.md` when review passes, keeping status in sync with the kanban board.

### The `/spec-kitty.accept` Command

Use this command after every work package is in `tasks/done/` and the checklist is complete:

1. **Readiness Checks**: Confirms no work packages remain in `planned`, `doing`, or `for_review`; validates frontmatter metadata (`lane`, `agent`, `assignee`, `shell_pid`) and ensures the status event log has an entry for each lane transition.
2. **Artifact Audit**: Verifies `spec.md`, `plan.md`, `tasks.md`, and supporting documents are present and free from `NEEDS CLARIFICATION` markers; confirms all checkboxes in `tasks.md` are checked.
3. **Acceptance Metadata**: Records timestamp, actor, mode, and parent commit in `kitty-specs/<feature>/meta.json`, creating an acceptance commit unless run in dry-run mode.
4. **Guidance Output**: Produces merge instructions for either hosted PRs or local merges, plus cleanup commands to remove the feature worktree and branch once merged.

`/spec-kitty.implement` and `/spec-kitty.accept` both assume you are operating from that feature’s worktree. If you drift back to the repo root, `cd .worktrees/<feature-slug>` (or recreate the worktree with `git worktree add`) before moving prompts or running acceptance.

`/spec-kitty.accept` is also exposed as `spec-kitty accept`, so the same workflow is available from the terminal with optional `--json`, `--mode`, and `--no-commit` switches.

### The `/spec-kitty.implement` Workflow: Kanban Discipline

The implementation command enforces a rigorous task workflow that ensures traceability and prevents work from stalling:

**Mandatory Initialization (Blocking):**

Before any coding begins, `/spec-kitty.implement` requires each work package to transition through lanes with full metadata tracking:

1. **Move prompt to doing lane**: Use `spec-kitty agent action implement WPxx` (workflow command handles this automatically)
2. **Update frontmatter metadata**:
   ```yaml
   lane: "doing"
   assignee: "Agent Name"
   agent: "claude"  # or codex, gemini, copilot, etc.
   shell_pid: "12345"  # from echo $$
   ```
3. **Record the lane transition**: The status event log (`status.events.jsonl`) gets a timestamped event; add context with `spec-kitty agent tasks add-history WPxx --note "..."`
4. **Commit the move**: Preserve git history of the workflow transition

**Validation Checkpoint:**

The agent must verify before proceeding to implementation:
- Prompt file exists in flat `tasks/` directory
- Frontmatter shows `lane: "doing"`
- `shell_pid` is captured
- `spec-kitty agent tasks status` shows the WP as `in_progress`
- Changes are committed to git

**Automation Helpers:**

Spec Kitty ships with helper scripts to streamline the workflow:

- `spec-kitty agent action implement WPxx` – Modern workflow command that auto-advances lanes (planned → doing → for_review)
- `spec-kitty agent tasks add-history WPxx --note "Resumed after dependency install"` – Records a history note in the status event log without moving lanes.
- `.kittify/scripts/bash/tasks-list-lanes.sh FEATURE-SLUG` – Shows the current lane, agent, and assignee for every work package.
- `.kittify/scripts/bash/tasks-rollback-move.sh FEATURE-SLUG WPxx` – Returns a prompt to its previous lane if a move was made in error.
- `scripts/bash/validate-task-workflow.sh WPxx kitty-specs/FEATURE` – Validates prompt is in correct lane with required metadata before implementation starts.
- `scripts/git-hooks/pre-commit-task-workflow.sh` – Optional git hook to enforce lane metadata in commits.

**Completion Flow:**

After implementing the work package, the agent must:

1. Record a completion note: `spec-kitty agent tasks add-history WPxx --note "..."`
2. Move to review: Use `spec-kitty agent action implement WPxx` (auto-advances to for_review when work complete)
3. Update frontmatter: `lane: "for_review"`
4. Optionally add a review-ready history note with `add-history`
5. Commit the transition

This discipline ensures:
- **Full traceability**: Every work package has complete history of who worked on it, when, and in which environment (shell_pid)
- **No stalled work**: Prompts can't languish in doing without accountability
- **Clear handoffs**: Review gates enforce quality checks before work is marked complete
- **Parallel workflow visibility**: Multiple agents can work simultaneously, each with their own shell_pid tracking

### Example: Building a Chat Feature

Here's how these commands transform the traditional development workflow:

**Traditional Approach:**

```text
1. Write a PRD in a document (2-3 hours)
2. Create design documents (2-3 hours)
3. Set up project structure manually (30 minutes)
4. Write technical specifications (3-4 hours)
5. Create test plans (2 hours)
Total: ~12 hours of documentation work
```

**SDD with Commands Approach:**

```bash
# Step 1: Create the feature specification (5 minutes)
/spec-kitty.specify Real-time chat system with message history and user presence

# This automatically:
# - Creates branch "003-chat-system"
# - Generates kitty-specs/003-chat-system/spec.md
# - Populates it with structured requirements

# Step 2: Generate implementation plan (5 minutes)
/spec-kitty.plan WebSocket for real-time messaging, PostgreSQL for history, Redis for presence

# Step 3: Generate executable tasks (5 minutes)
/spec-kitty.tasks

# This automatically creates:
# - kitty-specs/003-chat-system/plan.md
# - kitty-specs/003-chat-system/research.md (WebSocket library comparisons)
# - kitty-specs/003-chat-system/data-model.md (Message and User schemas)
# - kitty-specs/003-chat-system/contracts/ (WebSocket events, REST endpoints)
# - kitty-specs/003-chat-system/quickstart.md (Key validation scenarios)
# - kitty-specs/003-chat-system/tasks.md (Work packages with subtasks)
# - kitty-specs/003-chat-system/tasks/WP0x-*.md (Prompt bundles in flat directory, lane: "planned" in frontmatter)
```

In 15 minutes, you have:

- A complete feature specification with user stories and acceptance criteria
- A detailed implementation plan with technology choices and rationale
- API contracts and data models ready for code generation
- Comprehensive test scenarios for both automated and manual testing
- All documents properly versioned in a topic branch

### The Power of Structured Automation

These commands don't just save time—they enforce consistency and completeness:

1. **No Forgotten Details**: Templates ensure every aspect is considered, from non-functional requirements to error handling
2. **Traceable Decisions**: Every technical choice links back to specific requirements
3. **Living Documentation**: Specifications stay in sync with code because they generate it
4. **Rapid Iteration**: Change requirements and regenerate plans in minutes, not days

The commands embody SDD principles by treating specifications as executable artifacts rather than static documents. They transform the specification process from a necessary evil into the driving force of development.

### Template-Driven Quality: How Structure Constrains LLMs for Better Outcomes

The true power of these commands lies not just in automation, but in how the templates guide LLM behavior toward higher-quality specifications. The templates act as sophisticated prompts that constrain the LLM's output in productive ways:

#### 1. **Preventing Premature Implementation Details**

The feature specification template explicitly instructs:

```text
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
```

This constraint forces the LLM to maintain proper abstraction levels. When an LLM might naturally jump to "implement using React with Redux," the template keeps it focused on "users need real-time updates of their data." This separation ensures specifications remain stable even as implementation technologies change.

#### 2. **Forcing Explicit Uncertainty Markers**

Both templates mandate the use of `[NEEDS CLARIFICATION]` markers:

```text
When creating this spec from a user prompt:
1. **Mark all ambiguities**: Use [NEEDS CLARIFICATION: specific question]
2. **Don't guess**: If the prompt doesn't specify something, mark it
```

This prevents the common LLM behavior of making plausible but potentially incorrect assumptions. Instead of guessing that a "login system" uses email/password authentication, the LLM must mark it as `[NEEDS CLARIFICATION: auth method not specified - email/password, SSO, OAuth?]`.

#### 3. **Structured Thinking Through Checklists**

The templates include comprehensive checklists that act as "unit tests" for the specification:

```markdown
### Requirement Completeness
- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Success criteria are measurable
```

These checklists force the LLM to self-review its output systematically, catching gaps that might otherwise slip through. It's like giving the LLM a quality assurance framework.

#### 4. **Charteral Compliance Through Gates**

The implementation plan template enforces architectural principles through phase gates:

```markdown
### Phase -1: Pre-Implementation Gates
#### Simplicity Gate (Article VII)
- [ ] Using ≤3 projects?
- [ ] No future-proofing?
#### Anti-Abstraction Gate (Article VIII)
- [ ] Using framework directly?
- [ ] Single model representation?
```

These gates prevent over-engineering by making the LLM explicitly justify any complexity. If a gate fails, the LLM must document why in the "Complexity Tracking" section, creating accountability for architectural decisions.

#### 5. **Hierarchical Detail Management**

The templates enforce proper information architecture:

```text
**IMPORTANT**: This implementation plan should remain high-level and readable.
Any code samples, detailed algorithms, or extensive technical specifications
must be placed in the appropriate `implementation-details/` file
```

This prevents the common problem of specifications becoming unreadable code dumps. The LLM learns to maintain appropriate detail levels, extracting complexity to separate files while keeping the main document navigable.

#### 6. **Test-First Thinking**

The implementation template enforces test-first development:

```text
### File Creation Order
1. Create `contracts/` with API specifications
2. Create test files in order: contract → integration → e2e → unit
3. Create source files to make tests pass
```

This ordering constraint ensures the LLM thinks about testability and contracts before implementation, leading to more robust and verifiable specifications.

#### 7. **Preventing Speculative Features**

Templates explicitly discourage speculation:

```text
- [ ] No speculative or "might need" features
- [ ] All phases have clear prerequisites and deliverables
```

This stops the LLM from adding "nice to have" features that complicate implementation. Every feature must trace back to a concrete user story with clear acceptance criteria.

### The Compound Effect

These constraints work together to produce specifications that are:

- **Complete**: Checklists ensure nothing is forgotten
- **Unambiguous**: Forced clarification markers highlight uncertainties
- **Testable**: Test-first thinking baked into the process
- **Maintainable**: Proper abstraction levels and information hierarchy
- **Implementable**: Clear phases with concrete deliverables

The templates transform the LLM from a creative writer into a disciplined specification engineer, channeling its capabilities toward producing consistently high-quality, executable specifications that truly drive development.

## The Charteral Foundation: Enforcing Architectural Discipline

At the heart of SDD lies a charter—a set of immutable principles that govern how specifications become code. The charter (`.kittify/charter/charter.md`) acts as the architectural DNA of the system, ensuring that every generated implementation maintains consistency, simplicity, and quality.

### The Core Articles of Development

The charter defines several core articles that shape every aspect of the development process:

#### Article I: Library-First Principle

Every feature must begin as a standalone library—no exceptions. This forces modular design from the start:

```text
Every feature in Specify MUST begin its existence as a standalone library.
No feature shall be implemented directly within application code without
first being abstracted into a reusable library component.
```

This principle ensures that specifications generate modular, reusable code rather than monolithic applications. When the LLM generates an implementation plan, it must structure features as libraries with clear boundaries and minimal dependencies.

#### Article II: CLI Interface Mandate

Every library must expose its functionality through a command-line interface:

```text
All CLI interfaces MUST:
- Accept text as input (via stdin, arguments, or files)
- Produce text as output (via stdout)
- Support JSON format for structured data exchange
```

This enforces observability and testability. The LLM cannot hide functionality inside opaque classes—everything must be accessible and verifiable through text-based interfaces.

#### Article III: Test-First Imperative

The most transformative article—no code before tests:

```text
This is NON-NEGOTIABLE: All implementation MUST follow strict Test-Driven Development.
No implementation code shall be written before:
1. Unit tests are written
2. Tests are validated and approved by the user
3. Tests are confirmed to FAIL (Red phase)
```

This completely inverts traditional AI code generation. Instead of generating code and hoping it works, the LLM must first generate comprehensive tests that define behavior, get them approved, and only then generate implementation.

#### Articles VII & VIII: Simplicity and Anti-Abstraction

These paired articles combat over-engineering:

```text
Section 7.3: Minimal Project Structure
- Maximum 3 projects for initial implementation
- Additional projects require documented justification

Section 8.1: Framework Trust
- Use framework features directly rather than wrapping them
```

When an LLM might naturally create elaborate abstractions, these articles force it to justify every layer of complexity. The implementation plan template's "Phase -1 Gates" directly enforce these principles.

#### Article IX: Integration-First Testing

Prioritizes real-world testing over isolated unit tests:

```text
Tests MUST use realistic environments:
- Prefer real databases over mocks
- Use actual service instances over stubs
- Contract tests mandatory before implementation
```

This ensures generated code works in practice, not just in theory.

### Charteral Enforcement Through Templates

The implementation plan template operationalizes these articles through concrete checkpoints:

```markdown
### Phase -1: Pre-Implementation Gates
#### Simplicity Gate (Article VII)
- [ ] Using ≤3 projects?
- [ ] No future-proofing?

#### Anti-Abstraction Gate (Article VIII)
- [ ] Using framework directly?
- [ ] Single model representation?

#### Integration-First Gate (Article IX)
- [ ] Contracts defined?
- [ ] Contract tests written?
```

These gates act as compile-time checks for architectural principles. The LLM cannot proceed without either passing the gates or documenting justified exceptions in the "Complexity Tracking" section.

### The Power of Immutable Principles

The charter's power lies in its immutability. While implementation details can evolve, the core principles remain constant. This provides:

1. **Consistency Across Time**: Code generated today follows the same principles as code generated next year
2. **Consistency Across LLMs**: Different AI models produce architecturally compatible code
3. **Architectural Integrity**: Every feature reinforces rather than undermines the system design
4. **Quality Guarantees**: Test-first, library-first, and simplicity principles ensure maintainable code

### Charteral Evolution

While principles are immutable, their application can evolve:

```text
Section 4.2: Amendment Process
Modifications to this charter require:
- Explicit documentation of the rationale for change
- Review and approval by project maintainers
- Backwards compatibility assessment
```

This allows the methodology to learn and improve while maintaining stability. The charter shows its own evolution with dated amendments, demonstrating how principles can be refined based on real-world experience.

### Beyond Rules: A Development Philosophy

The charter isn't just a rulebook—it's a philosophy that shapes how LLMs think about code generation:

- **Observability Over Opacity**: Everything must be inspectable through CLI interfaces
- **Simplicity Over Cleverness**: Start simple, add complexity only when proven necessary
- **Integration Over Isolation**: Test in real environments, not artificial ones
- **Modularity Over Monoliths**: Every feature is a library with clear boundaries

By embedding these principles into the specification and planning process, SDD ensures that generated code isn't just functional—it's maintainable, testable, and architecturally sound. The charter transforms AI from a code generator into an architectural partner that respects and reinforces system design principles.

## The Transformation

This isn't about replacing developers or automating creativity. It's about amplifying human capability by automating mechanical translation. It's about creating a tight feedback loop where specifications, research, and code evolve together, each iteration bringing deeper understanding and better alignment between intent and implementation.

Software development needs better tools for maintaining alignment between intent and implementation. SDD provides the methodology for achieving this alignment through executable specifications that generate code rather than merely guiding it.

## Glossary: requirement identifiers

### Requirement ID

| | |
|---|---|
| **Definition** | A stable identifier for one spec requirement: a kind (`FR`, `NFR`, `C`, or `SC`), a digit string whose width is significant, an optional single lowercase letter suffix, and an optional `<mission-slug>#` qualifier; canonical form is kind uppercase, digits verbatim, suffix lowercase. |
| **Context** | Spec-Driven Development |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The identifier is an implementation-concern ID (`IC-##`, a separate plan-level grammar; see the linked ADR below), or a work package ID. |
| **Related terms** | [Success criterion](#success-criterion), [Qualified citation](#qualified-citation), [work package](./orchestration.md#work-package), [Mission](./orchestration.md#mission), the single-grammar-authority ADR (`../adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md`) |

---

### Success criterion

| | |
|---|---|
| **Definition** | A measurable outcome a spec declares with the `SC` kind. It is a Requirement ID that is tracked (reported in finalize-tasks' informational success-criteria coverage) but not gating: an undeclared `SC` ref cited on a work package still fails as `unknown_spec_id`. |
| **Context** | Spec-Driven Development |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The concept is an acceptance scenario of a user story, or a functional requirement whose mapping is coverage-gated. |
| **Related terms** | [Requirement ID](#requirement-id), [Qualified citation](#qualified-citation) |

---

### Qualified citation

| | |
|---|---|
| **Definition** | A Requirement ID prefixed with another mission's slug and `#` (`<mission-slug>#FR-###`). It belongs to the named mission, is never declared, required, flagged, or warned about, and is reported as `foreign_qualified` (never failing) when cited in a work package's refs; the qualifier itself is never resolved. |
| **Context** | Spec-Driven Development |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | Citing a GitHub issue reference (`#` plus digits) or a file path. |
| **Related terms** | [Requirement ID](#requirement-id), [Success criterion](#success-criterion), the single-grammar-authority ADR (`../adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md`) |
