# Design decisions

## 2026-11-01 — seed
- One contract module (`scripts/docs/_dockitty_contract.py`) owns slug, publication, excluded folders, persona resolution, immutable set.
- Line-level frontmatter block replacement, not a YAML round-trip, so untouched keys keep their bytes.
- `guidance_text`: persona-derived sentence (DM `01M6BRRS43THXH8SZ861AFG8M3`).
- Unpublished `related` targets → `external_references` (DM `01M6BRRXG0MVX09DH92W1NTEWP`); deviates from the issue's "body link or drop", flagged for the operator.
- Excluded trees migrated too, so readers carry one shape.
- Not classified as a bulk edit (schema transformation, guarded by shape + body tests).
- Body-hash test is in-memory over the real corpus plus a `--verify-against` run, not a permanent git comparison (would fail later legitimate ADR amendments such as #6902).
