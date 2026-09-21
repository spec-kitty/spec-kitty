# Implementation Plan: CI down-route of prose-only .py diffs

**Branch**: `feat/ci-prose-only-downroute` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/ci-prose-only-downroute-01M31T5S/spec.md`

## Summary

Add content-based "prose-only" classification to CI path routing so a PR whose
entire Python diff is comments/docstrings is down-routed off the runtime
module-test matrix and the heavy architectural battery, while positively
selecting the docs/help-drift and doctest lanes. The classifier is a **new pure
module** (`scripts/ci/prose_only.py`) — `scripts/ci/gate_selection.py` stays a
pure function of a path list (#4842 F1/F2, #2476 single-authority invariant).
Blob access and path-list reduction happen in the workflow step that already
computes the base→head diff (`ci-modules.yml` changed-files, F2). The classifier
treats `# type:`/`# noqa`/`# pragma` deltas as code (F3) and the down-route
positively enables the docs lane rather than merely subtracting the code path
(F4). Fail-closed on every uncertainty.

## Technical Context

**Language/Version**: Python 3.11+ (CI helper scripts under `scripts/ci/`)
**Primary Dependencies**: Python standard library only — `ast`, `tokenize`, `io`. No new third-party dependency; no `yaml`/`fnmatch` in the new module (NFR-001). `git` (already invoked by the workflow step) supplies base/head blobs.
**Storage**: N/A (pure in-memory string→bool classification; no persistent state)
**Testing**: pytest — `tests/ci/test_prose_only.py` (new, unit) + `tests/ci/test_ci_module_wiring.py` (extend) + existing `tests/architectural/test_gate_selection_authority.py` / `test_local_gate_parity.py` / `test_ci_integrity_oracle_nonvacuous.py` (must stay green — path purity guard)
**Target Platform**: GitHub Actions runners (Linux) + local `make` parity
**Project Type**: single (CI tooling in `scripts/ci/`, workflows in `.github/workflows/`)
**Performance Goals**: negligible — one `ast.parse` per changed `.py` per side; bounded by PR file count, dwarfed by the shard compute it saves
**Constraints**: no product-code change (NFR-004); fail-closed on any uncertainty (FR-006); zero new lint/type suppressions (NFR-003); AST compare via `ast.dump(include_attributes=False)` + `type_comments=True` (C-002)
**Scale/Scope**: ~1 new source module (~80–120 LoC), ~1 workflow-step edit, ~1 new test file (~15–20 cases), ~2 workflow-lane wiring edits. No `src/**` touch.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter present at `.kittify/charter/charter.md`. Relevant gates:

- **DIRECTIVE_001 (Architectural Integrity)** — the plan explicitly keeps
  `gate_selection.py` pure and introduces the new boundary as a separate module;
  no shared mutable state, no new circular dependency. **PASS** (this is the
  central design decision, F1).
- **DIRECTIVE_024 (Locality of Change)** — change confined to `scripts/ci/**`,
  `.github/workflows/**`, and their tests. No opportunistic refactor of
  `gate_selection.py`. **PASS** (NFR-004).
- **DIRECTIVE_030 (Test/Typecheck Gate)** — every new branch/helper gets a
  focused test in the same WP; ruff+mypy clean. **PASS by construction**.
- **DIRECTIVE_041 (Tests as scaffold)** — the fail-closed tests assert an
  observable contract (the selected-lane set / the boolean verdict), not an
  implementation detail; red-first for the `# type:` regression. **PASS**.
- **#2476 single routing authority / C-001** — the new module introduces no
  second path→group map; routing still flows through the parsed router. **PASS**.
- **Terminology Canon / C-003** — no `feature*` identifiers introduced. **PASS**.
- **Supply-chain (051)** — **N/A**: no dependency added/upgraded/removed
  (stdlib only). Recorded as examined-and-not-applicable, not skipped.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-prose-only-downroute-01M31T5S/
├── plan.md              # This file
├── spec.md              # Committed
├── research.md          # Phase 0 output (this command)
├── data-model.md        # Phase 1 output (this command)
├── quickstart.md        # Phase 1 output (this command)
├── contracts/
│   └── prose-only-classifier.md   # the classifier + aggregate contract
├── traces/              # tracer files (seeded)
└── checklists/requirements.md
```

### Source Code (repository root)

```
scripts/ci/
├── prose_only.py            # NEW — pure classifier (FR-001, FR-002, FR-006)
└── gate_selection.py        # UNCHANGED — stays path-pure (FR-007)

.github/workflows/
├── ci-modules.yml           # EDIT (WP02) — changed-files step reduces prose-only .py before select_modules (FR-003, FR-008)
└── ci-router.yml            # EDIT (WP02) — SEPARATE prose-scan job (F2) gates arch battery/shards off, docs lane on (FR-004/005/008)

scripts/ci/
└── aggregate_source.py      # EDIT (WP03) — exclude prose-only .py from critical.diff.patch so diff-cover can't false-red (FR-009, squad F1)

tests/ci/
├── test_prose_only.py       # NEW — classifier unit tests (all FR-001..006 cases)
└── test_ci_module_wiring.py # EXTEND — aggregate down-route + fail-closed wiring

tests/architectural/
├── test_gate_selection_authority.py   # UNCHANGED, must stay green (path purity)
├── test_local_gate_parity.py          # UNCHANGED, must stay green (singularity)
└── test_ci_integrity_oracle_nonvacuous.py  # UNCHANGED, must stay green
```

**Structure Decision**: Single-project CI tooling. The one structural decision —
new module vs. editing `gate_selection.py` — is resolved in favor of a new pure
module per the #4842 F1/F2 review, preserving the reuse contract that the WP17
oracle and WP18 local parity depend on.

## Complexity Tracking

*No Constitution Check violations — section intentionally empty.*

## Parallel Work Analysis

Single small mission; sequential is correct — the wiring depends on the
classifier existing. Not decomposed into parallel lanes. Expected shape at
`/spec-kitty.tasks`: a small number of dependency-ordered WPs, roughly:

### Dependency Graph (updated post-adversarial-squad, research R10)

```
WP01: pure classifier (prose_only.py) + unit tests  (foundation)
        │
        ├──────────────► WP02: ci-modules + ci-router wiring (prose-scan job, F2)
        │                       + wiring/golden tests, path-purity guards green
        │
        └──────────────► WP03: ci-aggregate coverage honesty (exclude prose-only
                                from critical.diff.patch, F1) + coverage test
WP02 ∥ WP03  (disjoint files → parallel lanes)
```

### Work Distribution

- **Sequential work**: WP-A (classifier) must land before WP-B (wiring) — the
  wiring imports and calls the classifier.
- **Parallel streams**: none warranted at this size.
- **Agent assignments**: python-pedro for both WPs (Python + CI); reviewer-renata
  reviews. The `# type:` fail-closed test is the load-bearing red-first case.

### Coordination Points

- **Integration tests**: `tests/ci/test_ci_module_wiring.py` exercises the
  reduced-path-list → `select_modules` path end to end; the golden test pins the
  exact down-routed lane set (SC-001).
