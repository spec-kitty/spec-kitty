# Error and diagnostic contract: charter-pack-cutover-01M491G6

| Code | Raised by | Replaces | Payload |
|---|---|---|---|
| `ACTIVE_CHARTER_CONFIG_INVALID` | `ActiveCharterConfigError` (mission create, charter commands `--json`) | `CHARTER_PACK_CONFIG_INVALID` | unchanged shape; golden `tests/core/golden/mission_create_refusals.json` updated; added to `src/charter/activation/ERROR_CODES.md` |
| `LEGACY_CHARTER_STATE` | CLI-root gate (FR-011) | — (new) | first finding, remedy text (see cli.md) |
| `DEFAULT_PRESET_MISSING` | `init` / `charter generate` / upgrade provisioning when the built-in `default` preset is absent | `DefaultCharterPackMissingError` | preset path |
| `PRESET_NOT_FOUND`, `PACK_NOT_FOUND`, `PRESET_ID_UNRESOLVED`, `PRESET_WOULD_OVERWRITE` | `charter activate --preset` | — (new) | pack, preset, ids / diff |
| `PRESET_INVALID` | `charter activate --preset`, `charter pack list`, `charter pack path --preset` (a preset file that fails the strict preset loader) | — (new; owner-approved 2026-10-07) | pack, preset file, offending field. A DRG load failure while checking ids is `PRESET_ID_UNRESOLVED`; an unreadable/invalid activation target is `ACTIVE_CHARTER_CONFIG_INVALID` |
| `RESYNTHESIS_FAILED` | `charter activate --preset --json --resynthesize` when the preset was written but the follow-up resynthesis failed | — (new; owner-approved 2026-10-07) | message states the preset was applied; error payload carries the applied-preset data |
| `RETIRED_PACK_FIELD` | pack validation and loading | — (new; was a generic "extra field" error) | file, field (`accompanies_doctrine_pack`, `doctrine_pack_id`), replacement |

All codes listed in the changelog Before/After (FR-017).
