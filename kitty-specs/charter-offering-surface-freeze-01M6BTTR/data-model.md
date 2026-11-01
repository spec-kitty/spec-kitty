# Data model — frozen offering public surface census

The census is one YAML document with three sections plus a header. It is a
*contract record*, not runtime data: nothing under `src/` reads it.

## Header

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | `"1.0"`; a shape change bumps it and the reader's accepted set |
| `surface` | string | human label; must name the in-process Python contract, never an HTTP surface |
| `mission` | string | the mission slug that froze this revision |
| `issue` | int | `6285` |
| `frozen_at` | ISO date string | date the surface was frozen |
| `c003` | string | the single restatement of the ADR-0004 DTO direction; the `api.py` C-003 docstring and this string must agree on substance |

## `surface[]` — one row per exported symbol

| Field | Type | Rule |
|---|---|---|
| `name` | string | must appear exactly once; the ordered list must equal `charter.offering.api.__all__` |
| `origin` | dotted module path | must equal the module the `api.py` import statement names for this symbol (AST-derived) |
| `disposition` | enum | `PUBLIC` only. `DISPOSITION[origin]` (longest-prefix) must also be `PUBLIC` |
| `facades` | list of module paths | sorted; must equal the set of facade modules that `_FACADE_TABLE` records as re-exporting this symbol *from* `charter.offering.api` |
| `contract_kind` | enum | one of `enum`, `model`, `exception`, `protocol`, `dataclass`, `constant`, `function`; must match the runtime object |
| `today_type` | non-empty string | today's hand-written type, described for a consumer author |
| `signature` | string or null | for callables (functions **and** classes): the exact `inspect.signature(obj)` rendering; `null` for values |
| `dto_target` | non-empty string | the generated-DTO direction for this symbol (ADR-0004); descriptive, not a promised class name |
| `dto_status` | enum | `transitional` only. `final` is rejected — nothing on this surface is final until the contract work lands |

### Runtime kind derivation

| Runtime evidence | `contract_kind` |
|---|---|
| `isinstance(obj, enum.EnumMeta)` | `enum` |
| `inspect.isclass(obj)` and `issubclass(obj, BaseException)` | `exception` |
| `inspect.isclass(obj)` and `issubclass(obj, pydantic.BaseModel)` | `model` |
| `inspect.isclass(obj)` and `dataclasses.is_dataclass(obj)` | `dataclass` |
| `inspect.isclass(obj)` and `inspect.isabstract(obj)` | `protocol` |
| `inspect.isfunction(obj)` | `function` |
| anything else non-class | `constant` |

A changed runtime kind is a surface change and must be a census change.

## `reached_classification[]` — one row per reached offering path

| Field | Type | Rule |
|---|---|---|
| `path` | dotted module path | must be a key of the live `reached_offering_paths()` union (offering paths only) |
| `disposition` | string | must equal `DISPOSITION[path]` by longest prefix; covers `PUBLIC`, `FACADE-ONLY`, `TICKETED-BASELINE`, `CONSTRUCTION-ROUTED`, `INTERNAL-METADATA` |
| `on_surface` | bool | true iff the path is an `origin` in `surface[]` |
| `consumers` | list of repo-relative paths | the reaching files, sorted; recomputed from the live scan |
| `route` | string | for non-surface rows: how a consumer is sanctioned to reach it (`facade: charter.<name>`, `service`, `ratchet-allowlist`, `metadata`) |

## `public_contract_delta[]`

Every reached symbol that is needed by a runtime consumer but is **absent** from the
frozen surface. Expected empty. The gate recomputes the delta from
`reached_classification` (reached ∧ not `on_surface` ∧ disposition not in the
sanctioned non-public set) and fails when it disagrees with the declared list. A
non-empty entry is an operator decision; this mission may not add it silently.
