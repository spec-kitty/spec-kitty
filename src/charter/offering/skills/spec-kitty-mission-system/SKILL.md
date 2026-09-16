---
name: spec-kitty-mission-system
description: >-
  Understand how Spec Kitty missions work: the 4 built-in mission types, how
  they define workflows via step contracts and action indices, how missions and
  work packages relate, how templates are resolved through the 6-tier chain,
  and how doctrine artifacts (procedures, tactics, directives) compose mission
  behavior.
  Triggers: "what missions are available", "how do missions work",
  "which mission should I use", "explain the mission system",
  "what is a mission", "change the mission", "mission templates",
  "step contracts", "action index", "mission procedures".
  Does NOT handle: runtime loop advancement (use runtime-next),
  setup or repair (use setup-doctor), governance (use charter-doctrine),
  or glossary curation (use glossary-context).
---

# spec-kitty-mission-system

Understand how missions structure work in Spec Kitty. A mission is a
domain-specific workflow blueprint that defines what steps you go through,
the template each step provides, what artifacts you produce, and how to
validate success.

---

## How Missions Work

### The Core Concept

A mission answers: "What process should we follow to achieve this goal?"

Different goals need different processes. Building a software component is
different from conducting research or writing documentation. Each mission
provides domain-appropriate:

- **Steps** — the ordered phases of work (specify → plan → implement → review); each step provides the prompt/content **template** agents follow
- **Artifacts** — expected outputs (spec.md, plan.md, tasks.md)
- **Guards** — conditions that must be met before advancing (e.g., spec.md must exist before planning)
- **Validation** — checks that verify the output quality
- **Agent context** — personality and instructions for the AI agent

### The Hierarchy: Mission Type → Mission → Work Package → Workspace

```
Mission Type (e.g., software-dev)
  └── Mission (kitty-specs/042-auth-system/)
        ├── meta.json           ← links mission to mission type + target branch
        ├── spec.md             ← what we're building
        ├── plan.md             ← how we'll build it
        ├── tasks.md            ← WP breakdown
        └── tasks/
              ├── WP01.md       ← work package prompt
              ├── WP02.md
              └── WP03.md
                    └── Workspace (.worktrees/042-auth-system-lane-b/)
```

- **Mission Type** = the workflow blueprint (reusable across missions)
- **Mission** = a concrete thing you're building, linked to a mission type via `meta.json`
- **Work Package (WP)** = one parallelizable slice of work within a mission
- **Workspace** = an isolated git worktree owned by one execution lane

### meta.json (Mission → Mission Type Link)

Every mission has a `meta.json` that records which mission type it uses:

```json
{
  "feature_number": "042",
  "slug": "042-auth-system",
  "mission": "software-dev",
  "target_branch": "<target-branch>",
  "created_at": "2026-03-22T10:00:00Z",
  "vcs": "git"
}
```

The `mission` field determines which templates and validation rules
apply. Default is `software-dev` if omitted.

---

## The 4 Built-In Mission Types

### software-dev (default)

Full software development lifecycle with work packages and code review.

**Steps (runtime DAG):**
```
discovery → specify → plan → tasks → implement → review → accept
```

**Required artifacts:** `spec.md`, `plan.md`, `tasks.md`

**Gating:** step ordering comes from the `mission-runtime.yaml` DAG
(`depends_on`); work-package lane transitions are validated by the status
model, and a WP cannot be claimed past its dependencies until each is
`approved` or `done`. Review must be approved before acceptance.

**Agent context:** TDD practices, library-first architecture, tests before code.

**Use when:** Building components, fixing bugs, refactoring code — any work that
produces code changes.

### research

Systematic research with evidence-gated synthesis.

**Steps (runtime DAG):**
```
scoping → methodology → gathering → synthesis → output → accept
```

**Required artifacts:** `spec.md`, `plan.md`, `tasks.md`, `findings.md`

**Gating:** step ordering comes from the `mission-runtime.yaml` DAG
(`depends_on`). The mission expects at least 3 documented sources before
synthesis, and publication is approved at acceptance.

