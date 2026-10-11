# Contract — pack.yaml descriptor schema & load/validate behaviour

This mission has no network API. Its contracts are the `pack.yaml` schema, the CLI surface, and the error codes. This file is the testable contract implementers code against.

## `pack.yaml` schema (v2 — this mission)

```yaml
# round-trip: skip: field-shape sketch with placeholder values, not an instance that validates against PackDescriptor
pack_id: <ULID 26 chars>            # required, immutable
pack_version: <semver>              # required iff pack_level == built-in; optional otherwise
parent_pack: <handle> | null        # optional
name: <string>                      # required
pack_level: built-in | org | project   # REQUIRED (new)
requires_core: <version-specifier>  # optional (new) e.g. ">=4.0,<5.0"
active_charter: <pack-relative path> # optional (new) e.g. org-charter.yaml
pack_drg: <pack-relative path>      # optional (new) e.g. drg/fragment.yaml
```

Backward compatibility: a v1 `pack.yaml` (the four original fields) is **not** valid under v2 for an org pack during the deprecation window — it loads with a `PACK_LEVEL_MISSING` warning; a project pack is migrated (see migration contract). No field is removed or renamed.

## Error / diagnostic codes

| Code | When | Surface | Severity |
|------|------|---------|----------|
| `PACK_LEVEL_MISMATCH` | declared `pack_level` ≠ configured position | load / `validate` | refuse (fail) — names file, declared, configured |
| `PACK_LEVEL_MISSING` | `pack.yaml` present, no `pack_level` | load / `validate` | WARN now (names the file to add); refuse only when the deprecation switch is flipped |
| `schema_invalid` | unparsable `requires_core`, unknown `pack_level` value, extra field | `validate` descriptor leg | fail |
| `RETIRED_PACK_FIELD` | a retired field present (unchanged) | load | fail |

## CLI surface

- `spec-kitty charter pack validate <pack_path>` — branches on declared `pack_level`; checks the resolved active-charter + DRG paths for the level (FR-008/009).
- `spec-kitty charter pack regenerate-graph [--pack-root <dir>] [--check]` — `--pack-root` (new) targets a pack outside core for both the write path and `--check` (FR-013); default (no flag) byte-unchanged.

## Resolution seam (FR-009)

`resolve_pack_layout(pack_root, descriptor) -> (active_charter_path | None, drg_path)`:
- `active_charter_path` = `pack_root / descriptor.active_charter` if set, else the per-level convention (org → `org-charter.yaml`; built-in/project → none).
- `drg_path` = `pack_root / descriptor.pack_drg` if set, else per-level convention (org → `drg/fragment.yaml`; built-in → sharded `*.graph.yaml` root; project → `graph.yaml`).
- Paths must resolve inside `pack_root` (no `..` escape) or `validate` reports an error at the resolved path.
- The exact function name/location is an implementation choice for `/spec-kitty.tasks`; the contract is: ONE seam, descriptor-first, convention-fallback, routed through by every existing filename lookup.

## `requires_core` compatibility check (FR-014)

`check_requires_core(descriptor, core_version) -> bool | diagnostic`: a reusable predicate #3504 vendor tooling can call. Absent `requires_core` ⇒ no constraint (passes). Present ⇒ `core_version in SpecifierSet(requires_core)`.

## Clean-tree digest (FR-015)

`clean_tree_digest(pack_root, *, kinds=None) -> str`: SHA-256 over enumerated known-files, LF-normalized, deterministic across `git archive` export / worktree / installed copy; ignores `__pycache__`/untracked noise by construction. **Separate** from `snapshot_sha256` (unchanged).

## Migration contract (FR-010)

`m_*_pack_level_backfill`: for each existing **project** pack lacking `pack.yaml`, write one with `pack_level: project` + a minted `pack_id`. Config-aware discovery; never `mkdir`; skips `packs/built-in` and `packs/internal`; never clobbers an authored `pack.yaml` (adds `pack_level` only if absent; never overwrites a differing `pack_id`).
