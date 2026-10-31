# Implementation Plan: Chain gate classifies subscript assignment and name-keyed dict comprehensions correctly

**Branch**: `kitty/mission-chain-gate-subscript-name-pairing-01M66YGY` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/chain-gate-subscript-name-pairing-01M66YGY/spec.md`

## Summary

Refine Rule 2 of the chain single-authority class gate
(`tests/architectural/test_org_pack_chain_single_authority.py`) so it mirrors the rule the
gate's docstring already states: only a ROOTs-only collection over `<registry>.packs` is a
violation, and anything carrying `pack.name` is name-paired and legitimate. Two concrete
gaps are closed — an `ast.Assign` whose target is an `ast.Subscript` is a collector
(name-pairing judged from the subscript key), and an `enumerate(...)`-wrapped `.packs`
iteration is still a packs iteration. One false positive is closed — a `DictComp` whose
key is `<x>.name` is name-paired and exempt. Every new rule ships with a planted
violation and a planted non-violation, all measured against the pre-fix classifier.

## Technical Context

**Language/Version**: Python 3.11 (`ast` module only; no new dependency)
**Primary Dependencies**: pytest (architectural marker), stdlib `ast`
**Storage**: N/A — the gate scans source files in memory
**Testing**: `uv run pytest tests/architectural/test_org_pack_chain_single_authority.py`
(targeted gate file only; the mission does not sweep `tests/architectural/`)
**Target Platform**: repository CI and any contributor running the architectural tier
**Project Type**: single project (library + CLI under `src/`)
**Performance Goals**: the gate keeps its single tree walk and single parse per file
**Constraints**: one file changes; no production module is touched; the allowlist stays
empty; scan scope, offering-tier exclusion and primitive-call rule are unchanged
**Scale/Scope**: ~1320 in-scope modules scanned, one gate module edited, ~8 fixtures added

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The gate keeps `charter.activation.layer_roots.resolve_pack_chain` as the only chain authority; the classifier only decides what counts as hand assembly. No second authority, no allowlist. |
| Architectural alignment | The change stays inside the class-gate module; it refines Rule 2, the rule that already carries the ROOTs-vs-names boundary. |
| ATDD-first | Fixtures are planted and run red before the classifier changes (T1), then green (T2); each fixture is the acceptance contract for one requirement. |
| Standing Order #4 (bug-fix discipline) | Defect reproduced on `main@512567ee` through the gate's own entry point (`_scan_source`), not through a new helper. |
| Standing Order #5 (gate non-vacuity) | Floor, planted violation per rule, planted non-violation per rule and the owner-bypass control stay; new fixtures make the two halves of the fix independently testable. |
| Standing Order #2 / `change-apply-smallest-viable-diff` | One module changes, no new files beyond the mission artifacts; no campsite clean beyond the docstring that must match the new rule. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Only the implicated gate file plus a targeted regression run of the charter activation unit tier. |

No violations; the Complexity Tracking table stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/chain-gate-subscript-name-pairing-01M66YGY/
├── spec.md              # authored
├── plan.md              # this file
├── research.md          # Phase 0: reproduction, supersession check, idiom survey
├── tasks.md             # Phase 2 (/spec-kitty.tasks)
└── traces/              # mission tracer files (approach, design-decisions, tooling-friction)
```

### Source Code (repository root)

```
tests/architectural/
└── test_org_pack_chain_single_authority.py   # the class gate; the only production-touching edit
```

**Structure Decision**: single-project layout; the change is confined to the existing
architectural gate module named by the issue. No `src/` file changes, which is what keeps
the blast radius at one test module plus changelog.

## Phase 0 — Research (see `research.md`)

