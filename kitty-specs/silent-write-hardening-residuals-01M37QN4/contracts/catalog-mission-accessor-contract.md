# Contract — shared `catalog.mission` accessor (Finding B)

**Surface**: new `charter/activation/charter_yaml_io.py::read_catalog_field(repo_root, field)` (+ thin `read_catalog_mission(repo_root)`). Callers: `charter/generate.py::_read_catalog_mission_from_charter_yaml`, `charter_runtime/preflight/references_refresh.py::_read_catalog_mission_and_template_set`.

## Guarantees

1. **Single read path.** Exactly one accessor reads `charter.yaml` `catalog.<field>`; both former readers delegate to it. A repo grep for direct `catalog`→`mission` reads returns 0 outside the accessor. (NFR-003 / SC-002)
2. **Canonical parser.** The accessor uses `load_charter_yaml` (ruamel round-trip, `preserve_quotes`) — the same parser as the rest of the charter tooling. No second parser (`YAML(typ="safe")`) survives for this field.
3. **Absent/malformed result is uniform.** Missing file, absent `catalog`, absent field, or a malformed document yields the same well-defined absent result (`None`) to every caller, guarded by `(YAMLError, OSError, UnicodeDecodeError)`.
4. **No boundary violation.** Both callers already reach `charter.activation.*` (lazily); the delegation adds no new forbidden import edge.
5. **Behavior parity.** Each caller's observable behavior is unchanged for all valid documents (the fix removes divergence risk, not existing behavior).

## Acceptance

- **AC-B1**: both callers resolve the identical `catalog.mission` value through the accessor for a normal charter. (SC-002)
- **AC-B2**: for a `charter.yaml` with no `catalog.mission` (and for a malformed doc), the accessor returns the same absent result to every caller.
- **AC-B3**: grep proves exactly one `catalog.mission` reader remains. (NFR-003)
- **AC-B4** (optional campsite): `language_scope._read_compiled_languages` reads `catalog.languages` through the same accessor with no behavior change.
