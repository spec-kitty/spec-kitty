# Contract: `doctor doctrine --json` additive keys (under `profile_health.org_drg`)

All keys are additive. The frozen top-level `profile_health` key set (#5729) is unchanged. None of these keys is emitted when no org packs are configured (FR-012).

| Key | When present | Shape |
|---|---|---|
| `unsanctioned_overrides` | existing; non-empty only | `[{urn, kind, why, legacy_template?: {path, reason}}]` |
| `sanctioned_overrides` | NEW; non-empty only | `[{urn, kind, pack, source: "consumer"\|"pack", reason}]` |
| `pack_sanction_errors` | NEW; non-empty only | `[str]`. Each message is also appended to `errors`, which drives RC=1. |
