# Implementation Plan: Centralized-runtime detection is a project property

**Branch**: `issue-6551-centralized-runtime-detection-is-project-local` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/spec.md`

## Summary

`uses_centralized_runtime()` currently answers "does this project use the 2.x
centralized runtime?" by first asking whether the *operator's home* has
`~/.kittify/cache/version.lock`. Move the project's own `metadata.yaml` stamp to
first place: a readable stamp at `>= 2.0.0` answers `True` outright, and the home
check survives only for the metadata-less shapes that existing tests pin. That
single predicate change makes `0.6.7_ensure_missions.detect()` and
`0.12.0_documentation_mission.detect()` deterministic for a given commit, so a
`upgrade` run on a machine with no `~/.kittify` no longer copies the packaged
missions in, and no frozen overrides get auto-committed.

## Technical Context

**Language/Version**: Python 3.11+ (project floor; the CLI runs on 3.11–3.13)
**Primary Dependencies**: `packaging.version.Version`, PyYAML (already in use by
`ProjectMetadata`), Typer + `typer.testing.CliRunner` for the production-path test
**Storage**: `.kittify/metadata.yaml` (project stamp), `~/.kittify/cache/version.lock`
(global runtime marker), `.kittify/migration-ledger.jsonl` (applied authority)
**Testing**: pytest; `pytest.mark.fast` for the unit cases, `pytest.mark.integration`
+ `pytest.mark.git_repo` for the real `upgrade` invocation (mirrors
`tests/upgrade/test_upgrade_integration.py`)
**Target Platform**: any (POSIX and Windows paths both flow through
`get_kittify_home()`)
**Project Type**: single (Python CLI in `src/specify_cli/`)
**Performance Goals**: detection stays pure file I/O with no new syscalls beyond
the one `metadata.yaml` read it already performed on the bootstrapped path
**Constraints**: NFR-001 no-op upgrade leaves `git status --porcelain` empty;
NFR-002 detection writes nothing; NFR-003 the new integration test runs in under
60s and stays out of the full heavy suites
**Scale/Scope**: 1 predicate (`src/specify_cli/upgrade/compat.py`), 2 call sites
(unchanged), 1 test module extended + 1 test module added

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | How this plan satisfies it |
| --- | --- |
| **Single canonical authority** | `uses_centralized_runtime` stays the only answer to "is this a 2.x runtime project"; the fix reorders its inputs rather than adding a second predicate (C-002). |
| **ATDD-first / red-first (DIRECTIVE_034)** | The production-path test is written first and must fail on `HEAD` before the predicate changes; the helper cases are added with it so the red is legible. |
| **Locality of change (DIRECTIVE_024)** | One function body plus tests plus the changelog. No migration, registry, ledger or runner file changes. |
| **Smallest viable diff** | No new module, no new abstraction, no configuration knob. |
| **Ledger is the applied authority (ADR 2026-10-17-1, C-001)** | `registry.get_applicable` and `migration_settled` are untouched; the change restores the determinism the ledger's `skipped` semantics assume. |
| **NO_FULL_HEAVY_SUITES_IN_MISSION** | Run `tests/upgrade/` plus the touched-module suites locally; CI owns the heavy sweeps. |
| **Pre-existing Failure Reporting Rule** | Any red in `tests/upgrade/` that is not caused by this diff is reproduced on pristine `origin/main` and cited in the PR's `## Deferred`. |
| **Terminology** | "centralized runtime" and "override" keep their existing meanings in `docs/context/`; the mission introduces no new term. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery decisions D-1..D-4)
├── spec.md              # Mission specification
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── traces/              # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── compat.py                                  # THE change: predicate order
├── migrations/m_0_6_7_ensure_missions.py      # unchanged call site
└── migrations/m_0_12_0_documentation_mission.py  # unchanged call site

tests/upgrade/
├── test_compat.py                             # extended: pre-2.0 + fresh-home cases
└── test_upgrade_empty_home_noop.py            # new: production-path regression
```

**Structure Decision**: Single project. The change lives entirely in the
existing `specify_cli.upgrade` package; no new package or layer is introduced.

## Complexity Tracking

No charter violations. The plan adds one test module and extends one, which is
the minimum needed to pin both the helper contract and the production path.

## Implementation Concern Map

### IC-01 — Project-stamped detection

- **Purpose**: Make the "is this a 2.x runtime project" answer come from the
  project's own `metadata.yaml` first, so the same commit answers the same way on
  every machine.
- **Relevant requirements**: FR-001, FR-004, FR-005, NFR-002, C-001, C-002
- **Affected surfaces**: `src/specify_cli/upgrade/compat.py`
  (`uses_centralized_runtime`), consumed by
  `migrations/m_0_6_7_ensure_missions.py:detect` and
  `migrations/m_0_12_0_documentation_mission.py:detect`
- **Sequencing/depends-on**: none
- **Risks**: Ordering mistake that also changes the metadata-less answers
  (FR-005). Mitigated by re-reading the four pinned `test_compat.py` cases and
  adding the pre-2.0-under-fresh-home case explicitly.

### IC-02 — Proof at the production entry point

- **Purpose**: Pin the user-visible outcome — a converged project's `upgrade
  --project --yes` under an empty `SPEC_KITTY_HOME` makes no tracked change — so a
  future rewiring cannot regress it silently while helper tests stay green.
- **Relevant requirements**: FR-002, FR-003, NFR-001, NFR-003, SC-001, SC-003
- **Affected surfaces**: `tests/upgrade/test_upgrade_empty_home_noop.py`
  (new), `tests/upgrade/test_compat.py` (extended),
  `tests/upgrade/migrations/test_m_0_6_7_ensure_missions.py` and
  `tests/upgrade/test_m_0_12_0_documentation_mission_unit.py` (fresh-home pins)
- **Sequencing/depends-on**: IC-01 (the test is authored red-first before IC-01)
- **Risks**: A fixture that is not genuinely converged would pass vacuously; the
  fixture must seed the ledger's `skipped` records for both legacy migrations and
  assert the positive control (overrides absent *and* a real `success`-stamped
  neighbour still recorded).

### IC-03 — Changelog and docs

- **Purpose**: Record the user-facing fix in `docs/changelog/CHANGELOG.md` under
  `[Unreleased]` with the issue reference and before/after.
- **Relevant requirements**: SC-004
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a
  symlink). No ADR: this restores a documented invariant rather than changing a
  structural boundary, so `check_docs_freshness` should be unaffected.
- **Sequencing/depends-on**: IC-01
- **Risks**: Changelog entry over the 1,200-character cap; keep it impact-first
  and terse.
