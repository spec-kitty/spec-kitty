# Implementation Plan: Pin the post-fold convergence of the interview promotion (#6549)

**Branch**: `issue-6549-promote-answers-post-fold-convergence` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/promote-answers-post-fold-convergence-01M68JDG/spec.md`
**Input**: Mission specification from `kitty-specs/promote-answers-post-fold-convergence-01M68JDG/spec.md`

## Summary

#6549's reported non-convergence is already fixed on `main` by #6629: the shipped
`unify_charter_activation_promote_answers` step is registered as a recorded no-op
(`SUPERSEDED_MIGRATIONS`) and its successor resolves the activation write target
instead of reading `config.yaml` alone. What is missing is the regression evidence the
issue itself asks for. This Mission adds one focused test module that pins the
convergence three ways — the post-fold no-op, the end-to-end two-run upgrade of a
fold-crossing project, and a bite proof that the supersession entry is what holds the
line — and names that pin in the ADR amendment that documents the fix. No production
code changes.

## Technical Context

**Language/Version**: Python 3.11 (project floor; `uv`-managed, `uv run`/`.venv`)
**Primary Dependencies**: `pytest`, `ruamel.yaml`/`PyYAML`, `typer.testing.CliRunner`, `specify_cli.upgrade.*`, `charter.activation.*`
**Storage**: files on disk under `.kittify/` (`config.yaml`, `charter/charter.yaml`, `charter/activation.yaml`, `migration-ledger.jsonl`, `metadata.yaml`)
**Testing**: pytest; `tests/upgrade/` holds the upgrade-pipeline suites. New module: `pytest.mark.integration` + `pytest.mark.git_repo` (real `git init` + real CLI entry point), no network, no `uvx`.
**Target Platform**: Linux/macOS developer and CI machines
**Project Type**: single Python package (`src/specify_cli`, `src/charter`) with `tests/`
**Performance Goals**: new module under 60 s locally (three tests, each two upgrade runs at most)
**Constraints**: no `src/` change (NFR-002); shipped migration bytes untouched (C-001); no gate weakened (NFR-003)
**Scale/Scope**: one test module (~250 lines) plus one ADR sentence

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority / no second source of truth** — the Mission asserts the
  activation ledger (`.kittify/charter/activation.yaml`) stays the only activation
  authority and that `config.yaml` gains no copy. PASS.
- **ATDD-first / red-first** — the defect is already fixed, so the Module ships a
  guard that is *proven able to fail*: the bite proof removes the supersession entry
  and observes the #6549 symptom on the same fixture (tactic
  `acceptance-criteria-non-vacuity`: same-fixture positive control; production path,
  not a helper). PASS (see `## Complexity Tracking` for the honest note).
- **DIRECTIVE_044 (shipped migrations are byte-frozen)** — the Mission changes no
  migration module. PASS.
- **DIRECTIVE_041 (a test only where it guards real behaviour or a standing
  invariant)** — the guard pins a standing invariant (`upgrade` is a fixed point) that
  regressed once and whose fix is a single dictionary entry. PASS.
- **DIRECTIVE_024 (locality of change)** — one test module + one ADR sentence. PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — only the new module and its nearest suites run
  locally. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/promote-answers-post-fold-convergence-01M68JDG/
├── spec.md              # authored specification
├── plan.md              # this file
└── tasks/               # work-package task files (/spec-kitty.tasks output)
```

### Source Code (repository root)

```
src/
├── specify_cli/upgrade/
│   ├── supersession.py                                   # read-only: the table the bite proof edits
│   ├── registry.py                                       # read-only: selection/settlement
│   ├── runner.py                                         # read-only: the production entry point under test
│   └── migrations/
│       ├── m_unify_charter_activation.py                 # read-only (DIRECTIVE_044)
│       ├── m_unify_charter_activation_finalize.py        # read-only: the fold
│       └── m_4_0_0rc8_promote_interview_selections.py    # read-only: the successor
└── charter/activation/                                   # read-only: ledger seam

tests/upgrade/
├── test_activate_builtin_post_fold_dedup.py              # read-only: the rc35 precedent
├── test_upgrade_keeps_absent_activation_6629.py          # read-only: fixture style to follow
└── test_promote_answers_post_fold_convergence_6549.py    # NEW: the pin

docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md    # EDIT: name the pin in Amendment 2026-10-25
```

**Structure Decision**: single project. The test lives in `tests/upgrade/` beside the
rc35 post-fold precedent it mirrors, so the two post-fold dedup pins sit together. The
fixture follows `tests/upgrade/test_upgrade_keeps_absent_activation_6629.py` (real git
repo, real `AgentConfig`/`ProjectMetadata`, real CLI `upgrade` app) rather than
hand-writing YAML, because the failing property is an end-to-end upgrade property.

## Design

### Fixture: the fold-crossing project

`MigrationRunner`-level and CLI-level tests share one builder:

1. `git init -q -b work`, commit an empty root;
2. `save_agent_config(...)` and `ProjectMetadata(version="3.2.0rc30")` — the version
   stamp is **below** the fold and the promotion's `3.2.6rc1`, so both are selected and
   the ledger-adoption backfill does not settle them;
3. `answers.yaml` records `selected_directives: [DIRECTIVE_001]`;
4. `config.yaml` carries `activated_directives: [001-architectural-integrity-standard]`
   — the mirrored selection that makes the shipped promotion find nothing to promote
   (the state in which #6549's pass 1 recorded it `skipped` and pass 2 re-fired it);
5. commit.

Why not `spec-kitty init`? The fixture must be *pre-ledger*; `init` on this build
seeds the ledger and the activation ledger, which is exactly the state that does not
reproduce. Hand-building the pre-ledger shape keeps the fixture a description of the
defect rather than of a current init.

### Assertions

The convergence snapshot covers every file under the project except `.git/`, plus the
commit count. `charter.yaml` is not created until the fold runs, so the snapshot is
taken *after* the first upgrade.

- **FR-001 / FR-002 (two-run)**: after run 1, `config.yaml` has no `activated_*` key and
  `.kittify/charter/activation.yaml` exists; after run 2, every file's bytes are
  identical to the post-run-1 snapshot and `git rev-list --count HEAD` is unchanged.
- **FR-002 (seam)**: after the real fold migration applies, the *registered* class for
  the id is a `SupersededMigration`, `detect()` is False, and `apply()` leaves bytes
  identical.
- **FR-004 (positive control)**: the *shipped* class instantiated directly still
  answers `detect() is True` on the same fixture. Without this, "detect is False"
  could be vacuous (a probe that cannot see the promoted state at all).
- **FR-003 (bite)**: with the id removed from `SUPERSEDED_MIGRATIONS`, registry
  re-discovery through `auto_discover_migrations()` registers the shipped class; the
  same two-run fixture then leaves `activated_directives` in `config.yaml` with the
  whole built-in directive set on run 2 — the #6549 symptom on the same fixture. The
  test restores the table and the registry in `finally` so no later test inherits it.

### Risks

- Registry state is process-global: the bite test mutates `SUPERSEDED_MIGRATIONS` and
  reloads migration modules. Mitigation: an autouse fixture clears + re-discovers
  around every test, and the bite test restores the table in `finally` before that
  teardown runs.
- The bite test asserts on 38 ids; if a built-in directive is added the count changes.
  Mitigation: assert the *shape* (the config copy lists every built-in directive stem
  and is not the single selected stem), computed from the offering root, not a literal
  38.
- A bare fixture (no agent surfaces) can leave a session-presence refresh for a second
  run. Mitigation: drive the CLI `upgrade` entry point, which provisions surfaces in
  the same run, and assert the snapshot only after the first run completes; if a
  second-run write is legitimate the test surfaces it rather than hiding it (the
  prototype run of this plan shows the CLI path converging in one pass).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A guard test for behaviour that is already green (no red-first) | The defect's fix landed before this Mission (grounding, spec `## Context and grounding`); the issue's remaining deliverable is the missing regression pin | A red-first test cannot be written against current `main` without reintroducing the bug; the bite proof supplies the failing-on-regression evidence instead |

## Implementation Concern Map

### IC-01 — The convergence pin (tests)

- **Purpose**: Pin the two-run convergence of a fold-crossing project and the post-fold
  no-op of the registered promotion, with a same-fixture bite proof.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004
- **Affected surfaces**: `tests/upgrade/test_promote_answers_post_fold_convergence_6549.py` (new)
- **Sequencing/depends-on**: none
- **Risks**: registry/supersession global state (see `## Design` risks); fixture must be
  pre-ledger to be a description of the defect.

### IC-02 — The documentation cross-reference

- **Purpose**: Name the pin in ADR `2026-10-17-1` Amendment 2026-10-25 so the documented
  contract and its test are one hop apart.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
- **Sequencing/depends-on**: IC-01 (the file name must exist)
- **Risks**: ADR edits must not disturb the inventory tooling; only body prose changes,
  no new ADR file, so `docs_index`/`freshen_adr_inventory` are not required.