**Special:** Source gathering is iterative — sources are registered as they
are found until the evidence base is sufficient for synthesis. Source tracking
in `source-register.csv`, evidence in `evidence-log.csv`.

**Use when:** Investigating technologies, conducting literature reviews,
evaluating options, any work requiring structured evidence gathering.

### plan

Goal-oriented planning with iterative refinement.

**Steps:**
```
specify → research → plan → review
```

**Use when:** Planning a project, designing architecture, creating roadmaps —
any work that produces planning artifacts but not code.

### documentation

Documentation creation following the Divio 4-type system.

**Workflow phases:**
```
discover → audit → design → generate → validate → publish
```

**Required artifacts:** `spec.md`, `plan.md`, `tasks.md`, `gap-analysis.md`

**Divio types:** Tutorial (learning-oriented), How-To (task-oriented),
Reference (information-oriented), Explanation (understanding-oriented).

**Special:** Supports auto-generation via JSDoc, Sphinx, or rustdoc. Gap
analysis identifies missing documentation by classifying existing docs and
finding coverage gaps.

**Use when:** Creating docs for a project, filling documentation gaps,
documenting a specific component or API.

---

## Mission Type Definition Files

Each mission type lives in `packs/built-in/missions/{mission-key}/` with:

### mission-runtime.yaml (Runtime DAG)

Defines steps as a directed acyclic graph with dependencies:

```yaml
mission:
  key: software-dev
  name: Software Dev Kitty
  version: "2.1.0"

steps:
  - id: specify
    title: Specification
    depends_on: [discovery]
    prompt_template: specify.md
    description: Define user scenarios and acceptance criteria

  - id: plan
    depends_on: [specify]
    prompt_template: plan.md

  - id: implement
    depends_on: [tasks]
    prompt_template: implement.md
```

This is what `spec-kitty next` uses to determine step ordering.

### mission.yaml (Configuration)

Mission configuration: workflow phases, expected artifacts, commands, agent
context, and validation rules. (The former v1 state-machine blocks —
`initial`, `states`, `transitions`, `guards`, `inputs`, `outputs` — were
retired with the mission-DSL v1 runtime in dead-port-disposition-01M1TZVN;
step sequencing is authored in `mission-runtime.yaml` instead.)

```yaml
name: "Software Dev Kitty"
domain: "software"
artifacts:
  required: [spec.md, plan.md, tasks.md]
  optional: [data-model.md, quickstart.md]
workflow:
  phases:
    - name: "research"
    - name: "implement"
    - name: "review"
agent_context: |
  You are a software development agent following TDD practices.
mcp_tools:
  required: [filesystem, git]
  recommended: [code-search, test-runner]
validation:
  checks: [git_clean, all_tests_pass, kanban_complete]
```

### mission-steps/ (Agent Prompts)

Markdown files shown to agents at each step:
- `mission-steps/software-dev/specify/prompt.md` — Instructions for writing the specification
- `mission-steps/software-dev/plan/prompt.md` — Instructions for creating the implementation plan
- `mission-steps/software-dev/tasks/prompt.md` — Instructions for creating tasks and work packages
- `mission-steps/software-dev/implement/prompt.md` — Instructions for implementing a work package
- `mission-steps/software-dev/review/prompt.md` — Instructions for reviewing a work package
- `mission-steps/software-dev/accept/prompt.md` — Instructions for final acceptance validation

### templates/ (Content Templates)

Scaffolding files for artifacts:
- `spec-template.md` — Starting structure for spec.md
- `plan-template.md` — Starting structure for plan.md
- `task-prompt-template.md` — Starting structure for WP prompt files
- `tasks-template.md` — Starting structure for tasks.md

---

## Doctrine Composition Layer

Missions are backed by structured doctrine artifacts that define action
behavior and link to reusable knowledge.

### MissionStepContract (Action Contracts)

Each public action (specify, plan, implement, review) has a step contract
that defines its internal structure:

