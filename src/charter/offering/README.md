# Doctrine

The **doctrine** package is a standalone catalog of reusable governance
knowledge. It ships typed, schema-validated YAML artifacts that define *how work
should be done* — independent of any specific project or charter configuration.

## What it contains

| Artifact kind | Directory | What it defines |
|---|---|---|
| **Paradigm** | `paradigms/` | Worldview-level framing (e.g. test-first, DDD) |
| **Directive** | `directives/` | Constraint-oriented governance rules |
| **Tactic** | `tactics/` | Reusable step-by-step behavioral recipes |
| **Procedure** | `procedures/` | Stateful multi-step workflows with entry/exit conditions |
| **Styleguide** | `styleguides/` | Cross-cutting quality and consistency conventions |
| **Toolguide** | `toolguides/` | Tool-specific operational syntax and guidance |
| **Schema** | `schemas/` | Machine-validated contracts for artifact structure |
| **Template** | `templates/` | Output scaffolds and interaction contracts |
| **Agent Profile** | `agent_profiles/` | Declarative agent identity and collaboration contracts |
| **Mission** | `missions/` | Workflow definitions (state machines, action indices, templates) |

## Design principle

Doctrine is a **pure knowledge library**. It has no dependency on the charter
package or the CLI. The charter package reads from charter.offering to compile
project-specific governance bundles, but doctrine itself is unaware of any
consumer.

**Dependency direction:** nothing in this package imports from `charter` or
`specify_cli`.

## Authoring pipeline

New artifacts are authored at `<type>/<pack>/[<category>/]<name>.<kind>.yaml` —
for example `directives/built-in/NNN-name.directive.yaml` or
`tactics/built-in/testing/<name>.tactic.yaml`. The pack layer (`built-in`) is
mandatory and any category grouping nests *inside* it; an artifact placed
outside that shape is never loaded (see ADR 2026-07-26-2). Cross-artifact
relationships are expressed as edges in the per-kind `<kind>.graph.yaml`
fragment, not as inline reference fields inside each YAML (see ADR
2026-07-26-1; the single `graph.yaml` monolith was sharded by #2680). Raw
reference material may still be
captured under `_reference/` as an intake landing zone; converting it to
doctrine is a manual editorial step that writes the shipped YAML plus the
matching `graph.yaml` edges.

## Architecture references

- Container view: `docs/architecture/diagrams/02_containers/README.md` — "Doctrine Artifact Catalog"
- Component view: `docs/architecture/diagrams/03_components/README.md` — "Doctrine and Glossary" section
- Governance ADR: `docs/adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md`
- Glossary: `docs/context/charter.md`
- Naming decision (agent vs tool): `docs/context/naming-decision-tool-vs-agent.md`
