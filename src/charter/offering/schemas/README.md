# Schemas

**Schemas** are machine-validated contracts that define the allowed structure and
fields for doctrine artifacts. They are used by validation utilities and CI to fail
fast when invalid doctrine files are introduced.

## Available Schemas

| Schema | Validates |
|--------|-----------|
| `activation-preset.schema.yaml` | Activation preset YAML in a charter pack's `presets/<name>.yaml` (name, description, per-kind `activated_*` keys, `activated_kinds`, `mission_type_activations`); its kind enums are pinned to `ArtifactKind` by `tests/charter/presets/test_builtin_presets.py` |
| `agent-profile.schema.yaml` | Agent profile YAML (6-section structure, directive refs, routing metadata) |
| `directive.schema.yaml` | Directive YAML (id, title, intent, enforcement) — cross-artifact relationships live in the per-kind DRG fragments, `packs/built-in/<kind>.graph.yaml` |
| `import-candidate.schema.yaml` | Curation import candidate YAML |
| `mission.schema.yaml` | Mission definition YAML (states, transitions, guards, agent-profile on steps) |
| `occurrence-map.schema.yaml` | Bulk-edit occurrence map YAML (DIRECTIVE_035 — target, categories, exceptions) |
| `paradigm.schema.yaml` | Paradigm YAML (id, name, summary) |
| `styleguide.schema.yaml` | Styleguide YAML (scope, principles, anti-patterns) |
| `tactic.schema.yaml` | Tactic YAML (steps, references) |
| `toolguide.schema.yaml` | Toolguide YAML (guide_path, commands) |

## Usage

Schemas use JSON Schema Draft 7 or Draft 2020-12. The `agent_profiles` subpackage
uses `jsonschema.Draft7Validator` for runtime validation. Other schemas are used in
tests and CI checks.

## Glossary Reference

See [Schema (Doctrine Artifact)](../../../docs/context/charter.md#schema-doctrine-artifact)
in the doctrine glossary context.
