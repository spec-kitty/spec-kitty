# Data Model: the `code_producing` capability

This mission adds no persisted entity and no new artifact. The "data" it touches is
the mission-type descriptor and the in-memory resolved bundle, described here so the
invariants are explicit and testable.

## Entity: `MissionType` (authored descriptor)

Location: `src/charter/offering/missions/models.py`, loaded from YAML under
`src/charter/offering/missions/mission_types/<id>.yaml`, or from a charter-pack /
org / project layer through `resolve_layered_mission_types`.

| Field | Type | Cardinality | Notes |
| --- | --- | --- | --- |
| `schema_version` | `int` | required, default `1` | unchanged |
| `id` | `str` | required | unchanged; kebab-case identifier pattern |
| `display_name` | `str` | required | unchanged |
| `extends` | `str \| None` | optional | unchanged |
| `action_sequence` | `list[str] \| None` | optional | unchanged |
| `path_conventions` | `dict[str, str] \| None` | optional | unchanged |
| `requires_substantive_spec` | `bool \| None` | optional | unchanged (`#6315`) |
| **`code_producing`** | **`bool \| None`** | **optional, default `None`** | **new.** `None` = undeclared, defer to the built-in default map. |

**Invariants**

- `model_config = ConfigDict(frozen=True, extra="forbid")` (unchanged). The field
  must therefore be *declared* here before any YAML may set it; an undeclared
  `code_producing:` key would raise at load, which is the desired fail-loud
  behaviour.
- The field is tri-state on purpose: `True` / `False` are authored decisions,
  `None` means "not declared, use the default". Collapsing `None` to `False` in
  the DTO would make "declared false" and "undeclared" indistinguishable and lose
  the ability for the built-in map to supply `True` for `software-dev`.

## Entity: `ResolvedMissionType` (in-memory bundle)

Location: `src/charter/activation/mission_type_profiles.py`.

| Member | Type | Resolved when | Notes |
| --- | --- | --- | --- |
| `mission_type` | `str \| None` | construction | `None` for the neutral/typeless bundle |
| `action_sequence` | `list[str]` | construction | hot path, unchanged |
| `wp_driven` | `bool` | construction | unchanged (`#6315`) |
| `requires_substantive_spec` | `bool` | first read (`cached_property`) | unchanged (`#6315`) |
| **`code_producing`** | **`bool`** | **first read (`cached_property`)** | **new**, backed by `_code_producing_thunk` |

**Invariants**

- The neutral bundle (`_neutral_context()`) answers `code_producing is False` — a
  typeless mission produces no code by definition, and the facet must never raise.
- A caller that reads only `action_sequence` triggers no additional roster or
  disk read. The thunk holds `(type_key, is_registered, pack_context)` — all
  already computed at construction — so the deferred read is the layered mission
  type roster only.
- `code_producing` is memoised: repeated reads do not re-read the roster.

## Resolution precedence (the capability's whole rule)

```
declared value on the resolved MissionType   (own layer, or inherited via the
                                              layered roster)
        │  if None
        ▼
BUILTIN_CODE_PRODUCING[mission_type]          (software-dev True;
                                               research / documentation / plan False)
        │  if absent
        ▼
False                                         (conservative default for any
                                               unknown / custom type)
```

On any exception during resolution, `code_producing_for` returns
`BUILTIN_CODE_PRODUCTING.get(mission_type, False)` — i.e. the same two lower rungs
without the declared-value rung.

## Built-in defaults table (the one owning list)

| Mission type | `code_producing` | Rationale |
| --- | --- | --- |
| `software-dev` | `true` | produces committed code; already gated today |
| `research` | `false` | produces analysis artifacts, not code |
| `documentation` | `false` | produces prose |
| `plan` | `false` | produces a plan |
| any custom / undeclared | `false` | conservative: no existing custom type silently gains code-rigour gates (`#6327`) |

## State transitions

None. The capability is a pure read; it neither writes `meta.json` nor participates
in the mission FSM. The only consumer-visible transition it affects is the
`in_progress → for_review` pre-flight verdict:

```
move-task WP --to for_review
  └─ _validate_ready_for_review
       ├─ Check 1: research artifacts      (all mission types, unchanged)
       └─ Check 2: worktree state          (was: mission_type == "software-dev")
            └─ now: code_producing(mission_type) is True
                 ├─ repo_root arm  → shared claim-base gate (unchanged)
                 └─ worktree arm   → currency / uncommitted / implementation commit /
                                     kitty-specs contamination (unchanged)
```

## Externally visible interface

One function, Python-internal, on an existing public seam:

```python
charter.activation.api.code_producing_for(repo_root: Path, mission_type: str) -> bool
```

Total, no raising (resolution errors fall back), no I/O contract of its own beyond
what `resolve_mission_type_context` already does. No HTTP, event, webhook or file
format changes; hence `meta.json` records `"contracts": "none"`.
