# Data Model — mission-type capability contract on the offering seam

No persistence, no state, no new files on disk. Three in-memory symbols, one property on the
existing resolved DTO. Values are booleans derived from the mission type's own resolution.

## Entities

### `MissionTypeCapabilities` (`charter.offering.missions.capabilities`)

The immutable, transportable answer to "what can this mission type do?".

| Field | Type | Default | Meaning |
|---|---|---|---|
| `wp_driven` | `bool` | `False` | The mission type iterates work packages — its action sequence declares an `implement` step (kernel rule, single authority). Advisory where the frozen DAG is authoritative (#6330 item 3). |
| `requires_substantive_spec` | `bool` | `False` | The mission type's authored rigour requirement: a stub spec may not satisfy it. Unauthorised/undeclared defaults to `False` (conservative). |

- Frozen (`dataclass(frozen=True)`), compares by value, no identity semantics.
- Both defaults are `False` so that constructing an empty snapshot is the conservative answer,
  never an optimistic one.
- #6327 will add `code_producing` as a third field with a conservative `False` default; that is
  an additive change to this table, not a reshape.
- Hashed (frozen dataclass) so it can key a cache/lookup keyed by capabilities.

### `MissionTypeCapabilitySource` (`charter.offering.missions.capabilities`)

A `@runtime_checkable` `Protocol` with two read-only properties:

```python
class MissionTypeCapabilitySource(Protocol):
    @property
    def wp_driven(self) -> bool: ...
    @property
    def requires_substantive_spec(self) -> bool: ...
```

- The protocol, not a concrete base type, is the contract: any resolver result in any tier can
  satisfy it structurally, so the seam never names the resolver's class. `ResolvedMissionType`
  also declares it as a base class (nominal opt-in) so the conformance is visible in the type
  system; the protocol is properties-only, so it contributes no fields or behaviour.
- `runtime_checkable` gives `isinstance(obj, MissionTypeCapabilitySource)` with the documented
  caveat: it checks attribute presence, not the annotated type. The seam test's negative control
  uses an object that lacks a capability entirely.

### `capabilities_of(source)` (`charter.offering.missions.capabilities`)

The single read entry point. Returns a `MissionTypeCapabilities` built from the source's own
attributes (`bool(...)`-coerced so a truthy 0/1 from a YAML-backed resolver arrives as a real
`bool`). Raises `AttributeError` for a source missing a capability — a non-conforming object is a
programming error, never a silent `False`.

### `ResolvedMissionType.capabilities` (`charter.activation.mission_type_profiles`)

A plain `@property` on the existing frozen DTO returning `capabilities_of(self)`. Additive: the
existing `wp_driven` field and `requires_substantive_spec` `cached_property` are unchanged and
remain the single producers of the values.

## Relationships

```
                      reads its own attributes
ResolvedMissionType ───────────────────────────► MissionTypeCapabilities
   │  (activation tier)        capabilities_of()          (offering tier)
   │        ▲
   │        └── imported through charter.missions (the facade) -> charter.offering.api
   └─ conforms to ──► MissionTypeCapabilitySource  (offering tier)
```

Dependency direction: `charter.activation` → `charter.offering` (the sanctioned direction).
`charter.offering.missions.capabilities` imports nothing from `charter.activation`, from
`pydantic`, or from any I/O module.

## State transitions

None. The contract is a pure function of the mission type's resolved action sequence and authored
rigour declaration. No lifecycle, no ledger, no migration.

## Validation rules

| Rule | Enforced by |
|---|---|
| Both capabilities are readable through `charter.offering.api` | seam test (FR-001) |
| A source missing a capability fails the protocol check | seam test negative control (FR-002) |
| `capabilities_of` raises rather than defaults for a non-conforming source | seam test (FR-003) |
| The DTO's snapshot equals its own two attributes for all four built-ins | seam test parametrisation over `software-dev`/`research`/`documentation`/`plan` (FR-004) |
| Typeless mission yields `(False, False)` without raising | seam test (FR-008) |
| Custom type declaring `requires_substantive_spec: true` yields `True` | seam test (FR-008) |
| Importing the contract registers no `charter.activation` module | subprocess layering test with positive control (FR-007, NFR-002) |
| Origin module is `PUBLIC` in the census | `test_doctrine_census` / `test_charter_offering_public_surface` (FR-006) |
