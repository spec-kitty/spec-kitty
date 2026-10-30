# Implementation Plan: An explicit run scope for legacy-edge reconciliation

**Branch**: `issue-6728-reconcile-run-scope` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/reconcile-run-scope-01M66YH3/spec.md`; discovery in [research.md](research.md).

**Branch contract** (`spec-kitty agent mission setup-plan`, 17:48Z): current branch `issue-6728-reconcile-run-scope`; planning/base branch `issue-6728-reconcile-run-scope`; completed changes merge into `issue-6728-reconcile-run-scope`; the protected mainline `main` is never a push target (`branch_matches_target` is reported `false` only because `meta.json` still records `target_branch: main`; the resolver's own planning/merge target is this branch).

## Summary

Replace the `EllipsisType` sentinel that #6456 added to the legacy-edge reconciler with a typed
`RunScope` enum. Two functions change signature (`_is_legacy_applies`, `legacy_applies_edges`:
`dead_edge_regenerated_urns: … | EllipsisType = ...` → a required keyword-only
`run_scope: RunScope`), the enum owns the derivation of the dead-edge filter, and the five call
sites state their scope. No behaviour changes; the two scopes are pinned by tests that fail if the
sentinel semantics drift.

## Technical Context

**Language/Version**: Python 3.11+ (repo requires 3.11; `from __future__ import annotations` in the module)
**Primary Dependencies**: stdlib only (`enum`, `dataclasses`, `typing`); `charter.offering.drg.models` (`DRGEdge`, `DRGGraph`, `Relation`) for the value types; no new dependency
**Storage**: N/A (in-memory graph reconciliation; on-disk YAML is written by the caller, untouched)
**Testing**: pytest — `tests/charter/synthesizer/` (owning suite) plus `tests/charter/test_project_registration.py` for the `merge_project_overlay` callers; `mypy --strict` on the touched files
**Target Platform**: the Spec Kitty CLI (Linux/macOS/Windows), library-level change
**Project Type**: single project (`src/charter/activation/synthesizer/`)
**Performance Goals**: N/A — removes a branch from a per-edge predicate; no measurable change
**Constraints**: no behaviour change; no new module; the exported `merge_project_overlay(topic_scoped=…)` keyword keeps working
**Scale/Scope**: 1 source module (`reconcile.py`), 1 caller module (`resynthesize_pipeline.py`), 3 test modules; ~40 changed lines in `src/`

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority (Governing Principles, DIRECTIVE_044) | `RunScope` becomes the one owner of what a run scope means; the derivation stops being a body ternary repeated per caller. `merge_project_overlay` keeps its bool but converts in exactly one place (C-003). |
| ATDD-first / red-first (ATDD-First Discipline, DIRECTIVE_034) | A failing test lands before the implementation commit; the defect is a missing type, so the red is an `ImportError` on `RunScope` plus the behaviour-equivalence assertions that follow. |
| Test remediation discipline (DIRECTIVE_041) | The new tests guard real behaviour (which edges a run strips) and the standing invariant the issue states ("no `Ellipsis` default in these signatures"); no characterization-only or shape-only filler beyond that one signature guard, which is the issue's own acceptance criterion. |
| Smallest viable diff (tactic, RECONCILE_CHANGE_SCOPE_TENSIONS) | Two signatures, one new enum, five call sites, one test section. No dependency, no new module, no export widening beyond `__all__`. |
| Locality of change (DIRECTIVE_024) | `merge_project_overlay`'s exported bool stays; `_is_dead_mission_type_edge` keeps its plain optional-set filter. |
| Campsite cleaning (DIRECTIVE_025) | In scope: `_is_legacy_applies` loses its sentinel branch (complexity down, not up, NFR-003); the docstrings that describe the sentinel are rewritten. No pre-existing litter in these two functions beyond that. |
| `__all__` convention (C-007) | `RunScope` is added to `__all__`, and the dead-symbol gate is satisfied because a *different* module (`resynthesize_pipeline.py`) imports it — intra-module use is deliberately not counted for `__all__` members. |
| No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION) | Targeted suites only: `tests/charter/synthesizer/`, `tests/charter/test_project_registration.py`, `tests/architectural/test_no_dead_symbols.py` (the one arch gate the `__all__` edit implicates). |
| Terminology canon | "run scope", "topic-scoped run", "legacy edge" — no `feature*` language. |
| Bulk-edit gate (DIRECTIVE_035) | Not a bulk edit: the identifier lives in one source file; `occurrence_map.yaml` belongs to #4562 and is untouched (C-004). |

**Gate result**: PASS, no violations to justify; Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/reconcile-run-scope-01M66YH3/
├── spec.md              # authored
├── research.md          # discovery + Phase 0 (D-1 … D-5)
├── plan.md              # this file
├── data-model.md        # Phase 1: RunScope, RunLegacyEdgeFixture value shapes
├── quickstart.md        # Phase 1: how a maintainer reproduces/verifies by hand
├── tasks/               # Phase 2 (/spec-kitty.tasks)
└── traces/              # tooling-friction.md, approach.md, design-decisions.md (coord branch)
```

