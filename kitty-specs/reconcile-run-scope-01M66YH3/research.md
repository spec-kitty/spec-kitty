# Discovery: an explicit run scope for legacy-edge reconciliation (#6728)

Mission: `reconcile-run-scope-01M66YH3`. Recorded 2026-10-30 before the spec was
finalised; the spec and plan build on this file rather than rediscovering it.

## D-1 — The defect is a signature shape, not a wrong answer

`src/charter/activation/synthesizer/reconcile.py` carries:

- `_is_legacy_applies(edge, synthesized_urns, regenerated_urns=None, *, dead_edge_regenerated_urns: Collection[str] | None | EllipsisType = ...)`
- `legacy_applies_edges(existing_overlay, synthesized_urns, regenerated_urns=None, *, dead_edge_regenerated_urns: ... = ...)`

with the body line `dead_filter = regenerated_urns if dead_edge_regenerated_urns is ... else dead_edge_regenerated_urns`.

So the public surface has three states (set / `None` / `...`) while callers pass two. The
`...` state is invisible at the call site and its meaning has to be read off the body.

Complete caller census on `main@512567eee7` (`grep -n`, `src/` + `tests/`):

| Caller | `regenerated_urns` | dead-edge filter today | Scope |
| --- | --- | --- | --- |
| `merge_project_overlay` (`reconcile.py`) | `updated_urns` | `updated_urns if topic_scoped else None` | topic-scoped / full |
| `legacy_applies_edges` default (`...`) | callers' 3rd arg | `regenerated_urns` | topic-scoped |
| `_graph_delta` → `legacy_applies_edges` (`reconcile.py`) | `fresh_node_urns` | `None` | full |
| `_graph_delta` → `_is_legacy_applies` (`reconcile.py`) | `fresh_node_urns` | `None` | full |
| `resynthesize_pipeline._validation_callback` | `{n.urn for n in updated_overlay.nodes}` | default (`...` → same set) | topic-scoped |
| `tests/charter/synthesizer/test_project_intent_directive.py` (2 calls) | `()` / omitted | default | n/a (no filter) |
| `tests/charter/synthesizer/test_styleguide_reach_only.py` (3 calls) | `{regen}` / `{untargeted}` / `set()` | default | n/a |
| `tests/charter/synthesizer/test_synthesize_reconcile.py` (2 calls) | `{"tactic:regen"}` / omitted | default | n/a |

Evidence: `grep -rn "legacy_applies_edges\|_is_legacy_applies\|EllipsisType\|dead_edge_regenerated_urns" --include="*.py" src tests`.

## D-2 — Grounding: still live, not superseded

- `git log -S dead_edge_regenerated_urns -- src/charter/activation/synthesizer/reconcile.py` →
  one commit, `f3b0a864b6` "fix(charter): full synthesize keeps legacy applies edges of
  artifacts it did not regenerate (#6456)". Nothing after it touched the sentinel.
- `gh pr list --search 6728` → no open or merged PR references the issue (the only hits
  are #6737, which shipped #6456, and an unrelated #5476).
- `grep 6728 docs/changelog/CHANGELOG.md` → no entry.
- The code on `main@512567eee7` still imports `EllipsisType` and defaults to `...`, so
  issue #6728 reproduces as written.
- Related history to respect: #6404/#6442 (legacy `applies` edges), #6443 (dead
  `PROJECT_* --requires--> mission_type:*` edge), #6456 (full run keeps the legacy edge of
  an artifact it did not regenerate; this is the behaviour that introduced the sentinel).

## D-3 — Prior art in the same module: the boolean

`merge_project_overlay(..., topic_scoped: bool = False)` already names the run scope, and
its docstring spells the two dead-edge behaviours out. That is why #6728 offers
"`topic_scoped: bool` matching `merge_project_overlay`" as one option: the module already
has a scope concept, and the sentinel is a second, implicit one.

## D-4 — Chosen shape: a `RunScope` enum that owns the derivation

Two candidates were weighed:

1. **`topic_scoped: bool = False`** on both functions. Smallest textual diff, zero new
   types, symmetric with `merge_project_overlay`. Weakness: a boolean argument at a call
   site reads as `topic_scoped=False`, and the *reason* the dead edge is filtered or not is
   still encoded in a body ternary; the issue asks for the meaning to be in the type.
2. **`RunScope` enum (`FULL`, `TOPIC_SCOPED`)** whose member owns
   `dead_edge_filter(regenerated_urns)`. The call site reads `run_scope=RunScope.FULL`, the
   ternary leaves `_is_legacy_applies`, and the enum is the one place that knows how a
   scope filters the dead-edge rule. Cost: one small class plus an import at five call
   sites.

Chosen: (2), because the single-authority principle (DIRECTIVE_044) plus the mission's own
purpose ("the meaning in the type") both point at naming the concept; (1) leaves the
derivation in a body branch and only documents the sentinel away.

`merge_project_overlay` keeps its exported `topic_scoped: bool = False` (C-001): it is not
the sentinel, it is used by tests and the pipeline, and rewriting it would widen a P3
typing change into a public-signature change of an unrelated function. It converts to the
enum in exactly one place.

## D-5 — Required, keyword-only, no default

`run_scope` is keyword-only and has **no default** on both functions. Any default silently
re-introduces "the scope you did not say" — the defect class the issue names. The cost is
five call sites (one in `resynthesize_pipeline.py`, three in `reconcile.py`, plus tests),
each of which now states its scope.

Consequence to note for review: the *old* default (`...`) behaved as `TOPIC_SCOPED`, so a
caller that omitted the argument and passed `regenerated_urns` must now pass
`RunScope.TOPIC_SCOPED` to keep its result. Only `resynthesize_pipeline` is in that
position in `src/`.

## Open questions carried into the plan

1. Should the enum be added to `__all__`? The module convention (charter, C-007) requires
   `__all__` to declare the module's public names and the dead-symbol gate requires each to
   have a caller in `src/`; `RunScope` has callers in `reconcile.py` itself.
2. Where do the new tests live: a new `tests/charter/synthesizer/test_reconcile_run_scope.py`
   or a section in the owning `test_synthesize_reconcile.py`? (Plan answer: the owning
   suite, so the contract stays with its owner and no issue-named file needs a fold verdict.)
3. Red-first form: the defect is a missing type, so the red is an `ImportError`/`TypeError`
   on the new API rather than a wrong answer. Behaviour equivalence is proven twice — the
   untouched existing suite before/after, plus new scope-vs-`merge_project_overlay`
   equivalence assertions on one fixture.
