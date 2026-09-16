---
title: Mission Types Reference
description: Reference for Spec Kitty mission types (software-dev, research, documentation, and plan). Learn how blueprints define phases, step bindings, and custom workflows.
doc_status: active
updated: '2026-09-03'
related:
- docs/api/configuration.md
---
# Mission Types Reference

Spec Kitty supports four built-in mission types, each tailored to a different kind of work. A mission type is the reusable workflow blueprint. A mission is the concrete tracked item under `kitty-specs/<mission-slug>/`.

Terminology note:
- `Mission Type` = reusable blueprint
- `Mission` = concrete tracked item
- `Feature` = software-dev compatibility alias for a mission
- Current legacy command names may still use `feature` wording even when they are acting on a mission

---

## Mission Type Overview

| Mission | Domain | Best For |
|---------|--------|----------|
| `software-dev` | Software development | Building features, APIs, UIs |
| `research` | Research and analysis | Investigations, competitive analysis, technical research |
| `documentation` | Documentation creation | User guides, API docs, tutorials |
| `plan` | Goal-oriented planning | Structured planning documents with review/rollback, independent of a code mission |

---

## software-dev (Default Mission Type)

The default mission type for building software missions such as features.

### Domain

Software development: building new features, APIs, user interfaces, and system components.

### Phases

1. **research** — Understand requirements and constraints
2. **design** — Plan architecture and data models
3. **implement** — Build the solution
4. **test** — Verify correctness
5. **review** — Quality assurance

### Artifacts

