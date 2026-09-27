---
title: The Mission System Explained
description: "Why mission types exist and how they nest: the Mission Type, Mission, work package, and Workspace hierarchy, the four blueprints, and the two state machines next coordinates."
doc_status: active
updated: '2026-09-27'
related:
- docs/architecture/divio-documentation.md
- docs/architecture/kanban-workflow.md
- docs/architecture/mission-type-resolution.md
- docs/architecture/spec-driven-development.md
---
# The Mission System Explained

Spec Kitty's mission system lets you choose a workflow blueprint optimized for your type of work. This document explains why mission types exist, how they shape your experience, and how the pieces fit together.

Terminology note:
- `Mission Type` = reusable blueprint such as `software-dev` or `research`
- `Mission` = concrete tracked item under `kitty-specs/<mission-slug>/`
- `Mission Run` = runtime/session instance
- `Feature` = software-dev compatibility alias for a mission

**3.1.0 naming updates**: The `--mission` flag is now canonical on all commands that previously used `--feature` (e.g., `spec-kitty implement`, `spec-kitty merge`, `spec-kitty next`). `--feature` was a hidden deprecated compatibility alias; as of 3.2.x it has been **removed everywhere** — from the internal/agent command cluster (`agent status/tasks/action/context/mission`, `charter lint`, `materialize`, `validate-encoding`, `validate-tasks`, `verify`; #1060-A) and from the user-facing top-level commands (`implement`, `merge`, `next`, `research`, `context`, `accept`, `lifecycle`, `mission_type`; #1060). `--mission` is now the sole selector; passing `--feature` exits with `No such option`. Additionally, `spec-kitty constitution` has been renamed to `spec-kitty charter`; the old command name no longer exists.

## Why Different Missions?

Not all projects are the same:

| Work Type | Primary Goal | Key Activities |
|-----------|--------------|----------------|
| **Software development** | Working code | Write tests, implement features, review code |
| **Research** | Validated findings | Collect evidence, analyze data, synthesize conclusions |
| **Planning** | Actionable plan | Define architecture, map dependencies, write roadmaps |
| **Documentation** | Clear docs | Audit gaps, create content, validate accessibility |

A workflow designed for software development doesn't fit research:
- "All tests pass" makes no sense for a literature review
- "Documented sources" isn't relevant for code implementation
- Phases like "gather data" don't apply to feature development

Mission types solve this by providing domain-specific workflows, validation rules, and artifacts.

## The Hierarchy: Mission Type, Mission, work package, Workspace

Understanding how the pieces nest together is key to understanding Spec Kitty.

```
Mission Type (reusable workflow blueprint, e.g. software-dev)
  |
  +-- Mission (concrete tracked item)
  |     kitty-specs/042-auth-system/
  |       meta.json        <-- links mission to mission type + target branch
  |       spec.md          <-- what we're building
  |       plan.md          <-- how we'll build it
  |       tasks.md         <-- WP breakdown
  |       tasks/
  |         WP01.md        <-- work package prompt
  |         WP02.md
  |         WP03.md
  |           |
  |           +-- Execution Workspace (.worktrees/042-auth-system-lane-a/)
  |                 isolated git worktree resolved for this WP
```

**Mission Type** -- A reusable workflow blueprint. It defines the steps (each carrying its prompt and content templates), the expected artifacts, and the guards. You never edit mission types directly; you select one when starting a mission.

**Mission** -- A concrete tracked item, stored in `kitty-specs/###-name/`. Each mission is linked to exactly one mission type via its `meta.json` file. Different missions in the same project can use different mission types.

**Feature** -- Compatibility alias for a software-delivery mission. In software-dev contexts you will still see `feature` on legacy commands and filesystem fields.

**work package (WP)** -- One parallelizable slice of work within a mission. Each WP has its own markdown prompt file (`tasks/WP01.md`), its own status on the kanban board, and its own dependencies on other WPs.

**Workspace** -- An isolated git worktree where a single WP is implemented. Each workspace has its own branch, its own working directory, and its own agent. Multiple workspaces can run in parallel.

### meta.json: The Mission-to-Mission-Type Link

Every mission directory contains a `meta.json` that records which mission type it uses:

```json
{
  "feature_number": "042",
  "slug": "042-auth-system",
  "mission": "software-dev",
  "target_branch": "main",
  "created_at": "2026-03-22T10:00:00Z",
  "vcs": "git"
}
```

The `mission` field determines which templates, guards, and validation rules apply. If omitted, it defaults to `software-dev`. The key name is historical; the stored value is the mission type.

Different missions can use different mission types simultaneously:
- `kitty-specs/042-auth-system/` -- mission type `software-dev`
- `kitty-specs/043-market-analysis/` -- mission type `research`
- `kitty-specs/044-api-docs/` -- mission type `documentation`
- `kitty-specs/045-roadmap/` -- mission type `plan`

## Mission Types Are Doctrine Artifacts

A mission type is not hardcoded into the runtime — it is a **doctrine-defined
artifact**. The canonical catalogue lives in `packs/built-in/missions/<type>/`,
where each type *offers* its governance, action indices, step contracts, and
templates. The runtime is a finite-state machine that reads the *resolved* mission
type keyed off the `mission` field in `meta.json`; it holds no per-type knowledge
of its own.

The `MissionType` doctrine artifact is **load-bearing**: it is the single source of
truth for *"what is this mission type, what steps does it contain, and what gates
are checked?"* The end-state retires the derived `src/specify_cli/missions/` copies
entirely — the doctrine path (much of it a dead read-path today) goes live and the
`specify_cli` copies are removed in a **user-invisible swap**, verified during
migration by transitional parity scaffolds that are then deleted (no surviving
parity ratchet). #883 is slice 1: governance and the dossier gate reader.

### software-dev is a peer, not a special case

Historically `software-dev` was the default and carried hardcoded status woven
through the core loop. The direction now is that `software-dev` is an ordinary
built-in doctrine mission type on equal footing with `documentation`, `research`,
and `plan`. Its behaviour resolves from `meta.json` through the same path as the
other three, with no `software-dev-default` special-casing. `software-dev` remains
the fallback mission type when `meta.json` omits the `mission` field, but that
fallback governs only template-file selection — it no longer leaks software-dev
*governance* onto non-software missions. See
[Mission-Type Resolution](mission-type-resolution.md) for the seam that makes this
so, and [ADR 2026-07-14-2](../adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md)
for the decision.

### The dual missions tree and its retirement trajectory

Two mission trees exist today:

| Tree | Role |
|------|------|
| `packs/built-in/missions/<type>/` | **Canonical** — the source of truth for mission-type behaviour |
| `src/specify_cli/missions/<type>/` | **Derived copies** that a shrinking set of core readers still bind to directly |

The derived tree is **on the deprecation path**, not to be entrenched: no new
content is added to it, and no "keep the trees in sync" guard is introduced (that
would entrench the split). The direction is derive-then-delete — each reader is
migrated to the doctrine tree one slice at a time, after which the derived copies
and finally the copy step are removed. The first migration (planned as slice 1 of
this retirement — issue #883) flips the dossier gate reader to the doctrine-tree
source. Later slices migrate templates, gates, and step contracts before the
`specify_cli/missions/` tree is deleted outright.

## How Missions Work

### Selected When Creating a Mission During /spec-kitty.specify

When you run `/spec-kitty.specify`, Spec Kitty prompts for the mission type that will back the new mission:

```
? Select mission type:
  Software Dev Kitty - Build high-quality software with structured workflows
  Deep Research Kitty - Conduct systematic research with evidence synthesis
  Plan Kitty - Goal-oriented planning with iterative refinement
  Documentation Kitty - Create high-quality documentation following Divio principles
```

That choice determines:
- Workflow phases (the steps you go through)
- Required artifacts (the files you produce)
- Guards (conditions that must be met to advance)
- Agent context (personality and instructions for AI agents)

The mission type is locked in when the mission is created and cannot be changed afterwards.

### Two State Machines Working Together

Missions involve two orthogonal state machines that work in tandem:

**Mission action state** -- which outer lifecycle action are we in?
```
discovery --> specify --> plan --> tasks --> implement --> review --> accept
```
Managed by the mission type's step DAG and `spec-kitty next`.

**WP status** -- where is each work package in its lifecycle?
```
planned --> claimed --> in_progress --> for_review --> in_review --> approved --> done
```
Managed by the status model (append-only event log).

Together they determine what `spec-kitty next` returns: "We're in the implement action, WP01 is approved, WP02 is in_progress, WP03 is planned -- your next action is implement WP03."

## The Four Built-In Missions

### software-dev (default)

Full software development lifecycle with work packages and code review.

**Step sequence:**
```
discovery --> specify --> plan --> tasks_outline --> tasks_packages --> tasks_finalize --> implement --> review --> accept
```

**Required artifacts:** `spec.md`, `plan.md`, `tasks.md`

**Guards:**

| Transition | What must be true |
|---|---|
| specify --> plan | `spec.md` must exist |
| plan --> implement | `plan.md` and `tasks.md` must exist |
| implement --> review | All WPs must be `approved` or `done` |
| review --> accept | Review must be approved |

**Agent context:** TDD practices, library-first architecture, tests before code.

**Use when:** Building software missions such as features, fixing bugs, or refactoring code.

### research

Systematic research with evidence-gated transitions.

**Step sequence (state machine with loop):**
```
scoping --> methodology --> gathering <--> synthesis --> output --> done
```
The `gathering <--> synthesis` loop allows iterative evidence collection. You can go back to gathering more data after an initial synthesis pass.

**Required artifacts:** `spec.md`, `plan.md`, `tasks.md`, `findings.md`

**Guards:**

| Transition | What must be true |
|---|---|
| scoping --> methodology | Scope document (`spec.md`) must exist |
| methodology --> gathering | Methodology plan (`plan.md`) must exist |
| gathering --> synthesis | At least 3 sources documented |
| synthesis --> output | Findings document must exist |
| output --> done | Publication approved |

**Special:** Source tracking in `source-register.csv`, evidence in `evidence-log.csv`.

**Agent context:** Research integrity, methodological rigor, evidence documentation.

**Use when:** Investigating technologies, evaluating options, conducting literature reviews, competitive analysis -- any work requiring structured evidence gathering.

### plan

Goal-oriented planning with iterative refinement.

**Step sequence (runtime DAG):**
```
specify --> research --> plan --> review
```

**State machine (v1):**
```
goals --> research --> structure --> draft --> review --> done
```

Produces planning artifacts (architecture documents, roadmaps, design proposals) without implementation.

**Required artifacts:** `goals.md`, `plan.md`

**Guards:**
- `goals → research`: `artifact_exists("goals.md")`
- `research → structure`: `artifact_exists("research.md")`
- `structure → draft`: `artifact_exists("plan.md")`
- `review → done`: `gate_passed("plan_approved")`

**Use when:** Planning architecture, creating roadmaps, designing systems before implementation begins, writing design proposals.

### documentation

Documentation creation following the Divio 4-type system (tutorials, how-to guides, reference, explanations).

**Step sequence:**
```
discover --> audit --> design --> generate --> validate --> publish
```

**Required artifacts:** `spec.md`, `plan.md`, `tasks.md`, `gap-analysis.md`

**Special features:**
- Gap analysis identifies missing documentation by classifying existing docs against the Divio grid
- Supports auto-generation via JSDoc, Sphinx, or rustdoc for API reference docs
- Three iteration modes: initial (from scratch), gap-filling (audit and fill), mission-specific (single component; `feature_specific` accepted as a legacy input alias)

**Guards:** No guards on step transitions. Validation checks run during acceptance: all Divio types valid, no conflicting generators, templates populated (no `[TODO]` markers), gap analysis complete.

**Agent context:** Write the Docs best practices, Divio 4-type system, accessibility and bias-free language.

**Use when:** Writing tutorials, API docs, how-to guides, filling documentation gaps, documenting a specific feature.

## Mission Comparison

| | software-dev | research | plan | documentation |
|---|---|---|---|---|
| **Domain** | Software | Research | Planning | Documentation |
| **Steps** | 9 (DAG) | 6 (state machine) | 4 (linear) | 6 (phases) |
| **Has WP iteration** | Yes | Yes | No | Yes |
| **Has loops** | No | Yes (gather more) | No | No |
| **Default mission** | Yes | No | No | No |

### Required artifacts by mission

| Artifact | software-dev | research | plan | documentation |
|---|:---:|:---:|:---:|:---:|
| `spec.md` | Required | Required | Required | Required |
| `plan.md` | Required | Required | Required | Required |
| `tasks.md` | Required | Required | -- | Required |
| `findings.md` | -- | Required | -- | -- |
| `gap-analysis.md` | -- | -- | -- | Required |

## Which Mission Should I Use?

| If you're... | Use mission | Why |
|---|---|---|
| Building a new feature with code changes | `software-dev` | Full lifecycle with TDD, work packages, code review |
| Fixing a bug or refactoring existing code | `software-dev` | Same lifecycle, just smaller scope |
| Investigating or evaluating technology options | `research` | Evidence-gated transitions ensure rigor |
| Conducting a literature review or competitive analysis | `research` | Source tracking and iterative gathering loops |
| Planning a project roadmap or architecture | `plan` | Lightweight, produces plans without code |
| Designing a system without implementing it yet | `plan` | Four steps, no work packages needed |
| Writing tutorials, API docs, or how-to guides | `documentation` | Divio system ensures comprehensive coverage |
| Filling gaps in existing documentation | `documentation` | Gap analysis mode finds what's missing |

**Commands:**

```bash
# List available missions
spec-kitty mission list

# Start a feature with a specific mission
spec-kitty specify --mission research "What are the best auth patterns?"

# Check which mission a feature uses
cat kitty-specs/<feature-slug>/meta.json
```

## Template Resolution: Customizing Mission Prompts

Each mission provides command templates (the prompts agents see at each step) and content templates (scaffolding for artifacts like spec.md). You can override any template without modifying the package itself.

When a template is needed, Spec Kitty searches three locations in order:

| Priority | Location | Purpose |
|---|---|---|
| 1. Project override | `.kittify/overrides/command-templates/` | Per-project customization |
| 2. Global mission | `~/.kittify/missions/{mission}/command-templates/` | User-wide defaults |
| 3. Package default | (built into spec-kitty) | Ships with the tool |

First match wins. The package default is always the fallback.

**To customize a prompt for your project**, drop a file into `.kittify/overrides/command-templates/`:

```bash
# Copy the default template
cp ~/.kittify/missions/software-dev/command-templates/implement.md \
   .kittify/overrides/command-templates/implement.md

# Edit to taste
vim .kittify/overrides/command-templates/implement.md
```

Your override will be used instead of the package default for that step. Content templates (`templates/`) follow the same resolution chain.

## Guards: What Blocks Step Transitions

Guards are conditions that must be satisfied before a mission can advance to its next step. They prevent you from skipping ahead -- you can't plan without a specification, and you can't review without all work packages completed.

### Common guards you'll encounter

| Guard | What it checks | Example |
|---|---|---|
| Artifact exists | A required file is present | Can't start planning until `spec.md` exists |
| All WPs approved/done | Every work package passed review or is already landed | Can't start acceptance until all WPs are review-approved |
| Gate passed | A named event was recorded | Can't finish until review is approved |
| Source count | Minimum number of evidence sources | Can't synthesize until at least 3 sources documented (research) |

When a guard blocks you, `spec-kitty next` tells you what's missing:

```
Blocked: artifact_exists("spec.md") not satisfied.
Action: Run /spec-kitty.specify to create the specification document.
```

Guards vary by mission. The software-dev mission has guards on most transitions. The plan mission has none -- you advance manually. The research mission uses source-count guards to ensure evidence quality. The documentation mission checks quality during acceptance rather than between steps.

## Mission Templates Per Slash Command

Each mission customizes the slash commands with domain-appropriate prompts:

### /spec-kitty.specify

| Mission | Prompt Focus |
|---------|--------------|
| **Software Dev** | User scenarios and acceptance criteria |
| **Research** | Research question, scope, expected outcomes |
| **Plan** | Goals, constraints, success criteria |
| **Documentation** | Iteration mode, Divio types, target audience |

### /spec-kitty.plan

| Mission | Prompt Focus |
|---------|--------------|
| **Software Dev** | Technical architecture and implementation plan |
| **Research** | Research methodology and data collection strategy |
| **Plan** | Architecture, roadmap, or design structure |
| **Documentation** | Documentation structure and generator configuration |

### /spec-kitty.implement

| Mission | Prompt Focus |
|---------|--------------|
| **Software Dev** | Work packages with TDD workflow |
| **Research** | Data collection, analysis, synthesis tasks |
| **Plan** | (no implementation phase) |
| **Documentation** | Template creation, generator setup, content authoring |

## Per-Feature vs. Global

### Before 0.8.0: Project-Wide Mission

Early versions set the mission at project level:
```
.kittify/
  mission.yaml  # One mission for entire project
```

**Problem**: Real projects need different approaches for different features:
- Feature A is new software development
- Feature B is researching which library to use
- Feature C is writing user documentation

### After 0.8.0: Per-Feature Mission

Now missions are selected per-feature:
```
kitty-specs/
  010-auth-system/
    meta.json  # mission: "software-dev"
  011-library-comparison/
    meta.json  # mission: "research"
  012-user-docs/
    meta.json  # mission: "documentation"
```

**Benefits**:
- Choose the right workflow for each task
- Same project can have software, research, and documentation features
- No need to reconfigure between different types of work

## How Missions Affect Agent Behavior

The `agent_context` field in each mission provides instructions that shape agent behavior:

**Software Dev agent**:
> You are a software development agent following TDD practices. Tests before code (non-negotiable).

**Research agent**:
> You are a research agent conducting systematic literature reviews. Document ALL sources.

**Documentation agent**:
> You are a documentation agent following Write the Docs best practices and Divio system.

These instructions guide AI agents to behave appropriately for the domain.

## See Also

- [Spec-Driven Development](spec-driven-development.md) - The methodology missions implement
- [Mission-Type Resolution](mission-type-resolution.md) - How per-mission-type behaviour resolves through the doctrine → charter → core seam
- [Divio Documentation](divio-documentation.md) - The documentation system used by Documentation Kitty
- [Kanban Workflow](kanban-workflow.md) - How work moves through lanes (applies to all missions)

---

*This document explains why missions exist and how they differ. For how to select and use missions, see the tutorials and how-to guides.*

## Try It

- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## How-To Guides

- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)
- [Use the Dashboard](../guides/how-to/monitoring/use-dashboard.md)

## Reference

- [Missions](../api/missions.md)
- [Slash Commands](../api/slash-commands.md)
