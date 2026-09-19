# Agent Profiles

**Agent profiles** are doctrine artifacts that define an agent's identity — its role,
specialization boundaries, collaboration contracts, and initialization behavior.
Profiles are the **identity layer** beneath missions: missions orchestrate *what work
happens*; profiles govern *who does the work and how they behave*.

An agent profile is distinct from a tool configuration. An **agent** is a logical
collaborator identity (implementer, reviewer, architect); a **tool** is a concrete
runtime product (Claude Code, Codex, opencode). This package defines agent identity;
tool installation is managed by `ToolConfig`.

## 6-Section Structure

Each profile defines:

1. **Context Sources** — Doctrine layers and directives to load
2. **Purpose** — What the agent does and does not do
3. **Specialization** — Primary focus, secondary awareness, avoidance boundaries
4. **Collaboration Contract** — Handoff partners, output artifacts, canonical verbs
5. **Mode Defaults** — Operating modes with descriptions and use-cases
6. **Initialization Declaration** — Self-description loaded at session start

## Layered Loading

Profiles are loaded from layered sources with field-level merge:

- **Shipped profiles** (`built-in/`) — Reference profiles included in the package
- **Organization profiles** — Optional organization-level pack overlays
- **Project profiles** (`.kittify/charter/agents/`) — Custom overrides per project

Each higher layer can override a lower-layer profile at field level when sharing
the same `profile-id`; project profiles have final precedence.

## Shipped Profiles

| Profile ID | Name | Role |
|------------|------|------|
| `architect-alphonso` | Architect Alphonso | architect |
| `curator-carla` | Curator Carla | curator |
| `debugger-debbie` | Debugger Debbie | investigator |
| `designer-dagmar` | Designer Dagmar | designer |
| `doctrine-daphne` | Doctrine Daphne | curator / onboarding-guide |
| `drupal-dries` | Drupal Dries | implementer |
| `frontend-freddy` | Frontend Freddy | implementer |
| `generic-agent` | Generic Agent | implementer |
| `human-in-charge` | Human in Charge | human-in-charge |
| `implementer-ivan` | Implementer Ivan | implementer |
| `java-jenny` | Java Jenny | implementer |
| `node-norris` | Node Norris | implementer |
| `paula-patterns` | Paula Patterns | architecture-scout |
| `planner-priti` | Planner Priti | planner |
| `python-pedro` | Python Pedro | implementer |
| `randy-reducer` | Randy Reducer | implementer |
| `researcher-robbie` | Researcher Robbie | researcher |
| `retrospective-facilitator` | Retrospective Facilitator | facilitator |
| `reviewer-renata` | Reviewer Renata | reviewer |
| `analyst-annie` | Analyst Annie | analyst |
| `comms-cleo` | Comms Cleo | communicator |
| `diagram-daisy` | Diagram Daisy | diagram-author |
| `lexical-larry` | Lexical Larry | semantic-analyst |
| `minutes-mahad` | Minutes Mahad | documentarian |
| `scribe-sally` | Scribe Sally | documentarian |
| `synthesizer-sam` | Synthesizer Sam | synthesizer |

## Python API

- `AgentProfile` — Pydantic domain model
- `AgentProfileRepository` — Layered loading, hierarchy, weighted matching
- `validate_agent_profile_yaml()` — JSON Schema (Draft 7) validation
- `RoleCapabilities` / `DEFAULT_ROLE_CAPABILITIES` — Role-based capability defaults

## Schema

Profiles are validated against `schemas/agent-profile.schema.yaml`.

## Glossary Reference

See [Agent](../../../../docs/context/identity.md#agent) and
[Tool](../../../../docs/context/execution.md#tool) in the glossary for the
canonical naming distinction.

## Canonical documentation

- **Agent-profile schema diagram** — [Doctrine artifact kinds → Schema at a glance](../../../../docs/architecture/doctrine-kinds.md#schema-at-a-glance)
  (the `@startyaml` `AgentProfileSchema` + nested `AgentSpecialization` diagram is generated from the code model in this package and drift-guarded; it is the single source of truth for the field set).
- **Kind catalog entry** — [Doctrine artifact kinds → Agent Profile](../../../../docs/architecture/doctrine-kinds.md).
- **Relationship edges (delegation, lineage)** — [Doctrine relationships](../../../../docs/architecture/doctrine-relationships.md).
