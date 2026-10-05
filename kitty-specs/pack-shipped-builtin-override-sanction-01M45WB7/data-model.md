# Data Model: Pack-shipped built-in override sanction

## Files

### Consumer allowlist: `<repo>/.kittify/doctrine/replaceable-builtins.yaml`
```yaml
replaceable_builtins:            # unchanged
  - urn: directive:SOME_BUILTIN
    reason: Why we replace it.   # required (non-empty) for directives
revoked_pack_sanctions:          # NEW, optional, consumer-only
  - urn: directive:MINUTES_STAND_ALONE   # withdraw every pack's sanction for this URN
    reason: optional
  - pack: doctrine-org                   # withdraw all sanctions delivered by this configured pack
```
- **`revoked_pack_sanctions` entries:** each one has exactly one of `urn` or `pack`, plus an optional string `reason`. Anything else makes the file malformed. A malformed consumer file is reported as an error, and the consumer allowlist is treated as empty. A `pack` entry that names a pack that is not configured (exact, case-sensitive match) is an error.
- **Unknown top-level keys:** ignored, for forward compatibility.

### Pack sanction: `<pack root>/replaceable-builtins.yaml`
The grammar is the same `replaceable_builtins: [{urn, reason}]`.
- **Errors that void this pack's sanctions:** a `revoked_pack_sanctions` key, a path that is not a regular file, a path that escapes the pack root, and unreadable or invalid YAML. Each is recorded in `pack_sanction_errors` and makes the report unhealthy.
- **Absent file:** an empty sanction.

## Entities (in `charter.offering.drg.override_policy`)

| Entity | Fields | Notes |
|---|---|---|
| `ReplaceableBuiltin` | `urn`, `reason` | unchanged |
| `ReplaceableBuiltinsPolicy` | `entries`, `revoked_urns` (default ∅), `revoked_packs` (default ∅) | existing constructions remain valid |
| `EffectiveOverridePolicy` | `consumer`, `packs: Mapping[str, Policy]`, `pack_errors`, `consumer_error: str \| None`, `revocation_errors` | built by one loader (FR-013); a malformed consumer file is recorded, not raised, and treated as empty (fail-closed) |
| `OverriddenBuiltin` | `urn`, `kind`, `pack` | `pack` comes from `org:<pack>` provenance |
| `SanctionedOverride` | `urn`, `kind`, `pack`, `source` ∈ {`consumer`, `pack`}, `reason` | |
| `UnsanctionedOverride` | `urn`, `kind`, `why` | unchanged shape; `why` contains `replaceable-builtins` |

Retired: `find_unsanctioned_overrides`, `find_overridden_builtin_urns` (superseded; single authority). `load_replaceable_builtins` becomes private.
| `OverrideAdjudication` | `sanctioned`, `unsanctioned` | pure result |

## Decision table (FR-003 / FR-004 / FR-007)
This reproduces spec.md § "Sanction decision table". The consumer allowlist is checked first. A revocation removes only the pack row. Another pack's sanction never applies.

## Invariants
1. Fail closed: no valid sanction means unsanctioned.
2. Scoping: only the pack named in the surviving node's provenance can sanction it.
3. Reasons: a directive needs a non-empty reason from the source that sanctions it.
4. Isolation: one bad pack file voids only that pack.
5. Purity: `adjudicate_overrides` and the `find_*` helpers do no I/O.
