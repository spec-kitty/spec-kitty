# Implementation Plan: Consolidation god-module decomposition

**Branch**: `issue-2026-consolidation-decomposition` (planning base and merge target; PR targets `main`) | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/consolidation-god-module-decomposition-01M42Z57/spec.md`
**Grounding**: [research/code-grounding.md](research/code-grounding.md) · **Decisions**: [research.md](research.md)

## Summary

Tidy-first, behaviour-preserving relocation (epic #2026 re-scope, closes #2600 and #3457):

1. Move the mission_number bake cluster out of `consolidation/ordering.py` into `consolidation/mission_number/bake.py`; `mission_number.py` becomes the package `consolidation/mission_number/` whose `__init__.py` is the unchanged stdlib-only predicate.
2. Introduce `ConsolidateOptions` (frozen dataclass, real defaults). The Typer `consolidate()` keeps its 19 options, builds the object and calls `run_consolidate(options)`; direct-call tests build the object.
3. Split `consolidation/executor.py` (4,603 LOC) verbatim into phase modules. `executor.py` keeps the locked driver with its inline rollback door, `_report_rollback`, operator-attestation recording and the locked entry (lock acquire/release).

No refusal text, exit code, state file, ref operation or ordering changes (C-001). #5613 is not fixed here (C-002). No size or ratchet gate is added (C-003).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (unchanged; no new dependency, so no supply-chain decision — DIRECTIVE_051 not engaged)
**Storage**: N/A (no state-file shape change)
**Testing**: pytest. Targeted: `tests/consolidation/`, `tests/specify_cli/consolidation/`, `tests/terminus/`, `tests/lanes/`, `tests/orchestrator_api/`, `make test-fast`, plus the specific architectural gate files listed in code-grounding §3. No full `tests/architectural/` or `make test-full` run (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: CLI (Linux/macOS/Windows), unchanged
**Project Type**: single project (`src/specify_cli/...`)
**Performance Goals**: none new; import-time cost unchanged in practice (same modules imported by the same entry points)
**Constraints**: byte-identical moved bodies; no gate loosened; ruff/format/mypy clean on changed files; C901 ≤ 15
**Scale/Scope**: ~5,500 LOC moved across 13 new modules; ~85 test files re-pointed (imports, ~493 executor patches, 41 ordering patches); ~15 gate/ledger entries re-pointed or widened

## Charter Check

| Charter rule | How this plan satisfies it |
|---|---|
| Standing Order 2 / DIRECTIVE_025 tidy-first | The whole mission is the distinct, behaviour-preserving step that precedes the #5613 functional change. Procedure `refactoring.procedure.yaml`; tactics extract-class-by-responsibility-split (executor), move-method (bake cluster), introduce-parameter-object / change-function-declaration (`consolidate`). |
| Standing Order 5 gate discipline | No new gate. Fixed-scope gates that would go vacuous are widened to the receiving modules (tightening), never narrowed. |
| Standing Order 6 canonical sources | Mission run through the canonical CLI; canonical templates. |
| Standing Order 3 tracer files | `traces/` seeded below; appended during implementation. |
| Standing Order 8 mission hygiene | Implementer and reviewer are distinct passes (review delegated to an independent reviewer agent); issue-matrix rows for #2600, #3457, #2026. |
| ATDD-first (C-011) | Each WP lands a failing-first structural test before its move (see WP list). For a pure move the "user-observable behaviour" is the structure itself; behaviour is pinned by the existing suites staying green. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Only targeted suites and named gate files. |
| "Issue branch first" (`issue-<n>-<slug>`) | Branch is `issue-2026-consolidation-decomposition`, not the brief's `refactor/consolidation-decomposition`: the charter wins, recorded in the PR. |
| Pre-existing failure reporting | Baseline taken on `origin/main` before any change (see research.md). |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/consolidation-god-module-decomposition-01M42Z57/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md
├── occurrence_map.yaml          # bulk-edit classification (module moves)
├── research/code-grounding.md   # read-only grounding run
├── traces/                      # tooling-friction / approach / design-decisions
└── tasks.md · tasks/WP0*.md     # /spec-kitty.tasks output
```

No `contracts/`: no API, CLI flag, JSON payload or state-file contract changes (C-001, C-006).

### Source Code

Before → after (`src/specify_cli/consolidation/`):

