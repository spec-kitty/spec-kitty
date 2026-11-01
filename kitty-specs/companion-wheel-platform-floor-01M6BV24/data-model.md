# Data Model: Platform floors

The Mission's data is entirely in-process: a floor is read, compared, and reported. Nothing is
persisted, and no released artifact changes shape.

## PlatformFloor

The oldest OS a binary needs, expressed the way the wheel tag expresses it.

| Field | Type | Rule |
|-------|------|------|
| `kind` | `"glibc"` \| `"macos"` | Which platform's floor this is. `win_amd64` states no minimum, so it has no kind. |
| `value` | `str` | `<major>_<minor>`, both decimal — `2_39`, `11_0`, `2_2`. The same spelling the tag uses. |
| `asset` | `str` \| `None` | The pinned asset the value was measured from; `None` for a declared floor. |

**Invariants**

- A value never carries a patch component: `GLIBC_2.2.5` normalizes to `2_2`, and `minos` `12.1.3` to `12_1`, because PEP 600 manylinux tags and `macosx_*` tags have no patch component.
- Comparison is numeric per component, never lexicographic: `2_39` > `2_9`, `11_0` > `9_0`.
- A floor string must match `^\d+_\d+$`; anything else is a refusal before any wheel is built.

## WheelFloor

The floor one platform wheel must claim: the maximum measured floor over the binaries that wheel
carries, plus the asset that sets it.

| Field | Type | Rule |
|-------|------|------|
| `floor` | `PlatformFloor` | Highest by numeric comparison over `binaries`. |
| `asset` | `str` | The asset whose measured floor equals `floor`; the first such asset in sorted order, so the message is deterministic. |

**Invariants**

- The maximum is taken per wheel, not across the whole pin set: a target that carries only the write service cannot inherit the charter service's floor.
- A wheel with no binaries that state a floor (static ELF, no `GLIBC_*` needs) has no `WheelFloor`; the declared floor stands unchanged.
- An unreadable asset raises before a `WheelFloor` exists, so no partial result can be compared or reported as passing.

## DeclaredFloors

The build inputs the tag is allowed to claim.

| Field | Type | Rule |
|-------|------|------|
| `glibc` | `str` | `--glibc-floor`, default `2_39`. |
| `macos` | `str` | `--macos-floor`, default `11_0`. |

**Invariants**

- Both are validated on every build, whether or not that platform is pinned (the existing glibc rule, now symmetric).
- A measured floor above the declared floor is a refusal (`SERVICE_PLATFORM_FLOOR_EXCEEDED`); at or below is silence. The declared value is what the tag says either way (constraint C-001).

## State transitions

```
pinned asset bytes
  ├─ digest mismatch ................. SERVICE_BINARY_DIGEST_MISMATCH (unchanged, first)
  ├─ not a readable native binary .... SERVICE_PLATFORM_FLOOR_UNREADABLE
  └─ readable
       ├─ no floor stated ............ no WheelFloor → declared floor stands
       └─ floor stated
            ├─ ≤ declared floor ...... build proceeds, tag unchanged
            └─ > declared floor ...... SERVICE_PLATFORM_FLOOR_EXCEEDED (no wheel written)
```

`--verify` replays the same ladder over the bytes inside each wheel, where the digest mismatch
step has already passed, and reports the last two as problems on stderr.

## Key Entities in the spec

- **Pinned asset** — a released service binary named by file name and SHA-256 in `pins/<service>.source.yaml`. Read-only here: this Mission never writes a pin.
- **Wheel tag** — `py3-none-manylinux_<glibc>_<arch>`, `py3-none-macosx_<macos>_<arch>` or `py3-none-win_amd64`, produced by the companion writer's `platform_tag`. Its floor component is the declared floor.