```yaml
# implement.step-contract.yaml
id: implement
action: implement
mission: software-dev
schema_version: "1.0"
steps:
  - id: setup-workspace
    description: "Create or enter the WP workspace"
  - id: implement-code
    description: "Write code following governance constraints"
    delegates_to:
      kind: tactic
      candidates: [tdd-red-green-refactor, zombies-tdd]
  - id: validate
    description: "Run tests and lint checks"
```

The `delegates_to` field links a step to doctrine artifacts. This is how
mission behavior connects to the knowledge layer: the contract says *what*
to do, the referenced tactic/directive/procedure says *how*.

### Procedure (Reusable Workflow Primitives)

Procedures are multi-step doctrine artifacts with prerequisites and ordered
steps. They are the reusable building blocks that step contracts delegate to.
Each procedure describes a complete mini-workflow (e.g., a refactoring
sequence, a test-first bug fix, a situational assessment).

Procedures live in `packs/built-in/procedures/` (shipped) or
`.kittify/procedures/` (project-local). Access via `DoctrineService`:

```python
procedure = service.procedures.get("refactoring")
# procedure.steps → ordered list of actions
# procedure.prerequisites → what must be true before starting
# All procedures: read packs/built-in/procedures/ or .kittify/procedures/
```

To validate project-layer doctrine artifacts:
```bash
spec-kitty doctrine validate .kittify/
```

### Agent Profiles (Role-Based WP Assignment)

