# Implementation Plan: Custom-type action-sequence + analysis-currency generalization

**Branch**: `kitty/mission-custom-type-sequence-analysis-currency-01M535FV` | **Date**: 2026-10-17 | **Spec**: `./spec.md`
**Input**: Mission specification from `kitty-specs/custom-type-sequence-analysis-currency-01M535FV/spec.md`

## Summary

Two coupled gaps block an activated org-pack-shape custom mission type (e.g. `cave-dev`) from
running the canonical loop at software-dev rigour:

- **Problem A — empty action sequence.** spec-kitty has two disjoint step authorities. Charter's
  `action_sequence` projection (`project_action_sequence` ← `MissionStepRepository` ←
  `_inject_projected_fields`) reads ONLY the dir-per-step shape
  (`mission-steps/<type>/<step>/step.yaml`). Org packs ship ONLY the runtime-DAG shape
  (`missions/<type>/mission-runtime.yaml`), which only `runtime.next` reads. So an activated
  org-pack type projects an empty sequence and fails `MissionTypeEmptyActionSequenceError`.
- **Problem B — analysis-currency gate is software-dev-literal** at three runtime sites, so an
  `analyze`-declaring custom type never gets the stale-analysis → re-`analyze` gate.

Approach: teach charter's single projection producer (`_inject_projected_fields`) a **charter-local
minimal reader** of the runtime-DAG `steps:` list as a fallback when the dir-per-step projection is
empty (operator-approved layering option; charter cannot import `runtime`). Generalize the three
analysis-currency sites to key on **the resolved runtime DAG declaring an `analyze` step** — NOT
`action_sequence` membership (software-dev's sequence has no `analyze`). Reuse `ResolvedMissionType`
throughout; no competing resolver. First slice of #4983; accept/merge/dossier/retrospective are out
of scope.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ruamel.yaml (thread-local `YAML(typ="safe")` already used in `charter.offering.missions`); no new deps.
**Storage**: filesystem (pack roots, frozen mission template `mission_template_frozen.yaml`)
**Testing**: pytest — `tests/charter_offering/missions/`, `tests/runtime/` (incl. `test_analyze_step.py`, `test_runtime_seam.py`, `test_next_board_authority.py`)
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single
**Performance Goals**: no hot-path regression; the runtime-shape reader fires only on the empty-projection fallback (custom types), never for built-ins.
**Constraints**: enforced layer chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` — charter MUST NOT import `runtime`; reader is a charter-local plain-YAML parse of id+order only. Byte-identical behaviour for all 4 built-in families. ruff/mypy clean; complexity ≤ 15.
**Scale/Scope**: ~4 source files, 1 new charter helper, ~4 test files. 4 WPs.

## Charter Check

- **Single canonical authority**: the projection stays the single producer; the runtime-shape reader is a *fallback input* to it, not a second resolver. Duplicate parse of the `mission-runtime.yaml` step-list shape in charter is an accepted slice-1 tension; shared extraction into a lower layer is the noted eventual home (Refs #2535).
- **ATDD-first / red-first**: each WP ships one failing-first test witnessing the behaviour.
- **Tiered rigour / test economy**: `DIRECTIVE_041` — one focused test per fold; no shape-pins, no inert self-compares. NFR-001 golden-parity tests are the ratchet.
- **No packaging/gate changes** (C-003).

## Project Structure

```
kitty-specs/custom-type-sequence-analysis-currency-01M535FV/
├── spec.md
├── plan.md
└── tasks/

src/charter/offering/missions/
├── mission_type_repository.py      # _inject_projected_fields fallback (WP01)
└── <runtime-shape step reader>     # new charter-local helper (WP01)

src/runtime/next/
├── runtime_bridge_io.py            # site 1: line 1543 (WP02)
├── runtime_bridge_cores.py         # new mission_declares_analyze_step(run_dir) helper (WP02)
├── runtime_bridge.py               # site 2: line 652 decide path (WP03)
└── runtime_bridge_query.py         # site 3: line 144 preview path (WP04)
```

## Complexity Tracking

| Deviation | Need | Why simpler insufficient |
|-----------|------|--------------------------|
| Charter-local reader of `mission-runtime.yaml` (duplicate of runtime's parse) | Charter needs DAG step order but the layer chain forbids importing `runtime` | A shared lower-layer extraction is cleaner but widens blast radius beyond slice 1; operator approved the charter-local reader for this slice, shared extraction deferred (Refs #2535) |

## Implementation Concern Map

### IC-01 — Custom-type action_sequence resolves from the runtime-DAG shape (Problem A)

- **Purpose**: An activated org-pack-shape custom type resolves its full ordered `action_sequence` from its own `missions/<type>/mission-runtime.yaml` steps, so it is usable through the canonical loop.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-001, SC-001.
- **Affected surfaces**: `src/charter/offering/missions/mission_type_repository.py` (`_inject_projected_fields` :274-284), new charter-local runtime-shape step reader; `tests/charter_offering/missions/`.
- **Sequencing/depends-on**: none.
- **Risks**: must preserve the empty/malformed → `None` → `MissionTypeEmptyActionSequenceError` fail-closed path; must not fire for built-ins (their dir-per-step projection is non-empty). Charter must not import `runtime` — parse plain YAML (id + order) directly.

### IC-02 — Analysis-currency gate generalized to any analyze-declaring family (Problem B)

- **Purpose**: For any mission whose resolved runtime DAG declares an `analyze` step, recompute analysis currency at `analyze` and re-issue `analyze` before `implement` on a stale/missing report — on both the decide and preview paths.
- **Relevant requirements**: FR-003, FR-004, FR-005, NFR-001, C-002, SC-002, SC-003.
- **Affected surfaces**: `runtime_bridge_io.py:1543` (drop family clause → `step_id == ANALYZE_STEP_ID`), `runtime_bridge_cores.py` (new `mission_declares_analyze_step(run_dir)` reading the frozen template DAG step ids), `runtime_bridge.py:652` + `runtime_bridge_query.py:144` (predicate via the helper; thread `run_ref.run_dir` into the query helper).
- **Sequencing/depends-on**: IC-01 (so a custom analyze-declaring family is resolvable/activatable end to end for the tests).
- **Risks**: must key on the DAG step SET, never `action_sequence` membership (software-dev's sequence lacks `analyze`); byte-identical for software-dev/research/documentation/plan (verified: only software-dev declares `analyze`). Do not weaken the frozen-template / golden-parity assertions.
