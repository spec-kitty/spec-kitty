# Data model: reconcile run scope (#6728)

Scope: in-memory value objects inside `src/charter/activation/synthesizer/reconcile.py`. There is
no persistence, no serialized form and no external interface: the two enums below never leave the
process, and neither is written to a DRG overlay, a manifest or a JSON envelope.

## `RunScope` (enum value object)

| Member | Meaning | Dead `requires --> mission_type:*` edge is stripped when | `applies` edge is stripped when |
| --- | --- | --- | --- |
| `FULL` | the run re-emits the whole project overlay | the source is a synthesized (`PROJECT_*`) directive, wherever it sits | the source is a regenerated, synthesized reach-only artifact |
| `TOPIC_SCOPED` | the run re-emits only the targeted artifacts | the source is a synthesized `PROJECT_*` directive **that this run regenerated** | the source is a regenerated, synthesized reach-only artifact |

Derivation, owned by the member rather than by the caller:

```python
def dead_edge_filter(self, regenerated_urns: Collection[str] | None) -> Collection[str] | None:
    return regenerated_urns if self is RunScope.TOPIC_SCOPED else None
```

`None` on the left of that return means "no filter" — the pre-existing meaning of
`_is_dead_mission_type_edge`'s optional second argument, which is unchanged.

## `regenerated_urns` (parameter, unchanged)

An optional collection of the URNs (owners) the run re-emitted. `None` keeps its pre-existing
meaning: no filter, so every synthesized owner qualifies. This parameter predates the scope and is
deliberately **not** folded into it: the same set feeds both rules, and folding it in would make
`_graph_delta` (which has a fresh-node set) unable to say "no filter".

## Equivalence table (the mission's core invariant)

For one fixture — a regenerated synthesized tactic, an untargeted synthesized tactic, a synthesized
styleguide, a hand-authored styleguide, each with a legacy `applies` edge, plus a dead
`directive:PROJECT_001 --requires--> mission_type:*` edge on a regenerated and on a non-regenerated
directive:

| Input | `RunScope.FULL` | `RunScope.TOPIC_SCOPED` | Equivalent to (old API) |
| --- | --- | --- | --- |
| `applies`, regenerated owner | stripped | stripped | `regenerated_urns` filter, both scopes |
| `applies`, untargeted synthesized owner | kept | kept | unchanged by #6456 |
| `applies`, hand-authored owner | kept | kept | never qualifies (`synthesized_urns`) |
| dead edge, regenerated directive | stripped | stripped | both filters admit it |
| dead edge, non-regenerated directive | **stripped** | **kept** | `None` vs `regenerated_urns` |

Rules and invariants:

1. The scope never affects the `applies` rule (FR-005). Only the dead-edge rule reads it.
2. `RunScope.FULL` + any `regenerated_urns` is meaningful and used by `_graph_delta`: applies
   filtered, dead edge unfiltered.
3. `RunScope.TOPIC_SCOPED` with `regenerated_urns=None` degenerates to `FULL`'s dead-edge behaviour
   — the old `...` default's behaviour when no regenerated set was passed (spec edge case 1).
4. There is no third scope and no `None`/`...` scope: `run_scope` is required and keyword-only, so a
   caller cannot omit its intent (C-005).
5. `merge_project_overlay(topic_scoped: bool)` is the only place a boolean becomes a `RunScope`:
   `RunScope.TOPIC_SCOPED if topic_scoped else RunScope.FULL`.

## Validation rules

- `RunScope` members are exhaustive by construction; `is` comparisons keep the derivation total (a
  future third member must decide its `dead_edge_filter`, which is the intended forcing function).
- No validation is needed for `regenerated_urns`: it is a caller-owned collection, already optional
  and already trusted by the pre-existing filter.
