# Quickstart: verify the reconcile run scope by hand (#6728)

Audience: a maintainer reviewing the diff. Reads the code in
`src/charter/activation/synthesizer/reconcile.py`; runs no CI.

## 1. The sentinel is gone

```bash
grep -n "Ellipsis\|dead_edge_regenerated_urns" src/charter/activation/synthesizer/reconcile.py
# expected: no output
grep -n "run_scope" src/charter/activation/synthesizer/reconcile.py
# expected: the RunScope class, both signatures, the merge mapping, and _graph_delta
```

## 2. Both scopes strip the dead project-intent edge differently

In a REPL from the repository root (`uv run python`):

```python
from charter.activation.synthesizer.reconcile import (
    RunScope, legacy_applies_edges,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

directive = DRGNode(urn="directive:PROJECT_001", kind=NodeKind.DIRECTIVE, label="intent")
dead = DRGEdge(source=directive.urn, target="mission_type:software-dev", relation=Relation.REQUIRES)
graph = DRGGraph(schema_version="1.0", generated_at="S", generated_by="t", nodes=[directive], edges=[dead])

legacy_applies_edges(graph, (), run_scope=RunScope.FULL)          # -> (dead,)  full run strips it
legacy_applies_edges(graph, (), run_scope=RunScope.TOPIC_SCOPED)  # -> ()       untouched owner keeps it
legacy_applies_edges(graph, (), {directive.urn}, RunScope.TOPIC_SCOPED)  # -> (dead,) regenerated owner
```

The third call is the point of the scope: a topic-scoped run strips the dead edge only where it
regenerated the owner.

## 3. The scope does not touch the `applies` rule

```python
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
regen = DRGNode(urn="tactic:regen", kind=NodeKind.TACTIC, label="r")
other = DRGNode(urn="tactic:untargeted", kind=NodeKind.TACTIC, label="u")
edge = lambda src: DRGEdge(source=src, target="directive:DIRECTIVE_003", relation=Relation.APPLIES)
graph = DRGGraph(schema_version="1.0", generated_at="S", generated_by="t",
                 nodes=[regen, other], edges=[edge(regen.urn), edge(other.urn)])
synth = {regen.urn, other.urn}

for scope in (RunScope.FULL, RunScope.TOPIC_SCOPED):
    assert [e.source for e in legacy_applies_edges(graph, synth, {regen.urn}, scope)] == ["tactic:regen"]
```

## 4. `merge_project_overlay` still speaks boolean

```python
from charter.activation.synthesizer.reconcile import merge_project_overlay
merge_project_overlay(existing_overlay=graph, updated_overlay=updated, synthesized_urns=synth)                     # FULL
merge_project_overlay(existing_overlay=graph, updated_overlay=updated, synthesized_urns=synth, topic_scoped=True)  # TOPIC_SCOPED
```

## 5. The pinned tests

```bash
uv run pytest tests/charter/synthesizer/test_synthesize_reconcile.py -k "run_scope" -q
uv run pytest tests/charter/synthesizer/ tests/charter/test_project_registration.py -q
uv run pytest tests/architectural/test_no_dead_symbols.py -q
```

Expected: the first two green (the second is the behaviour-equivalence proof for the whole owning
suite), the third green because `RunScope` has callers in `src/`.