```
executor.py        4,603  →  executor.py          driver + rollback door + _report_rollback
                                                  + attestations + locked entry (~600)
                              run_state.py         _MergeRunState, _CoordCheckpoint, post-tip recorder,
                                                  snapshot capture, shared messages, topology probes
                              coord_strand.py      strand mark / heal / restore primitive
                              phase_claim.py       pre-mutation gates, resume anchors, claim, snapshot begin
                              phase_advance.py     lane advance, surface, bake + pre-target done,
                                                  mission->target, gate-artifact guard
                              phase_bookkeeping.py target mission_number, capture/baseline, done + projection,
                                                  birth cutover, porcelain invariant, commit + assert
                              phase_gate.py        reconciliation gate + squash projection proof
                              phase_teardown.py    flatten, branch delete CAS, late landing, coord triple,
                                                  lane worktree/branch cleanup
                              phase_finalize.py    stale scan, push, finalize, stale render
                              entry_preflight.py   unlocked pre-phase: status dir, lanes.json, protected
                                                  target, refuse-before-destroy preflight
                              resume_recovery.py   lag classifier, refusal advice, behind-own-HEAD reset,
                                                  preflight-with-recovery wrapper
ordering.py          911  →  ordering.py          merge ordering only (~135)
mission_number.py     30  →  mission_number/__init__.py   stdlib-only predicate (unchanged)
                              mission_number/bake.py       assign / bake / write / verify cluster
cli/commands/consolidate.py  ConsolidateOptions + run_consolidate(options); Typer consolidate() builds it
```

Import DAG (no cycles): `run_state` ← `coord_strand` ← {`phase_advance`, `phase_bookkeeping`}; `run_state` ← {`phase_claim`, `phase_gate`, `phase_teardown`, `phase_finalize`, `entry_preflight`}; `phase_advance` ← `phase_bookkeeping`; `entry_preflight` ← `resume_recovery`; everything ← `executor`. (Pre-PR review fold: `_created_lane_worktree` and `_resume_reconciliation_already_passed` moved to `run_state`, so `phase_claim` no longer imports `phase_gate` and `phase_teardown` / `entry_preflight` no longer import `phase_advance`.)

**Structure Decision**: single project; new modules sit beside the existing seams in `consolidation/`.

## Key design decisions (full reasoning in research.md)

- **D1 mission_number home** — package `mission_number/` (leaf `__init__` + `bake.py`) instead of moving ~775 LOC into the stdlib-only leaf that `drivers.py` imports from git's merge-driver subprocess. Honours #2600's target and the leaf contract (a file-level contract: the parent `consolidation/__init__` still loads `bake.py`, as it loaded `ordering.py` before).
- **D2 executor cut** — by phase, with the driver, the door `try`, its inline phase calls and `_report_rollback` staying in `executor.py`, so `test_single_rollback_authority.py` and the phase-order pins keep reading the same function in the same file.
- **D3 patch re-pointing** — computed from the AST: for each `executor.<name>` patch, the set of new modules whose code loads `<name>` as a global. Patching each of them reproduces the old interception set exactly. No alias is kept only for patch strings.
- **D4 parameter object** — `ConsolidateOptions` in `cli/commands/consolidate.py` (the CLI layer owns CLI option semantics); `run_consolidate(options)` holds the old body verbatim, with `options.<field>` reads bound to the old local names at the top so the body text stays identical.
- **D5 vacuous-risk gates** — widen `test_executor_builds_no_revert_argv`, `_STATUS_BEARING_MODULES`, `CHURN_SURFACE_MODULES`, `_WRITE_DIR_CONSUMER_MODULES`, `_WP09_OWNED_FILES`, `_SEAM_IMPORT_TARGETS`, `_MERGE_CLI_CONSOLE_IMPORTERS` to the receiving modules.

## Risks

| Risk | Mitigation |
|---|---|
| A patch silently stops intercepting | AST audit (D3) over every test file; run the full targeted suites |
| Textual conflict with PR #5633 (#5613 fix) | Documented mapping hunk → new module (code-grounding §5); resolution is mechanical; operator chooses merge order |
| Import cycle | DAG above; import smoke test via the suites |
| mypy strictness on code leaving the `ordering` quarantine | fix types without changing behaviour, or keep the bake module under the existing quarantine entry re-pointed (decided in WP01 after running mypy) |

## Implementation Concern Map

- **IC-A mission_number cohesion (#2600):** relocate the bake cluster, convert the leaf to a package, re-point callers, re-point ordering-keyed gates (`_load_meta_census.py`, `test_destructive_op_routing.py`, `untrusted_path_audit/inventory.md`, `dead_symbol_allowlist.yaml`, `test_mission_resolver_walker_gate.py`, `test_commit_recipes.py`, `test_merge_compat_surface.py`, `test_ordering_bake_seam.py`), mypy quarantine entry.
- **IC-B consolidate parameter object (#3457):** `ConsolidateOptions`, `run_consolidate`, 8 direct-call sites.
- **IC-C executor phase split (#2026):** verbatim split, cross-module imports, test import/patch re-pointing, path/qualname gate re-pointing, vacuous-risk gate widening, module docstrings, `consolidate.py` module-map comment.
