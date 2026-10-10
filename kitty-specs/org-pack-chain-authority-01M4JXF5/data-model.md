# Data Model — One org-pack chain authority (#6006)

This mission defines no external interface. The surfaces below are an internal
Python API and one new YAML file schema.

## Entity: Org-pack chain

- **What it is**: the ordered list of organization charter-pack roots a project
  declares in `.kittify/config.yaml` under `charter_packs.org.packs[]`, each with
  `name` and `local_path` (joined with `subdir` when present).
- **Order**: declaration order; **last-declared-wins** on any id/body collision.
- **Postures**:
  - *lenient* — the existing-on-disk subset (a stale/unfetched `local_path` is dropped).
  - *strict* — a declared-but-absent pack raises, naming the pack and the `spec-kitty charter fetch` remedy.
- **Invariant**: "declared-but-missing" means declared-and-absent; zero declared packs is an empty chain, never a raise.

## API: `resolve_pack_chain(repo_root: Path, *, strict: bool) -> list[Path]`

- **Home**: `src/charter/activation/layer_roots.py` (the sole authority).
- **Returns**: declaration-ordered existing pack roots.
- **strict=False**: existing-filtered (≡ today's `resolve_existing_org_roots`).
- **strict=True**: raises `ValueError` (today's `require_declared_org_roots` message shape) on a declared-but-absent pack.
- **Absorbs**: `resolve_org_root_chain` (removed; callers move here).
- **Primitives** (`resolve_org_roots`, `resolve_existing_org_roots`, `require_declared_org_roots` in `org_pack_config.py`): survive but are callable only from the authority module and their own module (gate-enforced, FR-006).

## API: `ActiveCharterManager` widening

- `activate` / `list_available` / `list_available_detailed` / `_scan_layer_dirs` gain `org_root_chain: list[Path] | None = None`.
- When supplied: emit one ORG scan pair per chain root, **last-declared-first**.
- When `None`: fall back to the single `layer_roots["org"]` slot (back-compat).
- `_activate_cascade_target` is removed; the direct activation target uses the single widened scan.

## Entity: Requirement-kind declaration (`requirement-kinds.yaml`)

The full requirement-kind set a mission type declares, resolved through the chain
(built-in → org last-wins → project; project wins). Whole-file override, never
field-merge.

```yaml
# <tier>/missions/<mission_type>/requirement-kinds.yaml
schema_version: "1"
mission_type: research
kinds:                       # the FULL set for this type (no additive floor)
  - prefix: DR
    label: Data requirement
    glossary_term: data requirement     # referenced only; not resolved by this seam
    must_map_to_wp: true
  - { prefix: AR, label: Analysis requirement, glossary_term: analysis requirement, must_map_to_wp: true }
  - { prefix: QR, label: Quality requirement,  glossary_term: quality requirement,  must_map_to_wp: true }
```

- **Tier paths**:
  - built-in: `packs/built-in/missions/<type>/requirement-kinds.yaml`
  - org: `<org_root>/missions/<type>/requirement-kinds.yaml` (every pack in the chain; last-matching-file wins)
  - project: `.kittify/charter-packs/missions/<type>/requirement-kinds.yaml` (wins over org/built-in; was `.kittify/doctrine/` in #5956's design, retired per FR-011)
- **Absent at every tier**: the loader returns the built-in default kind set for the type (absence is not a refusal).

## Models (`src/charter/offering/missions/requirement_kinds.py`)

- `RequirementKind` — frozen Pydantic, `extra="forbid"`: `prefix: str`, `label: str`, `glossary_term: str`, `must_map_to_wp: bool`.
- `RequirementKindDeclaration` — frozen, `extra="forbid"`: `schema_version: str`, `mission_type: str`, `kinds: list[RequirementKind]` (non-empty).
- Mirrors `ExpectedArtifactSpec`/`ExpectedArtifactManifest` (`expected_artifact_manifest.py`).

## API: `load_requirement_kinds(mission_type: str, repo_root: Path) -> RequirementKindDeclaration`

- **Home**: `src/charter/activation/manifest_loader.py`, beside `load_manifest`; module-level cache keyed `(mission_type, tuple(str(root) for root in chain))`.
- **Org resolution**: via `resolve_pack_chain(repo_root, strict=True)` — a declared-but-missing pack refuses (Divergence B).
- **Project tier**: added (Divergence A) — project wins.
- **Fail-closed**: a present-but-unparseable/non-mapping/schema-invalid file raises a `ManifestSchemaError`-shaped error (`RequirementKindsSchemaError` or the reused shape); never a silent fall-through to the default.
- **Sibling**: `resolve_org_requirement_kinds(chain, mission_type)` mirrors `resolve_org_expected_artifacts` (last-matching-file-wins, whole-file).

## State transitions

None — this is pure resolution/validation; no lifecycle state.
