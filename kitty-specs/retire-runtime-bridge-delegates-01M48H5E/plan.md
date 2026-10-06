# Implementation Plan: Retire the runtime_bridge compat-delegate layer

**Branch**: `issue-2561-retire-runtime-bridge-delegates` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/retire-runtime-bridge-delegates-01M48H5E/spec.md`

Branch contract: planning base and merge target are both `issue-2561-retire-runtime-bridge-delegates`
(topology `single_branch`, PR-bound to `main`). The work packages run in sequence in the
repository root checkout.

## Summary

Delete the 36 compat delegates in `src/runtime/next/runtime_bridge.py`, remove the seams'
`_rb.<delegated name>` back-edges, and repoint every test at the owning seam. Work goes one
seam at a time behind a static acceptance test that starts strict-xfail for each seam and
flips to passing as that seam is migrated. Adapter delegates are pinned by characterisation
tests before they are removed. `get_or_start_run` and `build_operational_context_for_claim`
stay as plain re-exports for callers outside the package.

## Engineering Alignment (decisions recorded as Decision Moments)

1. **Internal call style** (`plan.design.internal-call-style`): inside `src/runtime/next/` a
   seam-owned name is called module-qualified on its owner (`runtime_bridge_io._build_run_ref(...)`),
   including the bridge's own calls to the two public re-exports. One name, one patch point.
   A seam calling its own function calls it directly. A deferred import of the *owning seam*
   is allowed where an import cycle forces it (io ↔ composition); a lookup on the bridge is not.
2. **Not a bulk edit** (`plan.design.bulk-edit-classification`): each site needs call-path
   judgement. The static acceptance test is the guardrail.
3. **Red-first for a deletion** (`plan.design.acceptance-gate`): a permanent static gate,
   per seam, `xfail(strict=True)` until that seam is done; plus adapter characterisation tests.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none added or changed (stdlib `ast` for the static gate; pytest, mypy, ruff as already pinned)
**Storage**: N/A
**Testing**: pytest. Per WP: the seam's own test files plus every test file that references the seam's deleted names. Closing WP: the full runtime_bridge surface (every test file referencing `runtime_bridge`, plus `tests/runtime`, `tests/next`, `tests/specify_cli/next`; baseline 2738 passed / 4 skipped on `main` 7297d8c0), `make test-fast`, and the named architectural gates `test_no_dead_symbols`, `test_layer_rules`, `test_bridge_cores_import_boundary`, `test_runtime_emitter_seam`. Never the full suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: the Spec Kitty CLI (Linux, macOS, Windows)
**Project Type**: single project
**Performance Goals**: N/A (no runtime behaviour change)
**Constraints**: no behaviour change; mypy over `src/runtime/next/` stays at ≤ 21 pre-existing errors; complexity ≤ 15; ruff check + format clean on changed files
**Scale/Scope**: 7 source files in `src/runtime/next/`; about 45 test files (grounding prototype touched 40)

## Charter Check

| Rule | How the plan meets it |
|------|-----------------------|
| Single canonical authority | Removes the duplicate binding for every moved symbol; one owner, one patch point. |
| ATDD-first / red-first (C-011, SO#4) | WP01 lands the static acceptance gate (strict-xfail per seam) and the adapter characterisation tests before any deletion. |
| Architectural gate discipline (SO#5) | The new gate starts with an empty allowlist, has a concrete floor (the 36 names are pinned by name) and a self-mutation test (a synthetic module with a delegate makes it fail). |
| Campsite cleaning (SO#2) | Stale seam docstrings describing the compat mechanism are rewritten in the WP that touches each seam. |
| Mission tracer files (SO#3) | Seeded at planning (`tracer/`), appended during implement. |
| Mission hygiene (SO#8) | #2561 and #2633 claimed and assigned; issue-matrix rows; reviewer ≠ implementer. |
| No full heavy suites | Targeted surface + named gates only. |
| Locality of change | Source edits stay in `src/runtime/next/`; out-of-package docstring deferred. |

No violations to justify.

## Project Structure

### Documentation (this mission)

```
kitty-specs/retire-runtime-bridge-delegates-01M48H5E/
├── spec.md
├── plan.md
├── research.md          # delegate inventory, back-edge inventory, hazards
├── data-model.md        # symbol ownership map (name → owning seam)
├── quickstart.md        # how to verify the mission locally
├── contracts/
│   └── bridge-surface.md  # what the bridge exports after the mission
├── tracer/              # tooling-friction, approach, design-decisions
└── tasks.md             # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/runtime/next/
├── runtime_bridge.py                # delegates deleted; calls owner-qualified; 2 re-exports kept
├── runtime_bridge_identity.py       # back-edges removed (3 names)
├── runtime_bridge_cores.py          # owns the tasks.md parsers (2 names)
├── runtime_bridge_engine.py         # back-edges removed
├── runtime_bridge_retrospective.py  # back-edges removed (9 names)
├── runtime_bridge_composition.py    # back-edges removed (8 names)
└── runtime_bridge_io.py             # back-edges removed (13 names)

