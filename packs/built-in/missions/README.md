# Missions

**Missions** are workflow definitions that configure steps (each with its templates) and guardrails
for structured work. Each mission subdirectory contains a mission configuration, an
optional runtime step DAG, command templates, and content templates.

## Available Missions

| Mission              | Directory        | Domain       | Steps                                                         |
|----------------------|------------------|--------------|---------------------------------------------------------------|
| Software Development | `software-dev/`  | software-dev | discovery → specify → plan → tasks → implement → review → accept |
| Documentation        | `documentation/` | other        | discover → audit → design → generate → validate → publish → accept |
| Plan                 | `plan/`          | planning     | specify → research → plan → review                            |
| Research             | `research/`      | research     | scoping → methodology → gathering → synthesis → output → accept |

## Structure Convention

Each mission directory contains:

- `mission.yaml` — Mission configuration (workflow phases, expected artifacts, commands, validation rules)
- `mission-runtime.yaml` — Runtime step DAG (steps, `depends_on` dependencies, agent-profile assignments)
- `command-templates/` — Markdown prompt files for each slash command step
- `templates/` — Content scaffolds for output artifacts (spec, plan, tasks, etc.)

## Python Utilities

The mission **logic modules** are **not** in this directory — this pack ships mission
**data** only (`mission.yaml`, prompts, templates, step contracts). The Python modules
(`primitives.py` with `PrimitiveExecutionContext`, `glossary_hook.py` with
`execute_with_glossary()`, `repository.py`, and the other 8 logic modules) live in the
`charter.offering` package at `src/charter/offering/missions/` and read this data at
runtime; a pack tree cannot host a Python package.

## Glossary Reference

See [Mission](../../../docs/context/orchestration.md#mission) and
[Command Template](../../../docs/context/orchestration.md#command-template)
in the orchestration glossary context.
