# Data Model — accept-path-conventions-name-overrides-01M66F7N

No persistent data changes. This mission extends one in-memory value object; the entities below are descriptive, not persisted.

## PathValidationResult (`src/specify_cli/validators/paths.py`)

Existing fields unchanged (`mission_name`, `required_paths`, `existing_paths`, `missing_paths`, `missing_artifact_tokens`, `warnings`, `suggestions`, `satisfied_by`).

New fields (both default-empty; hand-built results keep rendering valid text):

| Field | Type | Meaning |
|---|---|---|
| `remappable_missing_keys` | `list[str]` | Path-convention keys that are missing from the workspace AND can be remapped by a `project.path_conventions` override — i.e. every missing key whose declared key is NOT in `ARTIFACT_ROUTED_KEYS`. Populated by `validate_mission_paths()` at the point the key is recorded missing. |
| `mission_type` | `str \| None` | The mission-type slug used to name the override route (`.kittify/overrides/missions/<slug>/mission.yaml`). Derived from `mission.path.name` when the mission object carries a resolver-derived path; `None` (generic `<mission-type>` placeholder in the text) when it cannot be derived. |

### Invariants

- Remap-only vocabulary: a key in `ARTIFACT_ROUTED_KEYS` (`deliverables`) never appears in `remappable_missing_keys`, so the rendered example can never suggest overriding it (C-002).
- Ordering contract: `format_errors()` output keeps `--lenient` before any `mkdir -p` suggestion (C-001); the new guidance blocks are inserted between the `--lenient` sentence and `Required Actions:`.
- No validation semantics change: the new fields are render inputs only; `is_valid`, `missing_paths`, waiver handling and artifact routing are untouched (NFR-002).

## Rendered guidance (computed, not stored)

`format_errors()` derives from the fields above:

1. When `remappable_missing_keys` is non-empty: a block naming `project.path_conventions` in `.kittify/config.yaml` with a copy-pasteable YAML snippet listing exactly those keys.
2. Always alongside missing paths: a line naming `.kittify/overrides/missions/<mission_type>/mission.yaml` as the route for dropping a key the project has no directory for.