tests/runtime/test_bridge_no_compat_delegates.py   # NEW static acceptance gate
tests/runtime/, tests/next/, tests/specify_cli/next/, tests/integration/…  # repointed patches
```

**Structure Decision**: no new modules. One new test file; every other change edits existing files.

## Implementation Concern Map

### IC-01 — Acceptance gate and adapter characterisation

- **Purpose**: make the end state checkable before changing code, and pin the three adapter behaviours.
- **Relevant requirements**: FR-001, FR-003, FR-005, FR-008; NFR-001
- **Affected surfaces**: `tests/runtime/test_bridge_no_compat_delegates.py` (new); characterisation tests next to the bridge's existing load-runs / tasks.md / run-ref tests
- **Sequencing/depends-on**: none
- **Risks**: a vacuous gate. Mitigated by pinning the 36 names explicitly and a self-mutation test.

### IC-02 — Small seams: identity, cores, engine

- **Purpose**: retire 6 delegates (identity 3, cores 2, engine 1) and their back-edges.
- **Relevant requirements**: FR-001, FR-003, FR-006, FR-008 (`_parse_requirement_refs_from_tasks_md` grammar), FR-010
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_identity.py`, `runtime_bridge_cores.py`, `runtime_bridge_engine.py`; tests referencing those names
- **Sequencing/depends-on**: IC-01
- **Risks**: `_parse_requirement_refs_from_tasks_md` is an adapter (injects `grammar=`).

### IC-03 — Retrospective seam

- **Purpose**: retire 9 delegates (including the `_BufferingRuntimeEmitter` class alias) and the 5+ `_classify_and_emit_failure` back-edges.
- **Relevant requirements**: FR-001, FR-003, FR-006, FR-009, FR-010
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_retrospective.py`, `runtime_bridge_engine.py` (calls retrospective), `tests/integration/retrospective/*`, `tests/runtime/test_bridge_retrospective.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `test_runtime_emitter_seam` pins the emitter's home; keep it green.

### IC-04 — Composition seam

- **Purpose**: retire 8 delegates and the composition-side back-edges.
- **Relevant requirements**: FR-001, FR-003, FR-006, FR-007, FR-010
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_composition.py`, composition tests in `tests/runtime`, `tests/specify_cli/next`, `tests/next`
- **Sequencing/depends-on**: IC-01
- **Risks**: `_advance_run_state_after_composition` (engine-owned) is patched in 8 files; its call path runs through composition.

### IC-05 — IO seam and the public re-exports

- **Purpose**: retire 13 delegates, turn `get_or_start_run` / `build_operational_context_for_claim` into plain re-exports, remove io back-edges.
- **Relevant requirements**: FR-001, FR-003, FR-005, FR-006, FR-007, FR-008 (`_load_feature_runs`, `_build_run_ref`), FR-010
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_io.py`, `runtime_bridge_identity.py` (io now imports it at top level), io tests, CLI-facing tests patching the re-exports
- **Sequencing/depends-on**: IC-01; after IC-04 (io ↔ composition cycle edges)
- **Risks**: GROUNDING hazard 1 (9 tests patch the kept re-export while driving the bridge's internal path) and hazard 2 (adapters).

### IC-06 — Close-out

- **Purpose**: fix `_check_cli_guards`'s docstring, drop the last xfail marks, rewrite remaining stale docstrings, run the full targeted surface and named gates.
- **Relevant requirements**: FR-002, FR-004, FR-010; NFR-001..NFR-005
- **Affected surfaces**: `runtime_bridge.py`, seam module docstrings, the acceptance gate
- **Sequencing/depends-on**: IC-02..IC-05
- **Risks**: residual false-green patches; resolved by a final grep of bridge-qualified patch targets against the bridge's real attribute set.
