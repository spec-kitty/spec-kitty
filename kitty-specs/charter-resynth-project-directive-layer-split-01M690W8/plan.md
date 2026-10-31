# Implementation Plan: charter resynthesize project-directive layer split

**Branch**: `issue-6768-charter-resynth-project-directive` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-resynth-project-directive-layer-split-01M690W8/spec.md`
**Issue**: [#6768](https://github.com/spec-kitty/spec-kitty) (P0)

## Summary

`charter resynthesize` (and `charter synthesize --dry-run`) hand one snapshot to two
consumers with different layer semantics: the FR-020 / EC-6 additive-only check needs the
**built-in** layer, while EC-2 source-URN validation and the pre-write validation gate need a
**reference universe** that includes the project's own nodes. Because
`_build_synthesis_request` fills `SynthesisRequest.drg_snapshot` from the config-activated
directive list (built-in + org + project), an activated project directive is classified as
built-in and collides with itself when it is the resynthesis target.

The plan separates the two inputs where the request is authored, and nowhere else:

- the additive-only check runs against a **new `built_in_drg_snapshot`** built from the
  shipped DRG (`charter.offering.drg.loader.load_built_in_graph()`);
- `drg_snapshot` keeps its current content and role (the reference universe), so EC-2,
  the validation gate and every fixture key are unchanged;
- when a request omits the new field, every consumer falls back to `drg_snapshot`, so
  existing callers and tests are untouched.

No `PROJECT_` id-prefix heuristic (the issue's session-local workaround) and no change to
the invariant, its exception type or its `colliding_urn` contract.

## Technical Context

**Language/Version**: Python 3.11 (repo `.python-version`)
**Primary Dependencies**: pydantic v2, typer, ruamel.yaml — no new dependency
**Storage**: YAML/JSON on disk (`.kittify/charter/…`); read-only for this change
**Testing**: pytest; the red-first regression drives the real `charter activate` and
`charter resynthesize` commands through the existing fixture
`tests/charter/synthesizer/test_resynthesis_after_activation_6510.py`
**Target Platform**: CLI (Linux/macOS), installed package
**Project Type**: single Python package (`src/charter`, `src/specify_cli`)
**Performance Goals**: one memoized `load_built_in_graph()` per request; the pre-write gate
stays inside its documented 5 s fail-closed budget
**Constraints**: `normalize_request_for_hash` must not change (fixture keys); no gate
weakening; layered imports respected (`charter.offering.drg` ← `charter.activation`)
**Scale/Scope**: ~6 source files, 1 new test module, 1 changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority**: the built-in layer is read through the existing
  `load_built_in_graph()` seam; the classification is authored once in
  `_build_synthesis_request`. ✅
- **Layering**: `src/charter/**` must not import `specify_cli`; the new field and helper live
  in `charter.activation.synthesizer.request`, the request assembly in the CLI. ✅
  (`tests/architectural/test_layer_rules.py`)
- **change-apply-smallest-viable-diff / Locality of Change**: one new optional dataclass
  field, one helper, one request-builder edit, four consumer call sites. ✅
- **ATDD-First Discipline / test-first-bug-fixing**: the red test goes in before the fix,
  through the pre-existing CLI entry points, and the fix removes the red. ✅
- **DIRECTIVE_041 (tests guard real behaviour)**: the new tests guard the reported refusal
  and the additive-only invariant, not incidental helper shapes. ✅
- **NO_FULL_HEAVY_SUITES_IN_MISSION**: run the charter suites only; CI owns the rest. ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-resynth-project-directive-layer-split-01M690W8/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery + plan decisions)
├── data-model.md        # Phase 1 output (request field, layer roles)
├── quickstart.md        # Phase 1 output (how to verify by hand)
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — not created here)
```

No `contracts/`: the mission defines no external interface (internal request envelope and
CLI behaviour that already exist). `meta.json` records `"contracts": "none"` with its
rationale.

### Source Code (repository root)

```
src/charter/activation/synthesizer/
├── request.py                 # + built_in_drg_snapshot field, built_in_snapshot() helper
├── orchestrator.py            # additive check reads the built-in layer
├── resynthesize_pipeline.py   # additive check + bounded request propagation
└── synthesize_pipeline.py     # per-target request propagation

src/specify_cli/cli/commands/charter/
├── _synthesis.py              # _build_synthesis_request authors both layers;
│                              # dry-run callback and reconciliation preview split them
└── (no change to resynthesize.py command body)

tests/charter/synthesizer/
└── test_project_directive_layer_split_6768.py   # red-first regression + positive control

docs/changelog/CHANGELOG.md    # [Unreleased] entry
```

## Implementation Concern Map

| IC | Concern | Where |
|----|---------|-------|
| IC-01 | The request carries an explicit built-in layer, absent means "unchanged" | `request.py` |
| IC-02 | The request builder authors the built-in layer from the shipped DRG | `_synthesis.py` |
| IC-03 | Every additive-only consumer reads the built-in layer; every reference consumer keeps the universe | `orchestrator.py`, `resynthesize_pipeline.py`, `_synthesis.py` |
| IC-04 | Red-first proof through the real CLI, plus the built-in positive control | new test module |
| IC-05 | User-facing changelog entry | `docs/changelog/CHANGELOG.md` |

## Phase 0 — Outline & Research

Recorded in [research.md](./research.md): reproduction evidence, the two-job snapshot
analysis, the new-field/None-fallback decision, the fixture-hash constraint, and the three
open questions deliberately left out of scope.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md): the two layers, the request fields, invariants and the
  fallback rule.
- [quickstart.md](./quickstart.md): reproduce the refusal on `main` and confirm the fix by hand.
- Contracts: none (see above).

## Key Rules

- Fix the classification at the request builder; do not patch `emit_project_layer`'s
  invariant, its message, or its exception.
- Never key on the `PROJECT_` id prefix.
- Add tests for the branches the change introduces (diff-cover ≥ 90 % on changed lines):
  the `None` fallback and the `DRGLoadError` fallback both need a case.
- Keep the changelog entry under 1,200 characters, impact-first, with `(#6768)`.