Agent profiles define roles, specializations, and boundaries for work
package assignment. Each profile has these sections: purpose,
specialization (languages, frameworks, boundaries), collaboration (handoffs,
outputs), mode_defaults, and initialization_declaration. Doctrine references
are authored on the top-level `*-references` fields (`directive-references`,
`tactic-references`, `toolguide-references`, `styleguide-references`); the
retired `context-sources` block was removed (mission
`doctrine-drg-silent-drop-boundary`; #3629).

Profiles do not use relationship fields such as `specializes_from`. Lineage and
specialization relationships belong in the doctrine DRG; profile matching uses
weighted signals (language, framework, file path, keyword, exact-id).

The `mission.yaml` `task_types` section maps WP actions to agent roles:

```yaml
task_types:
  implement:
    agent_role: implementer
  review:
    agent_role: reviewer
  plan:
    agent_role: planner
```

```bash
# Discover activated profiles (--all for the full on-disk catalog)
spec-kitty agent profile list

# Inspect a profile's boundaries and initialization context (resolved
# through DRG lineage and context sources)
spec-kitty agent profile show <profile-id>
```

There is no separate hierarchy command: specialization lineage is declared in
the doctrine DRG (see the org-pack DRG YAML / generated `graph.yaml`); `profile
show` displays the resolved result.

### Action Indices (Doctrine Scoping)

Each mission action has an index that declares which doctrine artifacts are
relevant to that step:

```yaml
# packs/built-in/missions/software-dev/actions/implement/index.yaml
action: implement
directives: [TEST_FIRST]
tactics: [tdd-red-green-refactor, zombies-tdd, acceptance-test-first]
styleguides: [python-implementation]
toolguides: []
procedures: [implementation-handoff]
```

The charter context builder uses these indices to scope what gets
injected into the agent prompt at each step. This prevents agents from
seeing review-scoped doctrine during implementation and vice versa.

---

## Gating (post-retirement)

The mission-DSL v1 guard expressions (`artifact_exists(...)`,
`gate_passed(...)`, `all_wp_status(...)`, `any_wp_status(...)`,
`input_provided(...)`, `event_count(...)`) were retired with the DSL runtime
(dead-port-disposition-01M1TZVN). Gating now lives on two surfaces:

- **Step progression** — the `mission-runtime.yaml` DAG: a step runs only
  after every step in its `depends_on` list has completed.
- **WP lane transitions** — the status model (append-only event log): the
  9-lane transition matrix, review gates, and dependency gating (a WP with
  `dependencies` cannot be claimed until each is `approved` or `done`).

Artifact expectations are declared as `artifacts.required` in `mission.yaml`
and checked by the mission's `validation.checks` at acceptance.

---

## Template Resolution (6-Tier Chain)

When a command prompt is needed, spec-kitty resolves the current doctrine
mission-step prompt:

| Scope | Path | Purpose |
|---|---|---|
| Package | `packs/built-in/missions/mission-steps/<mission>/<step>/prompt.md` | Built-in default |
| Project doctrine | `.kittify/doctrine/...` | Project-local doctrine overrides where supported |
| Org doctrine | org doctrine pack | Shared organization doctrine where installed |

The package default is always the fallback. Legacy `command-templates` paths are
pre-migration artifacts, not the current package layout.

---

## Selecting a Mission Type

The mission type is set when you create a mission with `/spec-kitty.specify`.
It's recorded in `meta.json` and cannot be changed after creation.

**Commands:**

```bash
# List available mission types
spec-kitty mission-type list
spec-kitty doctrine mission-type list

# Specify a mission with a specific mission type
spec-kitty specify --mission-type research "What are the best auth patterns?"

# Check which mission type a mission uses
cat kitty-specs/<mission-slug>/meta.json | jq .mission
```

**Decision guide:**

| If you're... | Use mission type |
|---|---|
| Building a component, fixing a bug, refactoring | `software-dev` |
| Investigating, evaluating options, literature review | `research` |
| Planning architecture, roadmaps, design docs | `plan` |
| Writing tutorials, API docs, how-to guides | `documentation` |

---

## The Two State Surfaces

Missions track two orthogonal state surfaces:

**Mission-type state** — which phase of the workflow are we in?
```
discovery → specify → plan → tasks → implement → review → accept → merge
```
Managed by `mission-runtime.yaml` DAG and `spec-kitty next`.

**WP status** — where is each work package in its lifecycle?
```
planned → claimed → in_progress → for_review → in_review → approved → done
                                                    ↕
                                                 blocked / canceled
```
Managed by the status model (append-only event log).

Together they determine what `spec-kitty next` returns: "we're in the implement
phase, WP01 is done, WP02 is in_progress, WP03 is planned — your next action
is implement WP03."

---

## Runtime Bootstrap

On every CLI invocation, `ensure_runtime()` runs:
1. Checks `~/.kittify/cache/version.lock` — if version matches, fast path (< 100ms)
2. If stale: copies mission files from installed package to `~/.kittify/missions/`
3. Uses file locking to prevent concurrent corruption

This ensures `~/.kittify/` always matches the installed spec-kitty version.

---

## CLI Surface Contract

### `agent action implement` / `agent action review` — text-only output

The canonical agent surfaces `spec-kitty agent action implement <wp_id>` and
`spec-kitty agent action review <wp_id>` return **plain text** only. They do not
accept a `--json` flag. Passing `--json` to either command produces a Typer exit-2
error.

The top-level command `spec-kitty implement` *does* accept `--json`, but it is the
internal allocator used by the harness — not the surface intended for agent prompt
steps. Do **not** invoke `spec-kitty implement --json` from prompt steps; that is
an internal-only surface. Use `spec-kitty agent action implement <wp_id>` for
work-package execution.

Summary:

| Command | `--json`? | Intended for |
|---|---|---|
| `spec-kitty agent action implement <wp_id>` | **no** | Agent prompt steps |
| `spec-kitty agent action review <wp_id>` | **no** | Agent prompt steps |
| `spec-kitty implement <wp_id>` | **yes** | Internal harness allocator only |

If you need structured output from the implement action, use `spec-kitty agent tasks status --json`
to query the resulting WP state after the action completes.

### Workspace recovery

If a worktree is missing or corrupted, use the real recovery command (post-#2135,
the former `worktree repair` subcommand no longer exists):

```bash
spec-kitty doctor workspaces --fix
```

This removes husk directories (entries in `.worktrees/` that lack a `.git` entry)
without touching registered live worktrees.

## References

- `references/mission-comparison-matrix.md` -- Side-by-side comparison of all 4 mission types
