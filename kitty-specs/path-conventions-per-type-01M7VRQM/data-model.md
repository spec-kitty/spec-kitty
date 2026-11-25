# Data Model

## ProjectPathConventions (value object)

| Field | Type | Rule |
|-------|------|------|
| *(mapping content)* | `dict[str, str]` | Flat overrides. Keys ⊂ `VALID_PATH_KEYS` minus `deliverables`. Values are repo-relative, non-blank, with no `..` and no absolute path. |
| `per_type` | `Mapping[str, Mapping[str, str]]` | Keys are mission-type ids in the layered roster. Inner keys and values follow the same rules as flat. |

- `for_mission_type(type_id | None) -> dict[str, str]`: returns `{**flat, **per_type.get(type_id, {})}`. With `None`, it returns the flat overrides only.
- Invariant: the mapping never adds a key the Mission does not declare (remap-only is enforced at the merge site, C-003).

## Path-conventions waiver (meta.json)

| Field | Value | Rule |
|-------|-------|------|
| `path_conventions` | exactly `"waived"` | any other value is malformed: nothing is waived, and a warning is produced |
| `path_conventions_rationale` | non-blank string | missing, blank or non-string is malformed |

## Acceptance history entry (addition)

| Field | Present when | Value |
|-------|--------------|-------|
| `path_conventions_waived` | the per-run flag was used | `{"reason": "<stripped reason>"}` |
