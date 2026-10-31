# Implementation Plan: grep_absence must judge tracked text and record named evidence

**Branch**: `issue-6761-grep-absence-binary-evidence` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/grep-absence-binary-evidence-01M66F4Y/spec.md`

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

`src/specify_cli/acceptance/matrix.py::_check_grep_absence` runs
`grep -r --exclude=acceptance-matrix.json --exclude-dir=.git -- <pattern> <roots>`.
GNU grep ≥ 3.5, on matching content inside a binary file (a stale `.pyc` under
`__pycache__/`), prints `binary file matches` on **stderr** and exits 0 with
**empty stdout**. The matcher reads only stdout, so it records `still_present`
with evidence `grep found matches: ` (nothing after it), blocking `spec-kitty
accept` after the offending text is gone from every tracked file, with no way to
see why (#6761).

Fix in place, minimal diff: (1) add `-I` to the grep invocation so binary
files are skipped and the invariant judges text (the tracked surface);
(2) when grep exits 0, fall back to stderr when stdout is empty, so the
recorded evidence names what grep saw instead of being blank. Red-first: a
regression test builds the stale-`.pyc` fixture and drives the real
`acceptance-verdict --negative-invariant --execute` entry point; it fails on
current `main` and passes after the fix.

## Technical Context

**Language/Version**: Python 3.11+ (repo `pyproject.toml`), system GNU grep ≥ 3.5 in the target environment (CI Linux images).
**Primary Dependencies**: `typer` CLI shell; stdlib `subprocess` for the grep call. No new dependencies.
**Storage**: `acceptance-matrix.json` under the mission directory (schema unchanged).
**Testing**: pytest; existing suite `tests/specify_cli/acceptance/test_negative_invariant_authoring.py` owns this contract and drives the CLI entry point `acceptance_verdict` through a fixture git repo (`_init_flat_mission`).
**Target Platform**: Linux/macOS dev machines and CI (GNU grep / BSD grep both support `-I`).
**Project Type**: single (Python package `src/specify_cli`).
**Performance Goals**: one `grep` subprocess per invariant execution, as today.
**Constraints**: no CLI/schema surface change (NFR-001); no new dependency (NFR-002); #2743/#5464 stay out of scope (C-001).
**Scale/Scope**: one function (`_check_grep_absence`), one test module, changelog entry.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Single canonical authority: the verdict/evidence semantics stay owned by
  `acceptance/matrix.py`; no second matcher appears. ✓
- Architectural alignment: edit inside the existing acceptance module seam; no
  boundary crossed. ✓
- ATDD-first / red-first (DIRECTIVE_034, C-002): the failing regression test
  lands before the fix in the same work package. ✓
- Smallest viable diff (`change-apply-smallest-viable-diff`): two behavior
  points in one function; no refactor. ✓
- Non-vacuity (`acceptance-criteria-non-vacuity`): the stale-`.pyc` test
  carries a same-fixture positive control (a tracked text file still containing
  a pattern yields `still_present` with named evidence), and the compound fix
  (skip binaries; stderr fallback) is proven half by half by asserting both the
  `confirmed_absent` verdict and the stderr-in-evidence behaviour. ✓

No violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/grep-absence-binary-evidence-01M66F4Y/
├── spec.md              # This mission's specification
├── plan.md              # This file
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/acceptance/
└── matrix.py                  # _check_grep_absence: add -I; stderr fallback in evidence

tests/specify_cli/acceptance/
└── test_negative_invariant_authoring.py   # red-first regression tests (existing module owns the contract)

docs/changelog/
└── CHANGELOG.md               # [Unreleased] entry for the user-facing fix
```

**Structure Decision**: single-package layout; the fix and its tests land in the modules that already own the acceptance-verdict contract.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

One concern; a single work package is proportionate.

### IC-01 — Binary-safe grep_absence verdict and named evidence

- **Purpose**: Make `_check_grep_absence` judge text files only and never record an empty match list on a non-absent verdict, so a stale `.pyc` cannot block `accept` invisibly.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002
- **Affected surfaces**: `src/specify_cli/acceptance/matrix.py` (`_check_grep_absence`), `tests/specify_cli/acceptance/test_negative_invariant_authoring.py`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: none
- **Risks**: `-I` must not weaken the text search (guarded by the positive control); BSD grep compatibility (also supports `-I`); evidence truncation must keep today's 500-char discipline on the error path and the 5-line discipline on the match list.
