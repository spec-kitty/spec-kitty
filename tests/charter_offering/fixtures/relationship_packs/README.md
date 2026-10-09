# Relationship migration fixtures (WP07)

These org-pack fixtures back the relationship-migration tests
(`tests/charter_offering/test_relationship_migration.py`) and the WP06 field-rejection
tests. Each pack follows the canonical org-pack layout: `<pack>/drg/fragment.yaml`.

| Pack | Scenario | Purpose |
|------|----------|---------|
| `lineage-pack/` | Scenario 1 | A profile-to-profile `specializes_from` **edge** (lineage authored the new way). Must load and merge cleanly. |
| `augment-all-kinds-pack/` | Scenario 10 | `enhances` / `overrides` **edges** spanning a directive, toolguide, mission-step-contract, and mission-type. Proves augmentation edges author across every topology-bearing kind. Must load and merge cleanly. |
| `legacy-field-pack/` | Negative | Still authors the relationship as an artifact **field** (`specializes-from:`), not an edge. This is the deprecated form WP06 turns into a hard error; the pack exists so WP06's rejection test has a concrete target. It is **expected to be rejected** once WP06 lands. |

Authoring rule (FR-001/FR-003/FR-004, NFR-007): relationships are DRG **fragment
edges**, never artifact fields. `lineage-pack` and `augment-all-kinds-pack`
demonstrate the canonical form; `legacy-field-pack` is the anti-pattern.
