# Tracer 01 — Pack chain authority + caller migration (IC-01, IC-02)

Append implementation notes here during implement. Seeded at planning.

- **resolve_pack_chain(repo_root, *, strict)** home: `src/charter/activation/layer_roots.py`. Absorbs `resolve_org_root_chain`.
- **Primitives** (`org_pack_config.py`): `resolve_org_roots` / `resolve_existing_org_roots` / `require_declared_org_roots` → module-private (authority-only callers).
- **Migration targets**: effective_set (`_scanned_ids`/`_declared_org_roots`/`_readable_roots`/`_fallback_ids`), preset_application (`_Roots.of`/`_available_mission_types`), activate/deactivate/_cascade_shared, context.py (re-point only), resolve_org_dirs (lenient re-point).
- Invariants: resolve_layer_roots dict unchanged (NFR-001); lenient byte-identical (NFR-004); _org_scan_dirs flat-wins unchanged (NFR-005).

## Trail
- (planning) seeded.
