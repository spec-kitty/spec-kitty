# Missions

**Missions** are workflow definitions that configure phases, templates, and guardrails
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

This directory also contains shared mission primitives:

- `primitives.py` — `PrimitiveExecutionContext` dataclass with glossary middleware fields
- `glossary_hook.py` — `execute_with_glossary()` for wiring glossary checks into mission execution

## Glossary Reference

See [Mission](../../../glossary/contexts/orchestration.md#mission) and
[Command Template](../../../glossary/contexts/orchestration.md#command-template)
in the orchestration glossary context.
