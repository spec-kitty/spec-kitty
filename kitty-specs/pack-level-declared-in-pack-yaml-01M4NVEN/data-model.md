# Data Model — pack-level-declared-in-pack-yaml

The authoritative visual is `src/charter/diagrams/pack-descriptor-model.puml` (rendered in `src/charter/README.md`). This file is the textual contract.

## Entity: PackDescriptor (`pack.yaml`)

Pydantic model (`src/charter/offering/packs/pack_descriptor.py`), `model_config = ConfigDict(extra="forbid", frozen=True)`.

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `pack_id` | `str` | yes | — | ULID (26 chars), immutable identity (unchanged) |
| `pack_version` | `str` | **conditional** | — | required **iff** `pack_level == "built-in"`; optional otherwise (model_validator) — **new rule** (FR-005) |
| `parent_pack` | `str \| None` | no | `None` | lineage handle (unchanged) |
| `name` | `str` | yes | — | human handle (unchanged) |
| `pack_level` | `PackTier` | **yes** | — | `kernel.pack_tiers.PackTier` = `Literal["built-in","org","project"]` — **new** (FR-001) |
| `requires_core` | `str \| None` | no | `None` | PEP 440 version-specifier range; validated (FR-002) — **new** |
| `active_charter` | `str \| None` | no | `None` | pack-relative path to the active-charter file (FR-003) — **new** |
| `pack_drg` | `str \| None` | no | `None` | pack-relative path to the DRG source (FR-004) — **new** |

**Validation rules**
- `pack_level` must be a member of `PackTier`; any other value → pydantic schema error naming the field.
- `requires_core`, when present, must parse as a version specifier; else → `schema_invalid` naming `requires_core`.
- `active_charter` / `pack_drg`, when present, must resolve to a file **inside** the pack root (no `..` escape) — checked at validation time (IC-03), not model time.
- `pack_version` required ↔ `pack_level == "built-in"`.
- Retired-field rejection (`retired_fields.py`) runs before the generic extra-field check (unchanged).

**Lifecycle**: authored by a pack author (or minted by the backfill migration for project packs). Immutable once loaded (`frozen`).

## Value Object: PackTier (`kernel.pack_tiers`)

The single authority for the three level names and their precedence (`built-in < org < project`). `pack_level` reuses it; after this mission the artifact provenance/layer value uses the **same** spelling (`built-in`, hyphenated), so one vocabulary serves both the tier token and provenance.

## Entity: PackManifest (`pack-manifest.yaml`) — generated, unchanged by this mission

Machine-written sibling (`generate_builtin_manifest`); never hand-edited (`test_pack_manifest_no_author_edit`). Fields incl. `snapshot_sha256`, `artifact_counts`, `constituents`, `manifest_hash`. **Not** modified here except the authored-field gate's expectation of the sibling `pack.yaml` key set (FR-018).

## Relationships

- `PackDescriptor.pack_level` → **PackTier** (value, single authority).
- `PackDescriptor.parent_pack` → **PackDescriptor** (self-referential lineage / `extends`).
- `PackDescriptor.active_charter` → **active charter file** (`org-charter.yaml` for an org pack).
- `PackDescriptor.pack_drg` → **DRG source** (`drg/fragment.yaml` org; sharded `*.graph.yaml` built-in; `graph.yaml`+overlays project).
- `PackDescriptor` ↔ **PackManifest** (generated sibling, one per pack).

## Per-level layout (what `validate` expects, branched on declared `pack_level`)

| Level | Configured position | DRG source | Active charter | Manifest |
|-------|--------------------|-----------|----------------|----------|
| `built-in` | built-in root (`resolve_pack_root("built-in")`) | sharded `*.graph.yaml` | — | generated `pack-manifest.yaml` |
| `org` | `charter_packs.org.packs[]` | `drg/fragment.yaml` (single) | `org-charter.yaml` | none |
| `project` | `.kittify/charter-packs/` | `graph.yaml` + `overlays/` | — | none |

The `(pack_root, descriptor) -> (active_charter_path, drg_path)` resolution seam returns the descriptor's pointer when set, else the convention above.

## Artifact provenance/layer value (unified by #5992)

The resolved source layer of a loaded artifact — `built-in` / `org` / `project` — emitted by `BaseArtifactRepository._provenance` / `get_provenance()`. After this mission it is spelled identically to the tier token (`built-in`, hyphenated) and derives from `kernel.pack_tiers`. Distinct, untouched vocabularies: the `builtin|pack` skill-origin (`skills/manifest.py`) and the `"builtin:"` command-target prefix.
