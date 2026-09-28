# Missions

Mission definitions (configuration, runtime step DAG, command templates and
content templates) live in `packs/built-in/missions/`. This repository carries no
mission-scoped overrides: the byte-identical `software-dev`, `documentation`, `plan`
and `research` mirrors were deleted by #5128, and
`tests/dossier/test_manifest.py::TestRepoMissionOverrideTierRetired` fails if one
reappears.

## Python Utilities

This directory also contains shared mission primitives:

- `primitives.py` — `PrimitiveExecutionContext` dataclass with glossary middleware fields
- `glossary_hook.py` — `execute_with_glossary()` for wiring glossary checks into mission execution

## Glossary Reference

See [Mission](../../../glossary/contexts/orchestration.md#mission) and
[Command Template](../../../glossary/contexts/orchestration.md#command-template)
in the orchestration glossary context.
