# Data Model: Canonical doctrine artifact slug convention

Phase 1 output. These are existing conceptual entities; the mission changes how their **slug/filename** relate, not their schema.

## Entities

### Doctrine artifact
- **Identity**: `id` (authored; canonical machine identity; SCREAMING for directives per `^[A-Z][A-Z0-9_-]*$`, kebab for other kinds). **Immutable** — never mutated to satisfy a filename (C-001).
- **Kind**: one of `directive, tactic, styleguide, procedure, agent_profile` (the registration-writing kinds). `glossary_pack`/`paradigm` are not registration-writing (no sidecar).
- **Slug** (derived): `slug_for(kind, id)` → `quote(kebab(id), safe="")` for directives, `quote(id, safe="")` otherwise (preserves the engine's URL-encoding; no path escape).
- **On-disk filename**: `<slug><ext>` where `ext` comes from `ArtifactKind._PATTERNS` (`.directive.yaml`, `.tactic.yaml`, `.styleguide.yaml`, `.procedure.yaml`, `.agent.yaml`).
- **Invariant**: for a **newly authored** artifact, `filename == slug_for(kind, id) + ext` (the scaffolder emits it that way). For **pre-existing** SCREAMING-filename directives the filename may differ from the slug; validation does not require them to match (the manifest carries the slug) — no migration renames them (go-forward only).

### Provenance sidecar
- **Path**: `.kittify/charter/provenance/<kind>-<slug>.yaml`.
- **Written by**: the registration engine, for every registration-writing kind (5).
- **Invariant (preserved)**: a sidecar with no backing artifact is corruption → still errors in `charter bundle validate` (NFR-001).

### Synthesis manifest
- **Records** per registered artifact: `(kind, slug, path, provenance_path, content_hash, adapter_id)`.
- **New role**: the **authority** the bundle validator trusts for `(kind, slug, path, provenance_path)` — the validator stops re-deriving the slug by parsing the filename.
- **Path-update rule (#4834)**: a registration pass re-writes the entry when `path` or `provenance_path` drifts, even if `content_hash` is unchanged.

### Slug authority — `slug_for(kind, identifier)`
- **Type**: pure function `(str, str) -> str`, deterministic, no IO.
- **Rule**: `directive → quote(kebab(identifier), safe="")`; all other kinds → `quote(identifier, safe="")`.
- **Consumers**: the `charter new` scaffolder (`doctrine.py`) and the registration engine (`project_registration.py`) — the single producer-side authority.

### `DIRECT_WRITE_KINDS`
- **Type**: module-level constant tuple in `artifact_kinds.py` = `("directive","tactic","styleguide","procedure","agent_profile")`.
- **Consumers (single source of truth, NFR-002)**: `scan_project_artifacts` (`project_scan.py`), `ManifestArtifactEntry.kind` `Literal` (`manifest.py`), and `bundle.py`'s `_KIND_SUFFIX`/`_ALL_ARTIFACT_PATTERNS` all reference it; a parity test asserts equality.

### Validator resolution (hybrid)
- **Registered artifacts**: resolved via the manifest entry `(kind, slug, path, provenance_path)` — no filename re-parse.
- **Orphans / legacy (no manifest)**: filesystem walk retained (both directions — orphan sidecar and orphan artifact), so corruption stays detected.

## State (go-forward only — no migration)

```
NEW artifact  ──scaffold(slug_for)──►  kebab filename on disk  ──register──►  manifest (slug, path, provenance_path)  ──validate──► green
EXISTING SCREAMING file  ──(unchanged on disk)──►  manifest already has kebab slug  ──validate (manifest-driven)──► green   # no rename
```

