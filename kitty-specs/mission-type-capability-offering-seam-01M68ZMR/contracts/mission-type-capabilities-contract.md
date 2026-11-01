# Contract — mission-type capability contract on the offering seam (#6331)

**Seam**: `charter.offering.api` (the frozen charter offering public surface).
**Origin module**: `charter.offering.missions.capabilities` (census disposition `PUBLIC`).
**Door**: `src/charter/missions.py` facade re-exports the three symbols from the seam.
**Versioning**: in-process Python contract; additive-only within 4.x.

## Exported surface (additive; exactly three symbols)

```python
from charter.offering.api import (
    MissionTypeCapabilities,      # frozen value object
    MissionTypeCapabilitySource,  # runtime-checkable Protocol
    capabilities_of,              # (source) -> MissionTypeCapabilities
)
```

### `MissionTypeCapabilities`

```python
@dataclass(frozen=True)
class MissionTypeCapabilities:
    wp_driven: bool = False
    requires_substantive_spec: bool = False
```

- Immutable, value-equal, hashable.
- Field defaults are the conservative answer; the class never implies a capability a mission type
  did not declare.

### `MissionTypeCapabilitySource`

```python
@runtime_checkable
class MissionTypeCapabilitySource(Protocol):
    @property
    def wp_driven(self) -> bool: ...
    @property
    def requires_substantive_spec(self) -> bool: ...
```

### `capabilities_of`

```python
def capabilities_of(source: MissionTypeCapabilitySource) -> MissionTypeCapabilities: ...
```

## Conformance

| Object | `wp_driven` | `requires_substantive_spec` |
|---|---|---|
| built-in `software-dev` | `True` | `True` |
| built-in `research` | `False` | `True` |
| built-in `documentation` | `False` | `False` |
| built-in `plan` | `False` | `False` |
| typeless mission (no mission type) | `False` | `False` |
| custom type declaring `requires_substantive_spec: true` | per its action sequence | `True` |
| custom/undeclared type | per its action sequence | `False` (conservative default) |

`ResolvedMissionType` conforms to `MissionTypeCapabilitySource` (declared as a base class, and
structurally: the protocol is properties-only) and exposes `capabilities` — a
`MissionTypeCapabilities` built from its own attributes via `capabilities_of`, reached through
the `charter.missions` facade.

## Invariants

1. **Boundary** — `charter.offering.missions.capabilities` imports nothing from
   `charter.activation`; importing it registers zero `charter.activation*` modules. ADR
   `2026-10-16-1` (Amendment 2026-10-19) records the verified zero-edge dependency direction.
2. **Single authority** — the capability values have exactly one producer: the resolved mission
   type. `capabilities_of` derives, it does not decide; no built-in capability table is copied
   into the offering tier.
3. **Fail loud** — a source that does not answer both capabilities raises `AttributeError`.
   There is no defaulting path for a non-conforming object.
4. **No new hot-path work** — the read touches only attributes already resolved on the object in
   hand; `requires_substantive_spec` stays behind its existing memoised `cached_property`.
5. **Additive only** — the seam manifest stays sorted; the three symbols are additive and carry
   no rename of an existing symbol.
6. **Advisory where the DAG is authoritative** — `wp_driven` is a derived advisory flag on the
   DTO; the runtime WP-advance guard reads the frozen DAG (#6330 item 3).

## Out of contract (deliberately)

- `resolve_mission_type_context` and `ResolvedMissionType` themselves are **not** on the seam.
  They live in `charter.activation`, above the seam; importing them into `charter.offering` would
  invert the recorded dependency direction. A consumer reads the capabilities of a resolved
  object it already holds.
- `code_producing` (#6327) and the contract's internal hardening (#6330) are separate changes.
