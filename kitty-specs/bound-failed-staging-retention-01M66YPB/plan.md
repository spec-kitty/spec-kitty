# Implementation Plan: Bound failed-synthesis staging retention

**Branch**: `issue-6723-bound-failed-staging-retention` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: `kitty-specs/bound-failed-staging-retention-01M66YPB/spec.md`
**Audience**: software-engineer and automation-agent.

## Summary

Deliver #6723 in one bounded WP: after a refused synthesis preserves its run's
`.kittify/charter/.staging/<run_id>.failed/` directory, keep only the newest 3
failed directories under `.staging/` and remove the rest. The change lives in
the shared staging lifecycle (`StagingDir` in
`src/charter/activation/synthesizer/staging.py`), so `charter synthesize`,
`charter resynthesize`, the synthesizer orchestrator and the dry-run paths all
inherit it. The current run's failure, its `cause.yaml`, and any live
(non-`.failed`) staging directory are never removed; removal goes through
`PathGuard.rmtree` and never raises over the synthesis failure. One named
constant owns the number, and the CLI refusal hint plus the
`.staging` governance-files row state it.

There is no product-architecture decision here: no new command, no config key,
no schema change, no change to synthesis, validation or promotion semantics.

## Technical Context

**Language/Version**: Python 3.11+; checkout CLI `spec-kitty` 4.0.0rc8
**Primary Dependencies**: Existing `ruamel.yaml`, `kernel.clock` and the synthesizer's own `PathGuard`; no additions, upgrades or removals
**Storage**: Filesystem only — `.kittify/charter/.staging/<run_id>/` and `<run_id>.failed/` (gitignored); no database, no state file
**Testing**: Existing pytest synthesizer entry points (`tests/charter/synthesizer/`); failing-first test before the production change, including one refusal through the real `charter synthesize` CLI
**Target Platform**: Existing Linux/macOS/Windows CLI; ordering must not depend on a new timestamp source beyond directory metadata
**Project Type**: Single existing Python CLI repository
**Performance Goals**: Retention adds ≤ 50 ms to a refusal with 100 failed directories present (NFR-001); one directory listing plus one metadata stat per candidate (NFR-002)
**Constraints**: Never remove the current run's failure, a live staging directory, or a `cause.yaml` the command just reported; retention is best-effort and never masks the synthesis error (FR-002, FR-003, FR-006); new-code coverage ≥ 90 %; no full heavy local suite
**Scale/Scope**: One issue, one WP; `staging.py` plus the `synthesize` refusal hint, their tests, the `.staging` governance-files row, the atomicity ADR's retention sentences, and one changelog entry

## Charter Check

*Entry and post-plan review: pass; no new architecture, dependency or contract decision.*

- **Single canonical authority**: the retention bound is owned by one constant in
  the staging lifecycle module (FR-008); the CLI hint imports it rather than
  restating "3". No second retention implementation anywhere.
- **ATDD first**: a failing test through the pre-existing entry point
  (`StagingDir.create` / `commit_to_failed`, plus one real CLI refusal) lands
  before the production change; the red→green order is recorded in the PR.
- **Locality of change** (DIRECTIVE_024): four production/doc surfaces, all on
  the failure path of the staging lifecycle. No refactor of `PathGuard`,
  `write_pipeline`, the bundle validator or the collision remedy from #6510.
- **Guard seam** (ADR 2026-04-17-2): deletions go through `PathGuard.rmtree`;
  `tests/charter/synthesizer/test_path_guard.py` must keep passing unchanged.
- **Evidence preservation**: `cause.yaml` keeps its `{reason, traceback,
  timestamp}` shape; the retention pass never edits it.
- **Mission hygiene**: three tracer files seeded through
  `spec-kitty agent tracer-append`; issue-matrix row for #6723; branch
  `issue-6723-bound-failed-staging-retention`, PR to `main` only, no merge.
- **Pre-existing Failure Reporting Rule**: any CI red that is not attributable to
  this diff is diagnosed against `origin/main` and cited, not skipped.

**Post-design re-check**: pass. The design adds one pure-ish helper plus a call
site; it introduces no new module boundary, no dependency and no public API.

## Project Structure

### Documentation (this mission)

```text
kitty-specs/bound-failed-staging-retention-01M66YPB/
├── spec.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── reasons-canvas.md
├── data-model.md
├── quickstart.md
├── decisions/DM-01M66YQ2ZWJ6KDAH59GTBB24YM.md
└── tasks.md + tasks/WP01-*.md                (tasks phase)
```

### Source Code (repository root)

```text
src/charter/activation/synthesizer/staging.py            # retention helper + call from commit_to_failed
src/specify_cli/cli/commands/charter/synthesize.py       # refusal hint states the bound
src/charter/activation/synthesizer/path_guard.py         # unchanged; the deletion seam
tests/charter/synthesizer/test_staging_atomicity.py      # existing lifecycle suite (unchanged expectations)
tests/charter/synthesizer/test_staging_retention_6723.py # new focused tests (unit + CLI refusal)
docs/context/governance-files.md                         # `.staging` row states the bound
docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md # retention sentences updated
docs/changelog/CHANGELOG.md                              # [Unreleased] entry
```

**Structure Decision**: Single existing Python CLI repository. The retention is
part of the synthesizer's filesystem lifecycle, so it belongs beside
`StagingDir`, not in the CLI layer or in a new module.

## Validation and evidence handoff

- Targeted: `uv run --frozen pytest tests/charter/synthesizer/ -q` (the owning
  subsystem directory per AGENTS.md blast-radius rule) plus the new test file
  explicitly.
- Baseline: `make test-fast`.
- Quality: `uv run --frozen ruff check`, `ruff format --check` on the changed
  files, `uv run --frozen mypy` on the changed module, and
  `tests/architectural/test_no_legacy_terminology.py`.
- Docs (only if a doc page is added; this mission edits existing pages and the
  changelog): `check_docs_freshness --ci` if the ADR inventory changes.
- PR: draft first, five-section body, `taken-by-human`, CI followed on the head
  SHA to green, then flipped to ready for review with `ready-for-squad`. Nothing
  merged.

## Complexity Tracking

No charter violations: the change adds no project, layer, dependency or pattern.

## Implementation Concern Map

### IC-01 — Bounded failed-staging retention in the lifecycle

- **Purpose**: Keep the newest 3 preserved failures and remove the rest, without
  ever removing the current run or a live staging directory.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008; NFR-001..004; SC-001..SC-006
- **Affected surfaces**: `src/charter/activation/synthesizer/staging.py`
- **Sequencing/depends-on**: none
- **Risks**: ordering ties (mtime collisions) must be deterministic; a
  concurrent run's in-progress directory must never be a candidate; pruning must
  not raise over the synthesis error.

### IC-02 — Operator-facing truth about the bound

- **Purpose**: The refusal hint and the reference docs name the retention bound
  from the same source as the implementation, so the stated number cannot drift.
- **Relevant requirements**: FR-007, FR-008, FR-009; SC-006
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/synthesize.py`,
  `docs/context/governance-files.md`,
  `docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 (the constant must exist before the text uses it)
- **Risks**: doc drift (the ADR currently says failed dirs are "not deleted");
  changelog length cap of 1,200 characters.