| Artifact | Created By | Purpose |
|----------|------------|---------|
| `spec.md` | `/spec-kitty.specify` | User stories, requirements, acceptance criteria |
| `plan.md` | `/spec-kitty.plan` | Architecture, design decisions, implementation concern Map (IC-## entries) |
| `tasks.md` | `/spec-kitty.tasks` | work package breakdown translated from IC-## concerns |
| `data-model.md` | `/spec-kitty.plan` | Database schema, entity relationships |
| `contracts/` | `/spec-kitty.plan` | API specifications (optional) |
| `tasks/*.md` | `/spec-kitty.tasks` | Individual WP prompt files |
| `wps.yaml` | `/spec-kitty.tasks` | Machine-readable WP manifest with `plan_concern_refs` traceability |

### When to Use

- Adding a new software mission to an application
- Building APIs or services
- Creating user interfaces
- System integrations
- Bug fixes that require planning

---

## research

Mission for research and analysis work.

### Domain

Research and analysis: investigating technologies, competitive analysis, feasibility studies, and technical deep-dives.

### Phases

1. **question** — Define research questions
2. **methodology** — Plan research approach
3. **gather** — Collect data and evidence
4. **analyze** — Analyze findings
5. **synthesize** — Draw conclusions
6. **publish** — Document results

### Artifacts

| Artifact | Created By | Purpose |
|----------|------------|---------|
| `spec.md` | `/spec-kitty.specify` | Research questions and scope |
| `plan.md` | `/spec-kitty.plan` | Research methodology |
| `research.md` | `/spec-kitty.research` | Research findings and evidence |
| `tasks.md` | `/spec-kitty.tasks` | Research task breakdown |
| `findings.md` | Implementation | Final synthesized findings |
| `sources/` | Implementation | Source materials and references |

### When to Use

- Technology evaluation
- Competitive analysis
- Feasibility studies
- Performance investigations
- Security audits
- Best practices research

---

## documentation

Mission for creating documentation.

### Domain

Documentation creation: user guides, API documentation, tutorials, and reference materials.

### Phases

1. **discover** — Understand documentation needs
2. **audit** — Assess existing documentation
3. **design** — Plan documentation structure
4. **generate** — Create content
5. **validate** — Review and test
6. **publish** — Deploy documentation

### Artifacts

| Artifact | Created By | Purpose |
|----------|------------|---------|
| `spec.md` | `/spec-kitty.specify` | Documentation scope and audience |
| `plan.md` | `/spec-kitty.plan` | Structure and approach |
| `research.md` | `/spec-kitty.research` | Audit of existing docs |
| `gap-analysis.md` | Planning | Coverage gaps identified |
| `tasks.md` | `/spec-kitty.tasks` | Documentation task breakdown |
| Divio templates | Implementation | Tutorial, how-to, reference, explanation files |

### Divio Documentation Types

The documentation mission uses the Divio 4-type system:

| Type | Orientation | Purpose |
|------|-------------|---------|
| **Tutorial** | Learning | Teach beginners step-by-step |
| **How-To** | Task | Solve specific problems |
| **Reference** | Information | Complete technical details |
| **Explanation** | Understanding | Explain concepts and "why" |

### When to Use

- Creating user documentation
- Writing API references
- Building tutorial content
- Documenting architecture
- Creating onboarding guides

---

## Selecting a Mission Type

Mission types are selected when `/spec-kitty.specify` creates a new mission. The selected mission type is currently stored in `meta.json` under the historical key `mission`:

```json
{
  "mission": "documentation"
}
```

### During Mission Creation

When you run `/spec-kitty.specify`, you'll be asked to choose a mission type:

```
? Which mission type should this mission use?
  ○ software-dev — Building software features (default)
  ○ research — Research and analysis
  ○ documentation — Creating documentation
```

### Changing Mission

The mission type cannot be changed after mission creation. If you need a different mission type, create a new mission.

---

## Mission Configuration Files

Advanced users can customize missions via configuration files.

### Location

```
.kittify/missions/<mission-key>/mission.yaml
```

### Format

```yaml
key: software-dev
name: Software Development
domain: Building software features
description: >
  Standard mission for building new features, APIs, and user interfaces.
phases:
  - research
  - design
  - implement
  - test
  - review
artifacts:
  required:
    - spec.md
    - plan.md
    - tasks.md
  optional:
    - data-model.md
    - contracts/
templates:
  spec: spec-template.md
  plan: plan-template.md
  tasks: tasks-template.md
```

### Custom Missions

You can create custom missions by:

1. Creating a new directory: `.kittify/missions/my-mission/`
2. Adding a `mission.yaml` file
3. Optionally adding custom templates

Custom missions appear as options during `/spec-kitty.specify`.

### Plan-field declaration (`plan-field-declaration.yaml`)

The plan-substantiveness gate (`spec-kitty setup-plan` / `mission create`'s auto-commit
check) decides whether a mission's `plan.md` is real content or an unedited scaffold.
For the four built-in mission types this check is built in. For a **custom mission
type shipped by a pack**, the pack must additionally ship a `plan-field-declaration.yaml`
file next to its `plan-template.md`, in the same `missions/<mission-key>/templates/`
directory. It resolves through the same override → legacy → org → global-mission →
global → package-default tier chain used for every other mission-type template asset —
but note this asset is only honoured from a **mission-scoped** tier (the resolved path
must contain `missions/<mission-key>/`); a hit at one of the mission-agnostic tiers
(global override, legacy) is ignored (see below). Without this file, a custom
type's plan is **fail-closed** — reported as non-substantive with an "no field
declaration is registered" reason — never silently treated as passing.

The file declares one **primary** field (must be substantive) plus a non-empty list of
**peer** fields (at least one must be substantive). Each field entry is a mapping with a
`kind` key selecting one of four shapes:

| `kind` | Checks | Keys (beyond common `kind`/`heading`) |
| --- | --- | --- |
| `bold_field` | A specific `**Label**: value` line under `## heading` | `label` (required, str), `sub_list_valued` (optional, bool, default `false` — set when the field's value is itself a bulleted sub-list) |
| `any_bold_field` | Any bold-labelled line under `## heading`, optionally excluding one label | `exclude_label` (optional, str — skip this label when scanning for a substantive peer), `example_label` (optional, str — used only in diagnostic messages) |
| `table_field` | A Markdown table directly under `## heading` | (none) |
| `nested_heading_field` | A nested `### heading` structure under the parent `## heading` | `sub_shape` (required, one of `repeatable` \| `named_sibling`), `child_label` (required, str) |

Every entry also requires a non-blank `heading` (the `##` section the field's presence
check reads). Unknown keys anywhere in the file — a typo'd optional key, or a top-level
key outside `primary`/`peers` — fail loud with a diagnosable error rather than being
silently ignored.

Worked example, mirroring `software-dev`'s own Technical Context shape:

```yaml
primary:
  kind: bold_field
  heading: Technical Context
  label: Language/Version

peers:
  - kind: bold_field
    heading: Technical Context
    label: Testing
  - kind: any_bold_field
    heading: Technical Context
    exclude_label: Language/Version
  - kind: table_field
    heading: Problem Decomposition
  - kind: nested_heading_field
    heading: Decisions
    sub_shape: repeatable
    child_label: "Decision D-"
```

Org-pack precedence for this asset is deliberately **first-declared-root-wins** —
consistent with the `plan-template.md` it rides alongside — unlike
`expected-artifacts.yaml`, which resolves last-match. A `plan-field-declaration.yaml`
that resolves through a **mission-agnostic** tier (the global override or legacy tiers,
which are not scoped to any one mission type) is ignored, so it can never accidentally
gate an unrelated, undeclared mission type's plan.

---

## Mission Comparison

| Aspect | software-dev | research | documentation |
|--------|--------------|----------|---------------|
| Primary output | Working code | Research findings | Documentation |
| Typical WPs | 5-10 | 3-7 | 5-15 |
| Data model | Yes | No | No |
| API contracts | Optional | No | No |
| Gap analysis | No | No | Yes |
| Divio structure | No | No | Yes |

---

## Authoring Custom Missions

Custom missions are project-authored mission definitions that the Local Custom Mission Loader discovers, validates, and runs through the same composition path used by the built-in `software-dev` mission. This section is the canonical reference for the `mission.yaml` format. For an operator-narrative walkthrough, see [`kitty-specs/local-custom-mission-loader-01KQ2VNJ/quickstart.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/local-custom-mission-loader-01KQ2VNJ/quickstart.md).

### YAML shape

A custom mission lives at `.kittify/missions/<mission-key>/mission.yaml`. Top-level keys are `mission` (metadata block) and `steps[]` (ordered list of `PromptStep` entries). The optional `audit_steps[]` list mirrors the same shape and is reserved for end-of-mission audits.

Minimal valid example:

```yaml
mission:
  key: my-custom
  name: My Custom Mission
  version: 0.1.0
  description: Minimal custom mission for the loader reference.

steps:
  - id: do-the-thing
    title: Do the thing
    description: A composed step that delegates to a profile-bound agent.
    agent_profile: researcher-robbie

  - id: retrospective
    title: Mission retrospective marker
    description: Reserved structural marker; execution lands in a later tranche.
    depends_on: [do-the-thing]
```

### Step fields

Every entry in `steps[]` is a `PromptStep`. The table below covers every author-facing field; `id` and `title` are required on every step, and at least one of `agent_profile` / `contract_ref` / `requires_inputs` must be present so the step has a meaningful binding.

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `id` | yes | str | Unique within the mission; the final step's `id` MUST be `retrospective`. |
| `title` | yes | str | Short human label rendered in the Kanban / panels. |
| `description` | no | str | Free-form prose. Recommended for clarity. |
| `agent_profile` (alias `agent-profile`) | conditional | non-empty str | Profile key for composed steps. Required unless the step uses `contract_ref` or is a `requires_inputs` gate. Both snake-case and kebab-case YAML keys are accepted. |
| `contract_ref` | conditional | non-empty str | Reference to an existing `MissionStepContract` ID. Mutually exclusive with `agent_profile`. |
| `requires_inputs` | no | list[str] | Marks the step as a decision-required gate. The runtime pauses and the operator answers via `spec-kitty agent decision resolve …`. |
| `depends_on` | no | list[str] | Step IDs this step waits on. Used for dependency-aware ordering. |
| `raci` | no | object | Optional RACI override (`responsible`, `accountable`, `consulted`, `informed`). |
| `raci_override_reason` | no | str | Required string explanation when `raci` is set. |

### The retrospective marker

Every custom mission MUST declare a final `PromptStep` whose `id == "retrospective"`. The validator checks one rule: the last entry of `steps[]` (after dependency-aware sort) has `id == "retrospective"`. Missing or misnamed markers are rejected with the stable error code `MISSION_RETROSPECTIVE_MISSING`.

Execution semantics for the marker step are deferred to the retrospective-execution tranche (#506–#511); v1 only enforces the structural rule. See [research §R-001](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/local-custom-mission-loader-01KQ2VNJ/research.md) for the rationale.

### Profile binding

A composed step needs a profile so the runtime knows which agent persona to dispatch through `StepContractExecutionContext`. There are two binding surfaces:

- `agent_profile`: per-step inline declaration. The loader's contract synthesizer auto-generates a single-step `MissionStepContract` for the step. This is the ergonomic default for most authors.
- `contract_ref`: reference to a pre-existing `MissionStepContract` ID in the on-disk repository. Use this when multiple missions share the same contract or when a contract's execution rules need to be authored separately. If the referenced contract does not resolve, the loader rejects with `MISSION_CONTRACT_REF_UNRESOLVED`.

Declaring both `agent_profile` and `contract_ref` on the same step is rejected with `MISSION_STEP_AMBIGUOUS_BINDING`. Declaring neither (and having no `requires_inputs`) is rejected with `MISSION_STEP_NO_PROFILE_BINDING`. See [research §R-003](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/local-custom-mission-loader-01KQ2VNJ/research.md) for the full rationale.

Built-in missions (`software-dev`, `research`, `documentation`) do not set `agent_profile` on their shipped steps; the executor resolves each `(mission, action)` through a built-ins-only defaults table instead. When a table default (e.g. `researcher-robbie` for `software-dev/specify`) is deactivated in the project, the executor falls back to the highest-`routing-priority` available profile carrying the default's role (`researcher`, `architect`, `implementer`, or `reviewer`), and blocks with a structured composition error — not a crash — when no available profile carries that role. `charter deactivate agent-profile <id>` and `charter preflight` warn when a deactivated profile is one of these defaults. A project that wants a specific profile for a built-in step without relying on priority can deactivate the shipped default (the fallback then picks its own activated same-role profile) or define a custom mission type with explicit per-step `agent_profile` bindings.

YAML examples:

```yaml
# Inline profile binding — most common.
- id: gather-data
  title: Gather data
  agent_profile: researcher-robbie

# Reuse an existing contract.
- id: gather-data
  title: Gather data
  contract_ref: shared-research-contract-v1
```

### Reserved keys

The following `mission.key` values are reserved for built-in missions and cannot be used by custom mission definitions:

- `software-dev`
- `research`
- `documentation`
- `plan`

Any non-builtin discovery tier that produces a definition with one of these keys is rejected at load time with the stable error code `MISSION_KEY_RESERVED`. Built-in dispatch logic is hard-coded to these keys, so silent shadowing would be a footgun. To customize behavior of a built-in workflow, rename your mission to a non-reserved key. See [research §R-002](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/local-custom-mission-loader-01KQ2VNJ/research.md) for the rationale.

### Discovery precedence

The loader queries eight tiers in priority order; the highest-precedence tier wins. Lower-precedence definitions of the same key emit a `MISSION_KEY_SHADOWED` warning (except built-in shadow, which is the `MISSION_KEY_RESERVED` error above).

1. **Explicit path** — `--mission-path <path>` (env-forwarded; not exposed by `mission run` directly in v1).
2. **Environment variable** — `SPEC_KITTY_MISSION_PATHS=/path/one:/path/two`.
3. **Project override** — `.kittify/overrides/missions/<key>/mission.yaml`.
4. **Project legacy** — `.kittify/missions/<key>/mission.yaml`.
5. **Org** — org-provided mission roots (`context.org_roots`), sitting between project legacy and user global.
6. **User global** — `~/.kittify/missions/<key>/mission.yaml`.
7. **Project config (mission packs)** — `.kittify/config.yaml mission_packs: [...]` referencing `mission-pack.yaml` manifests.
8. **Built-in** — `software-dev`, `research`, `documentation`, `plan`.

## Authoring Custom Workflows

Workflows are the project-authored execution sequence for a mission. A mission's `meta.json` may set `workflow_id`; when absent, Spec Kitty uses the shipped `software-dev-default` workflow. Project workflow files are discovered before shipped workflows, so teams can opt into a named local sequence without forking the runtime.

Workflow files live in `.kittify/overrides/workflows/` and may use either `<workflow-id>.workflow.yaml` or `<workflow-id>.yaml`. The file's top-level `workflow_id` MUST match the requested slug. Slugs are lowercase URL-style identifiers matching `[a-z0-9][a-z0-9-]*`; path traversal, spaces, uppercase letters, and special characters are rejected before filesystem lookup.

Minimal valid example:

```yaml
workflow_id: solo-fast
description: Solo workflow that skips review.
version: 1
initial: specify
actions:
  - action_name: specify
    description: Create a mission specification
    next: [plan]
  - action_name: plan
    description: Create an implementation plan
    next: [implement]
  - action_name: implement
    description: Implement directly
    next: [accept]
  - action_name: accept
    description: Accept without review
    terminal: true
```

### Workflow fields

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `workflow_id` | yes | str | Must match the filename slug requested by `meta.json::workflow_id`. |
| `description` | yes | str | Human-readable summary. |
| `version` | yes | int | Schema version, currently `1`. |
| `initial` | yes | str | First action in the workflow. Must name an action in `actions[]`. |
| `integrations` | no | object | Declarative provider bindings, such as `vcs.provider` or `issue_tracker.provider`. Runtime support is provider-specific. |
| `actions` | yes | list | Ordered action graph. v1 workflows are linear: each action can name at most one successor in `next`. |

Each `actions[]` entry supports:

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `action_name` | yes | str | Unique action identifier. |
| `description` | yes | str | Human-readable step summary. |
| `next` | no | list[str] | Empty or omitted for terminal actions; otherwise one successor action. |
| `terminal` | no | bool | Terminal actions must not declare `next`. |
| `agent_profile` | no | str | Optional profile binding for workflow-aware callers. |
| `human_in_the_loop` | no | str | Optional checkpoint marker for non-agent actions. |
| `integration` | no | str | Optional reference such as `vcs.open_pr`. |
| `outputs` | no | object | Optional output names/templates declared by the action. |

Validation rejects duplicate action names, unresolved `next` references, unreachable actions, cycles, terminal actions with successors, and branching `next` lists. Unknown workflow ids fail closed and list available workflow ids; they do not silently fall back to `software-dev-default`.

When a workflow introduces a new software-dev action, make sure a matching command
template such as `.kittify/overrides/command-templates/<action-name>.md` is
available. Actions that reuse shipped names such as `specify`, `plan`, `tasks`,
`implement`, `review`, `accept`, or `design-review` resolve to bundled templates.

### Workflow portability commands

Use `spec-kitty workflow list` to see the workflow ids visible from the current project. Use `spec-kitty workflow export <workflow-id> <path>` to copy the resolved workflow YAML to a portable file, preserving project override precedence. Use `spec-kitty workflow import <path>` to validate a workflow file and copy it into `.kittify/overrides/workflows/<workflow-id>.yaml`. Both import and export refuse to overwrite existing files unless `--force` is supplied.

### Validation error codes

The loader emits a closed enumeration of error and warning codes. Wire spellings are stable: removal or rename is a breaking change requiring a deprecation cycle. Additions are non-breaking. Tooling MAY rely on string equality on `error_code` / warning `code` and MUST NOT fail on unknown `details` keys.

<!-- This table mirrors kitty-specs/local-custom-mission-loader-01KQ2VNJ/contracts/validation-errors.md.
     Mission-review verifies parity. -->

Errors (exit code 2):

| Code | When | Required `details` keys |
| --- | --- | --- |
| `MISSION_YAML_MALFORMED` | Discovery scanned a file but failed to parse it as YAML, OR `MissionTemplate.model_validate` raised `ValidationError`. | `file`, `parse_error` |
| `MISSION_REQUIRED_FIELD_MISSING` | Top-level `mission.key`, `mission.name`, `mission.version`, or `steps[]` missing. (A specific subset of `MISSION_YAML_MALFORMED` surfaced separately for operator clarity.) | `file`, `mission_key` (best-effort), `field` |
| `MISSION_KEY_UNKNOWN` | The user invoked `spec-kitty mission run <key>` but no discovery tier produced a definition with that key. | `mission_key`, `tiers_searched` (list[str]) |
| `MISSION_KEY_AMBIGUOUS` | Two or more tiers produced the same key AND the resolver could not pick a single selected entry (extreme edge case; default precedence picks one). Reserved for future use. | `mission_key`, `paths` (list[str]) |
| `MISSION_KEY_RESERVED` | A non-builtin tier produced a definition whose `mission.key` is in `RESERVED_BUILTIN_KEYS`. | `mission_key`, `file`, `tier`, `reserved_keys` |
| `MISSION_RETROSPECTIVE_MISSING` | Validator R-001: the last step's `id` is not `"retrospective"`. | `file`, `mission_key`, `actual_last_step_id`, `expected: "retrospective"` |
| `MISSION_STEP_NO_PROFILE_BINDING` | Validator FR-008: a step with empty `requires_inputs` declares neither `agent_profile` nor `contract_ref`. | `file`, `mission_key`, `step_id` |
| `MISSION_STEP_AMBIGUOUS_BINDING` | Validator: a step declares both `agent_profile` AND `contract_ref`. | `file`, `mission_key`, `step_id` |
| `MISSION_CONTRACT_REF_UNRESOLVED` | A step's `contract_ref` does not resolve in the on-disk `MissionStepContractRepository`. | `file`, `mission_key`, `step_id`, `contract_ref` |

Warnings (exit code unaffected; included in envelope):

| Code | When | Required `details` keys |
| --- | --- | --- |
| `MISSION_KEY_SHADOWED` | A definition was discovered in multiple tiers; the higher-precedence tier wins. Emitted for non-built-in keys (built-in shadow is an error per `MISSION_KEY_RESERVED`). | `mission_key`, `selected_path`, `selected_tier`, `shadowed_paths` |
| `MISSION_PACK_LOAD_FAILED` | A mission-pack manifest pointed at a `mission.yaml` that failed to load. | `pack_root`, `failed_path`, `parse_error` |

Detail key conventions:

- All paths are absolute strings.
- `mission_key` is the value of `template.mission.key` once known; `null` when unknown.
- `tier` ∈ `{"explicit", "env", "project_override", "project_legacy", "org", "user_global", "project_config", "builtin"}`.
- `step_id` is the `PromptStep.id` value.

### Example: ERP integration mission

The reference fixture used by the loader's test suite lives at [`tests/fixtures/missions/erp-integration/mission.yaml`](https://github.com/spec-kitty/spec-kitty/blob/main/tests/fixtures/missions/erp-integration/mission.yaml). The fixture is the **authoritative** copy of this example: any drift between the fixture and the operator narrative in [quickstart.md](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/local-custom-mission-loader-01KQ2VNJ/quickstart.md) is resolved in favor of the fixture, since the fixture is what the test suite executes against.

Inline copy of the fixture:

```yaml
mission:
  key: erp-integration
  name: ERP Integration
  version: 0.1.0
  description: Lookup an ERP record, ask the operator a question, and emit a JS adapter.

steps:
  - id: query-erp
    title: Query the ERP system
    description: Pull the active record set from the ERP integration endpoint.
    agent_profile: researcher-robbie

  - id: lookup-provider
    title: Look up the matching provider
    agent_profile: researcher-robbie
    depends_on: [query-erp]

  - id: ask-user
    title: Confirm the export shape
    description: Ask the operator which export shape to emit.
    requires_inputs: [export_shape]
    depends_on: [lookup-provider]

  - id: create-js
    title: Generate the JS adapter
    agent_profile: implementer-ivan
    depends_on: [ask-user]

  - id: refactor-function
    title: Refactor the legacy function
    agent_profile: implementer-ivan
    depends_on: [create-js]

  - id: write-report
    title: Summarize the run
    agent_profile: researcher-robbie
    depends_on: [refactor-function]

  - id: retrospective
    title: Mission retrospective marker
    description: Reserved structural marker; execution lands in #506-#511.
    depends_on: [write-report]
```

CLI invocations:

**1. Default panel output (success)**

```bash
spec-kitty mission run erp-integration --mission erp-q3-rollout
```

A `rich.panel.Panel` titled "Mission Run Started" is rendered. The body shows the success message, `feature_dir`, and `run_dir`. Exit code 0.

**2. JSON envelope (success)**

```bash
$ spec-kitty mission run erp-integration --mission erp-q3-rollout --json
{
  "result": "success",
  "mission_key": "erp-integration",
  "mission_slug": "erp-q3-rollout-01KQ…",
  "mission_id": "01KQ…",
  "feature_dir": "/abs/path/kitty-specs/erp-q3-rollout-01KQ…",
  "run_dir": "/abs/path/.kittify/runtime/runs/<run-id>",
  "warnings": []
}
```

Exit code 0. `warnings` is a list of `{code, message, details}` objects.

**3. JSON envelope (error)**

```bash
$ spec-kitty mission run no-such-key --mission x --json
{
  "result": "error",
  "error_code": "MISSION_KEY_UNKNOWN",
  "message": "No mission definition with key 'no-such-key' was found in any discovery tier.",
  "details": {
    "mission_key": "no-such-key",
    "tiers_searched": ["explicit", "env", "project_override", "project_legacy", "org", "user_global", "project_config", "builtin"]
  },
  "warnings": []
}
```

Exit code 2. Validation errors do NOT start a run; the `kitty-specs/<slug>/` directory is not created.

For the operator-narrative walkthrough (decision resolution, advancement, recovery from validation failures), see [`kitty-specs/local-custom-mission-loader-01KQ2VNJ/quickstart.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/local-custom-mission-loader-01KQ2VNJ/quickstart.md).

---

## See Also

- [Configuration](configuration.md) — Mission configuration details
- [Spec-Driven Development](../architecture/spec-driven-development.md) — The philosophy behind missions
- [Mission System](../architecture/mission-system.md) — Why missions exist

## Getting Started

- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## Practical Usage

- [Use the Dashboard](../guides/how-to/monitoring/use-dashboard.md)
- [Non-Interactive Init](../guides/how-to/installation/non-interactive-init.md)

## Background

- [Mission System](../architecture/mission-system.md)
