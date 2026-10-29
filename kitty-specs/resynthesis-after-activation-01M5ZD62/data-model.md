# Data Model: Re-synthesis after activation

No new persisted entity. This mission reads two existing records and changes one in-memory input.

## Synthesis ownership record (read only)
- `.kittify/charter/synthesis-manifest.yaml` → `artifacts[]`: `kind`, `slug`, `path`, `provenance_path`, `content_hash`.
- `.kittify/charter/provenance/<kind>-<slug>.yaml` → `artifact_urn` (e.g. `directive:PROJECT_001`).
- **Derived value:** `synthesized_urns(kind)` = { provenance(`e.provenance_path`).`artifact_urn` | `e` ∈ manifest.artifacts, `e.kind == kind` }.
- **Invariants:** absent manifest ⇒ ∅. An unreadable manifest or sidecar ⇒ the read raises (never ∅).

## Synthesis request input (in memory)
- `selected_directives`: activated directive ids − ids of `synthesized_urns("directive")`.
- `drg_snapshot.nodes`: `{urn: "directive:<id>", kind: "directive"}` for exactly the ids in `selected_directives` (the two never diverge).
- **Invariant:** no id in the snapshot is synthesis-owned, so a target never collides with synthesis's own output.

## Collision refusal
- `ProjectDRGValidationError.colliding_urn: str | None` (additive; `None` for non-collision validation errors).
- **Origin classes** (CLI): `unowned-project-directive` (activated, resolved from the project pack root, not in `synthesized_urns`) | `upstream` (built-in or org).
