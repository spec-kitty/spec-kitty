# Data Model: asset-sidecar-non-mapping-crash-01M66937

No persistent entities change. This mission adjusts the **loader data shapes**
of `BaseArtifactRepository`; the domain models (`AssetManifest`, `Directive`,
`Tactic`, …) are untouched.

## Parsed overlay/built-in document (raw YAML → guard → validation)

| State of `yaml_parser.load(file)` | Tier | Behavior before | Behavior after |
|---|---|---|---|
| `None` (empty file) | both | early return (absence) | unchanged (absence, research.md D4) |
| `Mapping` (dict) | both | `_pre_validate` → `data.get("id")` → merge/insert | unchanged |
| non-mapping (list, scalar, bool) | overlay | **`AttributeError` crash** at `data.get("id")` | skip + `Skipping invalid <layer> <kind> <file>: expected a YAML mapping, got <type name>` |
| non-mapping (list, scalar, bool) | built-in | crash in `_pre_validate` for 6 kinds; `ValidationError` skip for the rest | skip + same warning shape for **all** kinds (uniform semantics) |

## Invariants

- **INV-1 (skip envelope)**: a file the loader cannot turn into a valid item is
  skipped with a `UserWarning` matching
  `Skipping invalid <layer> <kind> <file>: <reason>`; the repository object
  remains constructible and every other valid artifact still loads.
- **INV-2 (empty ≠ malformed)**: `None` (empty file) stays absence — no
  warning, no skip record.
- **INV-3 (single authority)**: the non-mapping decision exists once, in
  `src/charter/offering/base.py`; no repository kind re-implements it.

## Relationships

`BaseArtifactRepository[T]` ← (11 subclasses, the per-kind test matrix):
`AssetRepository`, `DirectiveRepository`, `TacticRepository`,
`ToolguideRepository`, `GlossaryPackRepository`, `PackSkillRepository`,
`StyleguideRepository`, `ParadigmRepository`, `ProcedureRepository`,
`MissionStepContractRepository`, `MissionTypeProfileRepository`.

Out of scope (do not inherit the base class): `AgentProfileRepository`,
`MissionTypeRepository`, `MissionTemplateRepository`.
