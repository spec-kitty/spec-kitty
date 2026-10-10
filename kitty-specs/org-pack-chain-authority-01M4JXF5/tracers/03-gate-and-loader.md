# Tracer 03 — Empty-allowlist gate + requirement-kinds loader seam (IC-05, IC-06)

Append implementation notes here during implement. Seeded at planning.

- **Gate**: `tests/architectural/test_org_pack_chain_single_authority.py` mirroring test_remote_contact_owner.py. Module-ownership discriminator; empty allowlist; file-floor + planted-violation + owner-bypass controls. Lands LAST (after IC-02/03/04).
- **Loader**: `requirement_kinds.py` (RequirementKind/RequirementKindDeclaration, frozen, extra=forbid) + `load_requirement_kinds` in manifest_loader.py; `resolve_org_requirement_kinds` sibling of resolve_org_expected_artifacts.
  - Divergence A: adds project tier `.kittify/doctrine/missions/<type>/requirement-kinds.yaml` (project wins).
  - Divergence B: org chain via strict resolve_pack_chain (fail-closed), not lenient resolve_existing_org_roots.
  - Fail-closed: invalid file → ManifestSchemaError-shaped; missing-declared pack → strict chain refusal.

## Trail
- (planning) seeded.
