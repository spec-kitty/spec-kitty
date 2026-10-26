# Data Model: charter list in-force org-required ids

## RequiredInForce (value object, `charter.activation`)

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | `ArtifactKind` | an org-requirable, activatable kind whose `activated_<plural>` key is absent |
| `artifact_id` | `str` | the required id, in activation-stem spelling |
| `packs` | `tuple[RequiringPack, ...]` | the org packs that require it |

Derived: `pack_names` (first-seen order), `describe_packs()` (`'acme'`, `'base' (via 'overlay')`).
Shares both with `RequiredOmission`.

**Invariants**

- `artifact_id` is in the kind's org required floor.
- `PackContext.from_config(repo_root).effective_ids(kind, available)` contains `artifact_id`,
  where `available` is what the built-in, project and every org layer provide.
- Never produced for a kind whose allow key is present (that case is `RequiredOmission`, FR-023).

## `charter list --json` row

| Key | Type | Change |
| --- | --- | --- |
| `kind` | str | unchanged |
| `activated` | list[str] \| null | absent key + in-force required ids → those ids (was `null`) |
| `allow_list_present` | bool | new on every row |
| `available` | list \| null | unchanged |
| `deactivated` | list \| null | unchanged |

Payload: new top-level `schema_version: "2"`; `required_not_in_force` and `templates` unchanged.
