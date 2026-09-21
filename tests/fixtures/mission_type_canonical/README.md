# Fixtures: mission-type-canonical-source (#3831 #4088)

Static, checked-in consumer-project fixtures backing the mission
`mission-type-canonical-source-01M302V9`. They exist because, at the time
this WP was scoped, **no** fixture existed under `tests/` for an
org-activated custom mission type, nor for a pre-migration
`.kittify/overrides/missions/` override (spec.md, "Consumer census &
brownfield seam notes"). Shapes are mined from real callers/tests, never
invented:

- Org-pack `mission_types/<id>.yaml` shape: `charter.offering.missions.models.MissionType`
  (`schema_version`/`id`/`display_name`), `packs/built-in/missions/mission_types/*.yaml`.
- `charter_packs.org.packs` config block: `tests/doctrine/test_org_pack_subdir.py`,
  `tests/doctrine/drg/test_org_pack_config_resolve_existing_org_roots.py`,
  this repo's own `.kittify/config.yaml`. (`charter_packs` is the current
  canonical top-level key per `charter.offering.drg.org_pack_config`
  CR-04; the `doctrine.org.packs` spelling referenced in the WP prompt/spec
  is the retired-but-still-read legacy alias for the same block.)
- `.kittify/doctrine/mission_types/<type>/governance-profile.yaml` shape:
  `tests/charter/test_mission_type_profile_override.py`.
- `mission.yaml` / `MissionConfig` schema: `src/specify_cli/mission.py`,
  `src/specify_cli/missions/software-dev/mission.yaml`.
- `.kittify/overrides/missions/<type>/mission.yaml` precedence tier:
  `src/specify_cli/runtime/resolver.py::resolve_mission()` (Tier 1).
- `meta.json` shape: this mission's own `meta.json` (mission-identity model,
  083+).

## Tree

```
mission_type_canonical/
├── org_activated_custom_type/           # T001 (SC-001 / #3831)
│   ├── .kittify/config.yaml             # charter_packs.org.packs + mission_type_activations
│   ├── org-packs/acme-doctrine/
│   │   └── mission_types/docs-audit.yaml   # id=docs-audit, display_name="Docs Audit Kitty"
│   └── kitty-specs/001-audit-public-docs/meta.json   # mission_type: docs-audit
│                                          # NOTE: deliberately no .kittify/missions/ dir.
│
└── project_override/                    # T002 (SC-002 / #4088)
    ├── legacy/                           # pre-migration override home (used by T004's red repro)
    │   ├── .kittify/
    │   │   ├── config.yaml
    │   │   └── overrides/missions/software-dev/mission.yaml   # name: "Override Kitty"
    │   └── kitty-specs/001-legacy-override-feature/meta.json  # mission_type: software-dev
    │
    └── canonical/                        # post-migration target home (fixture only; not yet
        ├── .kittify/                     # exercised by a red repro -- reserved for WP05's
        │   ├── config.yaml               # migration/doctor tests)
        │   └── doctrine/mission_types/software-dev/governance-profile.yaml
        └── kitty-specs/001-canonical-override-feature/meta.json
```

## Consumers

- `tests/specify_cli/test_org_mission_type_resolution.py`:
  - `TestOrgActivatedCustomMissionType` (T003) drives
    `org_activated_custom_type/` through
    `specify_cli.mission.get_mission_for_feature()` and pins the #3831 bug:
    the loader is org-blind (only checks `.kittify/missions/<type>/` and the
    packaged missions dir), so a typed-but-org-only mission silently falls
    back to the packaged `software-dev` mission ("Software Dev Kitty")
    instead of resolving `docs-audit`'s own identity.
  - `TestProjectMissionTypeOverride` (T004) drives
    `project_override/legacy/` through the same entry point and pins the
    #4088 bug: `.kittify/overrides/missions/<type>/mission.yaml` is never
    consulted by that loader, so the project's `"Override Kitty"` override
    is silently ignored in favour of the packaged default.

Both repros are expected to be RED until the loader is rewired onto the
charter `ResolvedMissionType` source (later WPs in this mission).