### Source Code (repository root)

```
src/charter/activation/synthesizer/
├── reconcile.py             # RunScope + _is_legacy_applies + legacy_applies_edges + merge_project_overlay + _graph_delta
└── resynthesize_pipeline.py # passes run_scope=RunScope.TOPIC_SCOPED at its legacy-notice call

tests/charter/synthesizer/
├── test_synthesize_reconcile.py       # owning suite: new "#6728 — explicit run scope" section
├── test_styleguide_reach_only.py      # call sites gain run_scope
└── test_project_intent_directive.py   # call sites gain run_scope
tests/charter/test_project_registration.py  # merge_project_overlay callers (unchanged signature)
```

**Structure Decision**: keep everything in the existing `charter.activation.synthesizer` module.
The type belongs next to `SynthesizeMode` (the module's other run-mode enum) and the tests belong
in the suite that owns the reconciliation contract, so no new file needs a later fold-or-keep
verdict.

## Design

### The type

```python
class RunScope(enum.Enum):
    """How much of the project overlay a reconcile run re-emits (#6728).

    ``FULL``        — the run re-emits every artifact, so the dead project-intent
                      ``requires --> mission_type:*`` edge is stripped wherever it sits.
    ``TOPIC_SCOPED`` — the run re-emits only the targeted artifacts, so that edge is
                      stripped only where its owner was regenerated.
    """

    FULL = "full"
    TOPIC_SCOPED = "topic-scoped"

    def dead_edge_filter(self, regenerated_urns: Collection[str] | None) -> Collection[str] | None:
        """URN set the dead-edge check filters on, for this scope."""
        return regenerated_urns if self is RunScope.TOPIC_SCOPED else None
```

`_is_legacy_applies` then reads:

```python
def _is_legacy_applies(
    edge: DRGEdge,
    synthesized_urns: Collection[str],
    regenerated_urns: Collection[str] | None = None,
    *,
    run_scope: RunScope,
) -> bool:
    if _is_dead_mission_type_edge(edge, run_scope.dead_edge_filter(regenerated_urns)):
        return True
    return (
        edge.relation is Relation.APPLIES
        and edge.source.startswith(_REACH_ONLY_URN_PREFIXES)
        and edge.source in synthesized_urns
        and (regenerated_urns is None or edge.source in regenerated_urns)
    )
```

The `applies` branch is untouched on purpose: #6456's rule is scope-independent (FR-005), and a
test pins that the scope cannot leak into it.

### Call-site map (the six places, with before → after)

| Site | Before | After |
| --- | --- | --- |
| `merge_project_overlay` | `dead_edge_regenerated_urns=updated_urns if topic_scoped else None` | `run_scope=RunScope.TOPIC_SCOPED if topic_scoped else RunScope.FULL` (the one bool→enum conversion) |
| `legacy_applies_edges` body | forwards the sentinel | forwards `run_scope=` unchanged |
| `_graph_delta` → `legacy_applies_edges` | `dead_edge_regenerated_urns=None` | `run_scope=RunScope.FULL` |
| `_graph_delta` → `_is_legacy_applies` | `dead_edge_regenerated_urns=None` | `run_scope=RunScope.FULL` |
| `resynthesize_pipeline._validation_callback` | default (`...` → topic-scoped) | `run_scope=RunScope.TOPIC_SCOPED`, matching its `topic_scoped=True` merge |
| tests (7 calls) | default | `run_scope=RunScope.TOPIC_SCOPED` — the behaviour the `...` default had |

`EllipsisType` disappears from the import line and from both annotations.

### Red-first order

1. New test section in `tests/charter/synthesizer/test_synthesize_reconcile.py` that imports
   `RunScope`, inspects both signatures for an `Ellipsis`/`EllipsisType` parameter, and asserts the
   scope behaviour on one shared fixture. Run it: RED (`ImportError: cannot import name
   'RunScope'`), captured in the transcript.
2. Implementation commit (`reconcile.py` + `resynthesize_pipeline.py`).
3. Same tests: GREEN; the untouched `tests/charter/synthesizer/` suite green before and after.
4. A follow-up assertion that the two scopes and `merge_project_overlay`'s bool agree
   edge-for-edge on the same fixture, so the mapping cannot drift.

## Complexity Tracking

No Charter Check violations; this section stays empty by design.

## Implementation Concern Map

### IC-01 — The run-scope type and its call sites

- **Purpose**: name the scope (`RunScope`) and make it own the dead-edge filter derivation, so the
  sentinel and its body ternary are gone and every caller states which kind of run it is.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, C-001, C-002, C-003, C-005
- **Affected surfaces**: `src/charter/activation/synthesizer/reconcile.py` (`RunScope`, `__all__`,
  `_is_legacy_applies`, `legacy_applies_edges`, `merge_project_overlay`, `_graph_delta`),
  `src/charter/activation/synthesizer/resynthesize_pipeline.py` (one call site)
- **Sequencing/depends-on**: none
- **Risks**: the old default was topic-scoped — `resynthesize_pipeline` must be updated in the same
  commit or its legacy-strip notices change; the `applies` branch must not start consulting the
  scope.

### IC-02 — Tests that pin the two scopes and the no-sentinel invariant

- **Purpose**: make a silent change to the FULL/TOPIC_SCOPED difference, or the return of an
  `Ellipsis` default, fail a test; prove the two scopes agree with `merge_project_overlay`'s bool.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-005, NFR-001, SC-001, SC-002, SC-003
- **Affected surfaces**: `tests/charter/synthesizer/test_synthesize_reconcile.py` (new section),
  the three existing test modules' call sites
- **Sequencing/depends-on**: IC-01 (the tests target its API); the red commit lands first
- **Risks**: `[ratchet]` rows need the paired-fixture discipline — each scope test names its partner
  (the same fixture under the other scope), otherwise a "both keep it" bug passes both.

## Phase 0 — Outline & Research

No `NEEDS CLARIFICATION` remains: the discovery step (`research.md` D-1…D-5) settled the caller
census, the grounding, the enum-vs-bool choice, and the no-default decision. Phase 0 adds nothing
new; the open questions it carried (Q1 `__all__`, Q2 test location, Q3 red-first form) are answered
in Design above and in `data-model.md`.

## Phase 1 — Design & Contracts

- `data-model.md`: `RunScope` (enum value object), `regenerated_urns: frozenset[str] | None`, the
  per-scope decision table for both legacy-edge rules, and the invariants.
- `contracts/`: none — the mission defines no externally visible interface. `meta.json` gets
  `"contracts": "none"` with a rationale (see below).
- `quickstart.md`: how a maintainer reproduces the old sentinel behaviour and checks the new scope
  by hand in a REPL, without running CI.

**Contracts rationale for `meta.json`**: the change is internal to `src/charter` and reached from
`specify_cli` only through `charter.activation.api`, which this mission does not touch; no CLI flag,
exit code, JSON envelope or serialized key changes.

## Post-design Charter re-check

Still PASS. The design adds one enum and removes one parameter; it introduces no duplicate
authority (`RunScope` is the only place a scope's meaning is defined), and the only gate it
implicates (`test_no_dead_symbols`, because of the `__all__` edit) is in the targeted run list.
