# Implementation Plan: Scoped heavy legs intersect the universe pre-step

**Branch**: `issue-7001-universe-prestep-scope` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/spec.md`
**Input**: Mission specification from `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/spec.md` (GitHub issue #7001)

## Summary

#6994 taught each heavy battery leg to run only the architectural gates a diff
touches, named in a selected-gates file (`SK_BATTERY_GATES_FILE`). The shared
test-universe pre-step was not taught the same lesson: its decision
(`collect_universe_prestep consumers --battery-part <part>`) still asks whether the
leg's *whole* battery partition holds a gate that calls `collect_universe()`. Both
partitions hold one such gate, so every leg — including a docs-only leg that selects
three unrelated gates — answers `true` and pays the key/restore/collect/save/check
chain, whose cold path is a full `pytest --collect-only` of the test tree (396.7 s
measured here; 89–233 s on CI) and whose store key always misses on a new commit.

The change hands the decision the leg's own selected-gates file and answers for the
intersection. A leg whose selected gates hold a consumer keeps collecting exactly as
today; a leg with no gates file (whole-leg, full mode, nightly backstop) is untouched;
a named file that cannot be read fails closed. The universe itself is never narrowed —
only the decision is — because the two consuming gates compare across the whole suite.

## Technical Context

**Language/Version**: Python 3.12 (repo `requires-python >= 3.11`)
**Primary Dependencies**: standard library; `pytest` and `yaml` only where the existing modules already use them
**Storage**: `.pytest_cache/universe-store/` (existing keyed store, unchanged)
**Testing**: `pytest` — `tests/ci/` for the CI scripts and workflow shape, `tests/architectural/` for the plug-in
**Target Platform**: GitHub Actions ubuntu-24.04 runners, plus local reproduction
**Project Type**: single CLI repository with a CI scripts tree (`scripts/ci/`)
**Performance Goals**: the decision stays under 5 s on a scoped leg (NFR-001; measured 1.5 s today), so skipping the pre-step is never paid back by the decision
**Constraints**: the plug-in's `SK_BATTERY_GATES_FILE` semantics, the battery pytest command line, and the `select -> key -> restore -> collect -> save -> pytest -> check` order are unchanged (C-001, C-003)
**Scale/Scope**: one CI job (`architectural-heavy`, 2 legs), one decision command, one workflow step's arguments, one reference page, one changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the selected-gates file format gets exactly one
  parser, in `scripts/ci/battery_scope.py`, called by both the plug-in's scope and the
  pre-step's decision. No second reader with its own inline parsing.
- **ATDD-first / red-first** — the decision's new behaviour is driven by tests written
  against the pre-existing entry point (`python -m scripts.ci.collect_universe_prestep
  consumers` and the workflow job model), not by a new helper's unit test alone.
- **Locality of change (DIRECTIVE_024) / smallest viable diff** — the change stays in
  the two scripts and the one workflow job that already own the scoped-leg contract.
- **Campsite cleaning (DIRECTIVE_025)** — the reference page's stale sentence about
  leg 2/2 holding no consumer is corrected in the same change, since this mission is
  the reason it is wrong.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — validation runs the affected `tests/ci` files;
  the battery partition proof runs as its own targeted test, never a full heavy sweep.
- **Pre-existing Failure Reporting Rule** — any red outside this diff is attributed and
  reported, never skipped.

## Project Structure

### Documentation (this mission)

```
kitty-specs/scoped-leg-universe-prestep-01M6BV5D/
├── plan.md                              # this file
├── research.md                          # Phase 0 (discovery findings)
├── data-model.md                        # Phase 1
├── quickstart.md                        # Phase 1
├── contracts/selected-gates-file.md     # Phase 1 — the one interface this changes
├── issue-matrix.json                    # written by the issue-verdict command
├── tasks.md                             # /spec-kitty.tasks
└── tasks/                               # one directory per work package
```

### Source Code (repository root)

```
scripts/ci/battery_scope.py                 # owns the selected-gates file: write + parse (one parser)
scripts/ci/battery_partition_plugin.py      # read_gates_file() delegates to that parser (contract unchanged)
scripts/ci/collect_universe_prestep.py      # consumers: intersect with the leg's selected gates
scripts/ci/collect_universe_universe.py     # (unchanged) the collector
tests/ci/test_battery_scope.py              # writer/readers round-trip, one fixture
tests/ci/test_battery_partition_plugin.py   # plug-in scope still reads the same file the same way
tests/ci/test_collect_universe_prestep.py   # red-first: the decision's new answers
tests/ci/test_ci_workflow_prestep_shape.py  # pins the ci-router.yml wiring + mutation cases
.github/workflows/ci-router.yml             # pass the leg's gates file to the select step
docs/development/reference/ci-gate-mechanics.md  # command table, where-it-runs, measurement
docs/changelog/CHANGELOG.md                 # [Unreleased] entry (#7001)
```

**Structure Decision**: the change is a brownfield edit inside the existing CI-scripts
boundary (`scripts/ci/` + its `tests/ci/` siblings). No new module, no new package, no
migration, no CLI command: three functions gain a narrowing input and one workflow step
gains an argument.

## Phase 0: Outline & Research

Resolved in `research.md` (discovery) and extended here:

- **Decision: intersect the decision, not the collection.** The universe is every test
  in `tests/`, and its consumers compare across the whole suite
  (`test_fast_tier_marker_completeness.py`, `test_same_tier_uniqueness.py`). Narrowing
  the collected list would hand them a partial universe and turn a real gate into a
  lie. Alternatives considered: (a) narrow `collect_universe()` to the leg's files —
  rejected, unsound; (b) keep the whole-part answer and only skip `save`/`check` —
  rejected, saves nothing on the cold path; (c) intersect the *decision* — chosen.
- **Decision: one parser, in the writer's module.** `battery_scope.py` gains
  `write_selected_gates` (already implicit in `output_lines`) and `read_selected_gates`;
  `battery_partition_plugin.read_gates_file` keeps its documented contract (unset means
  whole part; a missing named file is a `pytest.UsageError`) but parses through the same
  function. Alternative: a third module for "gates file I/O" — rejected as extra surface
  for four lines; the writer already lives in `battery_scope`.
- **Decision: explicit CLI input defaulting to the environment.** `consumers` gains
  `--gates-file <path>`; omitted means `$SK_BATTERY_GATES_FILE`; empty means the whole
  part. CI passes it explicitly (readable in the workflow), and a local reproduction can
  export the same variable the plug-in reads.
- **Decision: fail closed on an unreadable file.** Exit 1, no `true`/`false` on stdout,
  a message naming the file. A scoped leg that quietly skipped a collection a selected
  gate needs would make that gate collect for itself — the failure `check` exists to
  catch, one job later and much more confusingly.
- **Open question resolved:** whether `consumers` should also report how much it
  narrowed. It prints one explanatory line to stderr (selected count of part files) so a
  reader of the CI log sees why the pre-step declined; stdout stays exactly
  `true`/`false`.

## Phase 1: Design & Contracts

- **Entities** — `data-model.md`: the selected-gates file, the universe consumer set,
  the leg.
- **Interface** — `contracts/selected-gates-file.md`: the file format (one
  repository-relative gate path per line, blank lines ignored, a set not a list), who
  writes it (`scripts.ci.battery_scope select`), who reads it (the battery plug-in's
  scope; the pre-step's decision), and the fail-closed rules for each.
- **Entry point** — `python -m scripts.ci.collect_universe_prestep consumers
  --battery-part <part> [--gates-file <path>]` → `true`/`false` on stdout, exit 0; exit
  1 with no answer for an unknown part or an unreadable gates file.
- **Wiring** — `ci-router.yml`: the `select` step gains
  `--gates-file "${{ steps.scope.outputs.gates_file }}"`; nothing else about the step
  changes (still `shell: bash`, still no `||`, still always runs, still writes
  `universe=` to `$GITHUB_OUTPUT`).

## Implementation Concern Map

| IC | Concern | Where | FR |
| --- | --- | --- | --- |
| IC-01 | The file format has one writer and one parser | `scripts/ci/battery_scope.py` | FR-005 |
| IC-02 | The plug-in keeps its contract while reading through that parser | `scripts/ci/battery_partition_plugin.py` | FR-005, C-001 |
| IC-03 | The decision answers for the intersection, and fails closed | `scripts/ci/collect_universe_prestep.py` | FR-001..FR-004 |
| IC-04 | CI actually passes the file | `.github/workflows/ci-router.yml` | FR-006 |
| IC-05 | The shape test pins the wiring and rejects a decision that ignores the file | `tests/ci/test_ci_workflow_prestep_shape.py` | FR-006, C-003 |
| IC-06 | The saving is measured and documented | `docs/development/reference/ci-gate-mechanics.md`, `docs/changelog/CHANGELOG.md` | FR-007 |

## Risks

| Risk | Mitigation |
| --- | --- |
| The decision and the leg read one file with two parsers, drifting silently | One parser (IC-01/IC-02) plus a writer/readers round-trip test on one fixture |
| A scoped leg skips a collection a selected gate needs, and that gate collects for itself | The intersection is exact (`part ∩ selected ∩ consumers`); FR-002 covers the consumer-present case and `check` still catches a stray collection |
| A gates file path that does not exist (a broken `RUNNER_TEMP`) | Fail closed (FR-004, NFR-003) — the job reds, it does not skip |
| The workflow shape test's mutation cases silently stop covering the new argument | IC-05 adds mutations that strip the argument and that keep it but ignore it |
| Local timings mislead (a shared 20-agent host) | Report the local measurement with the host caveat and cite the published CI range (89–233 s) for ordering |

## Validation Strategy

1. **Red first**: write the decision tests that fail on `main` — a selected file of
   non-consumer gates still answers `true` today.
2. Targeted suites only: `tests/ci/test_collect_universe_prestep.py`,
   `tests/ci/test_battery_scope.py`, `tests/ci/test_battery_partition_plugin.py`,
   `tests/ci/test_ci_workflow_prestep_shape.py`, and the battery partition proof
   (`tests/architectural/test_battery_partition_plugin.py`).
3. The real CLI, not only helpers: every acceptance scenario is exercised through
   `python -m scripts.ci.collect_universe_prestep consumers ...` (a subprocess) and
   through the parsed `ci-router.yml` job model.
4. Docs: `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0);
   `tests/architectural/test_no_legacy_terminology.py` for the touched vocabulary.
5. CI: the router's own routing tests, the workflow-shape tests and the pause-synthetic
   gates are read as described in the PR body; no gate is skipped or weakened.
