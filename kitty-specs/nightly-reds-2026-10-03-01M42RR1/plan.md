# Implementation Plan: Nightly reds 2026-10-03

**Branch**: `kitty/nightly-reds-2026-10-03` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/nightly-reds-2026-10-03-01M42RR1/spec.md`

## Summary

Repair six groups of nightly-only test failures whose cause is a test or test-support file lagging
an intended, merged product change (evidence: [research/nightly-red-memo.md](research/nightly-red-memo.md)).
All changes are under `tests/`. Each repair is proven red on base `b2c466d7d1` and green on the
branch. The three wall-clock budget tests (group G) are left untouched for an operator ruling.

Branch contract: work starts from `kitty/nightly-reds-2026-10-03`, plans on it, and consolidates
into it. The pull request targets `main` of spec-kitty/spec-kitty; the operator merges.

## Technical Context

**Language/Version**: Python 3.11+ (nightly interpreter lane runs 3.13)
**Primary Dependencies**: pytest, pytest-xdist, typer `CliRunner`, git (subprocess)
**Storage**: N/A (temporary directories only)
**Testing**: named test node ids run with `PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q -n0 <ids>`; `make test-fast` once as orchestrator baseline
**Target Platform**: Linux CI runners (GitHub Actions nightly) and developer workstations
**Project Type**: single project; test tree only
**Performance Goals**: none added; no budget changes
**Constraints**: no file under `src/` changes; no budget, timeout, retry, skip or deselect; `ruff` and `ruff format --check --force-exclude` clean on touched files
**Scale/Scope**: 5 test files and 1 test-support file; 29 test cases repaired; 1 new test for the snapshot builder

## Charter Check

| Gate | Status |
|---|---|
| Standing Order 4 (judge the test; stale → re-pin; red-first; never retry-to-green) | Pass: each group classified as stale oracle or harness defect with the staling commit named; red-first evidence required per work package |
| Standing Order 9 / ADR 2026-07-17-1 (never green-wash) | Pass: no `regression`-marked test is touched; group G is reported, not hidden |
| Standing Order 6 (canonical sources) | Pass: derived counts read the existing registry authorities (`CANONICAL_COMMANDS`, `CLI_DRIVEN_COMMANDS`, `PROMPT_DRIVEN_COMMANDS`); no new authority |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Pass: named tests only; the e2e owned-worktree test runs as one parametrised case at most |
| Locality of change / smallest viable diff | Pass: one file per failure group |
| ATDD-first | Pass: groups A to E are already red on base (the existing tests are the reproduction); group F adds a failing snapshot-builder test before the fix |

No violations; Complexity Tracking is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-reds-2026-10-03-01M42RR1/
├── spec.md
├── plan.md
├── research/nightly-red-memo.md
├── checklists/requirements.md
└── tasks.md            # created by /spec-kitty.tasks
```

No `data-model.md`, `contracts/` or `quickstart.md`: the mission has no data model or external contract.

### Source Code (repository root)

```
tests/
├── _support/
│   └── shared_build_artifacts.py                      # IC-04
├── specify_cli/
│   ├── cli/commands/
│   │   ├── test_doctor_cli_surface_golden.py          # IC-01
│   │   ├── test_doctor_skills.py                      # IC-01
│   │   └── test_init_hybrid.py                        # IC-01
│   ├── missions/test_handle_equivalence_matrix.py     # IC-02
│   └── upgrade/migrations/test_hosted_endpoint_session_backfill.py   # IC-03
└── <new test next to the existing shared_build_artifacts tests>      # IC-04
docs/changelog/CHANGELOG.md                            # closeout, by the orchestrator
```

**Structure Decision**: edit existing test files in place; the only new file is the snapshot-builder
test, placed beside the existing tests for `tests/_support/shared_build_artifacts.py`.

## Implementation Concern Map

### IC-01 — Command-registry censuses

- **Purpose**: make the three tests that count commands agree with the shipped registry.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003
- **Affected surfaces**: `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py`, `test_doctor_skills.py`, `test_init_hybrid.py`
- **Sequencing/depends-on**: none
- **Risks**: the frozen `doctor` snapshot is parametrised on the frozen set, so `run-index` needs option and help entries too. The `doctor skills` envelope must stay an exact comparison on every other key. Derived counts must not be compared against themselves (assert against the files actually produced).

### IC-02 — Handle-equivalence fixture

- **Purpose**: seed a mission whose type equals the custom key the run-identity test runs.
- **Relevant requirements**: FR-004, NFR-002, NFR-003
- **Affected surfaces**: `tests/specify_cli/missions/test_handle_equivalence_matrix.py`
- **Sequencing/depends-on**: none
- **Risks**: `_seed_mission` has four callers; the default must stay `software-dev`.

### IC-03 — Migration sequencing harness

- **Purpose**: assert order from the applicable list, apply only the two migrations under test.
- **Relevant requirements**: FR-005, NFR-002, NFR-003
- **Affected surfaces**: `tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py`
- **Sequencing/depends-on**: none
- **Risks**: the test must fail if either migration id is missing from the applicable list.

### IC-04 — Shallow-source snapshot

- **Purpose**: make the shared source snapshot a readable repository when the checkout is shallow.
- **Relevant requirements**: FR-006, NFR-003
- **Affected surfaces**: `tests/_support/shared_build_artifacts.py` plus one new or extended test for it
- **Sequencing/depends-on**: none
- **Risks**: the fix is verified with a depth-1 clone fixture, not by running the 20-case e2e test under a shallow checkout; one e2e case is run on the full clone to prove no regression. `git clone --depth 1` of a local path needs a `file://` URL to produce a shallow clone.