- Reproduce both misclassifications on `main@512567ee` through `_scan_source`.
- Confirm the issue was not superseded (`git log -S`, changelog, #6012 landing).
- Survey every place the classifier's helpers are used so the refinement does not change
  the primitive-call rule, the offering-tier exclusion or the census scope.
- Decide the name-pairing test for each idiom, including the asymmetry between a
  `DictComp` (key and value both candidates) and a loop (collected values plus subscript
  keys).

## Phase 1 — Design

### Classifier design

1. `_is_packs_iter` unwraps `enumerate(<registry>.packs)` (and a `Call` whose single
   argument is the packs attribute) so indexing does not hide the iteration.
2. `_collector_args(loop)` plus `_subscript_assignments(loop)` return what a loop's body
   collects: the argument lists of `append`/`add`/`extend` calls (as today) plus the value
   of every `ast.Assign` whose target is an `ast.Subscript`, each subscript pair carrying
   its key as extra pairing evidence.
3. A loop is a violation when some collected value is a bare `effective_root(...)` and no
   collected expression — `append`/`add`/`extend` argument or subscript key — carries a
   `*.name` attribute. Pairing stays loop-wide over the loop's collections, as the existing
   `paired-loop` fixture pins; what changes is which expressions count as collections and
   that a subscript key joins the evidence.
4. A `DictComp` is a violation when some element (`key` or `value`) is a bare
   `effective_root(...)` and neither the key nor the value carries `*.name`. A `DictComp`
   keyed by `<x>.name` is therefore exempt; a `DictComp` keyed by a bare
   `effective_root(...)` with a name value — `{p.effective_root(r): p.name ...}` — is still
   a violation, because the dict then *is* the roots-only shape in key position.

### Fixtures

| Fixture | Direction | Expected |
| --- | --- | --- |
| `for i, p in enumerate(...): roots[i] = p.effective_root(r)` | violation | `registry.packs iteration assembling roots` |
| `for i, p in enumerate(...): by_name[p.name] = p.effective_root(r)` | non-violation | no hits |
| `{p.name: p.effective_root(r) for p in ...packs}` | non-violation | no hits |
| `{p.effective_root(r): p.name for p in ...packs}` | violation | `registry.packs comprehension assembling roots` |

The two existing fixtures (`packs-loop`, `packs-comprehension`) and the existing
non-violations (`names-only`, `pair-comprehension`, `paired-loop`, `no-collection`) stay
untouched as regression pins for the behaviours that already worked.

## Complexity Tracking

*No charter violations; no entries.*

## Implementation Concern Map

### IC-01 — Classifier: subscript collectors and `enumerate` unwrapping

- **Purpose**: Make a preallocated-list loop over `enumerate(<registry>.packs)` a detected
  collector while keeping a name-keyed subscript assignment legitimate.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-005
- **Affected surfaces**: `tests/architectural/test_org_pack_chain_single_authority.py`
  (`_is_packs_iter`, `_collector_args`, `_subscript_assignments`, `_loop_collects_bare_roots`)
- **Sequencing/depends-on**: none
- **Risks**: over-reaching the pairing test (any `*.name` anywhere in the loop body) would
  excuse a genuinely roots-only loop that merely mentions a name; pairing must stay judged
  over the loop's collected values and subscript keys, never over the whole body.

### IC-02 — Classifier: name-keyed `DictComp` exemption

- **Purpose**: Stop flagging `{p.name: p.effective_root(r) ...}` as roots-only assembly,
  without excusing a `DictComp` that puts the root in key position.
- **Relevant requirements**: FR-004, FR-005
- **Affected surfaces**: same module (`_comprehension_collects_bare_roots`)
- **Sequencing/depends-on**: none; ships in the same module as IC-01
- **Risks**: exempting on "the `DictComp` mentions `*.name` anywhere" would swallow
  `{p.effective_root(r): p.name ...}`; the exemption must be driven by the key.

### IC-03 — Gate evidence: docstring, fixtures and non-vacuity

- **Purpose**: Keep the gate's stated rule and its demonstrated behaviour in step, and keep
  every new rule guarded by a positive and a negative fixture.
- **Relevant requirements**: FR-005, FR-006, NFR-001, NFR-002
- **Affected surfaces**: module docstring, `test_planted_violation_is_reported`,
  `test_non_violations_are_not_flagged`
- **Sequencing/depends-on**: IC-01, IC-02 (fixtures must be red before, green after)
- **Risks**: a fixture that passes on the pre-fix classifier proves nothing; T1 records the
  red run so the PR can cite it.
