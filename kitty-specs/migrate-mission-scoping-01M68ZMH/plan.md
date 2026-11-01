# Implementation Plan: Real `--mission` scoping for the corpus-walking `migrate` commands

**Branch**: `issue-6347-migrate-mission-scoping` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/migrate-mission-scoping-01M68ZMH/spec.md`
**Input**: Issue #6347 (P2, milestone "4.0.0 release scope"), follow-up deferred by #5294 / PR #6345.

## Summary

Three `migrate` subcommands walk a whole corpus and, since #5294 / PR #6345,
reject `--mission` outright. This mission gives `backfill-provenance`,
`charter-encoding` and `rebaseline-dossier-hashes` a real `--mission`: the flag
resolves through the canonical selector resolver in the CLI and narrows each
command's existing discovery walk to one Mission. `charter-encoding --mission`
skips the global charter store and reports the exclusion; omitting `--mission`
keeps the corpus-wide default; `rewrite-opposed-by` and `repin-hooks` keep
rejecting `--mission` because they have no Mission concept.

## Technical Context

**Language/Version**: Python 3.11+ (project floor; the code under change uses `from __future__ import annotations`, `X | None`, and `dataclass`).
**Primary Dependencies**: Typer (`>=0.24.1,<0.28`) + Click for the CLI, Rich for console output, pytest for tests. No new dependency.
**Storage**: Files on disk only — `kitty-specs/<mission>/acceptance-matrix.json`, `kitty-specs/<mission>/charter/*.{yaml,md,txt}`, `.kittify/charter/*.{yaml,md,txt}`, and `.kittify/dossiers/<slug>/snapshot-latest.json`. No database.
**Testing**: pytest, tiered by marker (`unit`, `fast`, `integration`); CLI behaviour through `typer.testing.CliRunner` invoking the assembled `specify_cli.app`; backends exercised directly against `tmp_path` fixtures. No full architectural/e2e sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: POSIX + Windows developer machines; the CLI is cross-platform, so path handling stays `pathlib`-only and no shell assumptions are introduced.
**Project Type**: single (Python package `src/specify_cli`) with the mission corpus under `kitty-specs/`.
**Performance Goals**: A scoped run must inspect O(1) Mission's files instead of O(corpus): `--mission` narrows discovery before any read, so no per-file scan of the rest of the corpus exists to be filtered.
**Constraints**: A scoped run never widens back to corpus scope (an unknown handle exits non-zero, it does not fall back); `--dry-run` never writes; every existing unscoped behaviour is byte-identical.
**Scale/Scope**: 3 CLI commands, 3 backends, 2 test modules, 1 changelog entry, 1 doc page touch (CLI reference regeneration). Roughly 350 changed lines including tests.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|------|---------|
| Single canonical authority (C-001) | Pass — handle resolution reuses `specify_cli.cli.selector_resolution.resolve_mission_handle`, the same seam `migrate backfill-merge-commit` uses; no second parser. |
| Locality of change (DIRECTIVE_024) | Pass — every edit lands in the command module, the three backends it already owns, and the two test modules that pin them. |
| Tests as scaffold, not friction (DIRECTIVE_041) | Pass — new tests pin the operator-visible contract (isolation, exclusion diagnostic, fail-closed handle) and use the pre-existing entry points; no implementation-coupled assertions. |
| Living documentation sync (DIRECTIVE_037) | Pass — the changelog entry and the regenerated CLI reference are updated in the same change. |
| PRs-only (DIRECTIVE_045) | Pass — no push to `main`, no merge; the operator merges. |
| `__all__` convention (C-007) | N/A — no new public module surface. |
| ATDD-first (C-011) | Pass — each command's scoped behaviour is written red first through `CliRunner`/the backend, then implemented. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/migrate-mission-scoping-01M68ZMH/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 decisions (D-01..D-05)
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/
│   ├── commands/
│   │   ├── migrate_cmd.py                    # the three commands: real --mission, resolution, reporting
│   │   └── migrate/
│   │       ├── backfill_provenance.py        # scoped matrix walk
│   │       └── charter_encoding.py           # scoped charter walk + global-store exclusion diagnostic
│   └── selector_resolution.py                # reused as-is (resolve_mission_handle)
└── dossier/
    └── rebaseline.py                         # scoped snapshot discovery

tests/
├── cli/test_mission_agnostic_flag.py         # reject set shrinks to the two non-Mission commands
└── migration/test_migrate_mission_scoping.py # red-first scoping contract for the three commands
```

**Structure Decision**: Single project. The CLI module keeps command wiring,
handle resolution and rendering; each backend keeps its own discovery walk and
gains one keyword-only `mission_slug` parameter. Handle parsing never reaches a
backend (C-002 in the spec).

## Phase 1 Design

### Approach (and rejected alternatives)

**Chosen: resolve once in the CLI, narrow each walk at its own discovery seam.**

- `migrate_cmd.py` gains one small helper,
  `_scoped_mission_slug(mission, repo_root, json_mode=...)`, which returns
  `None` when `--mission` is absent and otherwise delegates to
  `resolve_mission_handle`. That is the only new decision point; it is called by
  all three commands so their fail-closed behaviour is identical and stated once.
- `backfill_provenance._collect_matrix_paths(repo_root, mission_slug=None)`
  narrows its *mission loop* to one directory and still resolves that Mission's
  matrix through `placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`, so a
  coordination-homed matrix stays reachable.
- `charter_encoding._collect_charter_files(project_root, mission_slug=None)`
  scans one Mission's `charter/` directory and does **not** scan
  `.kittify/charter/`; the summary records `global_store_excluded` and both
  renderers report it.
- `dossier.rebaseline.iter_recorded_snapshot_files(root, mission_slug=None)`
  filters the existing glob by *mission identity from the path*: the dossier
  directory slug or the owning `kitty-specs/<slug>` source directory. It does
  **not** read each candidate's JSON to decide — that would break NFR-001 (a
  scoped run reads at most the target Mission's files).

**Rejected: resolve the handle inside each backend.** Three copies of handle
parsing, and the mid8/prefix forms would need `mission_resolver` inside modules
that today take a directory name (`backfill_mission_type_repo` documents that a
mid8 raises `MissionNotFoundError`). One resolver call in the CLI keeps one
authority and one failure mode.

**Rejected: post-filter resolved paths.** `_collect_matrix_paths` resolves each
matrix through a placement seam, so filtering *after* resolution would have had
to walk every Mission first — exactly the corpus read the feature exists to
avoid.

**Rejected: read the recorded `mission_slug` field to scope rebaseline.** It
would match more historical layouts, but it reads every snapshot in the corpus
to decide, contradicting NFR-001 and the "narrow before read" property. The path
signals (dossier slug, owning source dir) cover both real layouts; the residual
asymmetry is documented in `rebaseline.py` rather than paid for with a corpus
read.

### Structure and data flow

```
argv --mission <handle>
        │
        ▼
migrate_cmd.<cmd>  ── _scoped_mission_slug ──► resolve_mission_handle  (exits 2 / 1 on unknown)
        │  canonical mission_slug | None
        ▼
backend(repo_root, dry_run=…, mission_slug=…)
        │
        ├── backfill_provenance: mission loop narrowed → placement_seam read_dir(ACCEPTANCE_MATRIX)
        ├── charter_encoding:    one charter dir; global store skipped + recorded in summary
        └── dossier.rebaseline:  snapshot glob filtered by path-derived mission identity
        │
        ▼
summary (+ mission / global_store_excluded) → JSON payload | human summary
```

### Behaviour table

| Command | `--mission` absent | `--mission <handle>` |
|---|---|---|
| `backfill-provenance` | every `kitty-specs/*/acceptance-matrix.json` (unchanged) | that Mission's matrix only |
| `charter-encoding` | every Mission charter dir **and** `.kittify/charter/` (unchanged) | that Mission's charter dir only; global store excluded and reported |
| `rebaseline-dossier-hashes` | every recorded `snapshot-latest.json` (unchanged) | that Mission's recorded snapshot(s) only |
| `rewrite-opposed-by` | pack-scoped (`--pack`), unchanged | exit 2, "not mission-scoped" (unchanged) |
| `repin-hooks` | repo repair, unchanged | exit 2, "not mission-scoped" (unchanged) |

### Contracts touched

- CLI surface: three commands gain a **visible** `--mission HANDLE` option, so
  `--help` for those three changes (NFR-003). The other two stay hidden.
- JSON payloads: `backfill-provenance` and `rebaseline-dossier-hashes` gain a
  top-level `"mission"` (slug or `null`); `charter-encoding` gains `"mission"`
  and `"global_store_excluded"`. Additive only — no existing key changes shape.
- Python: `run_backfill_provenance_migration`, `run_charter_encoding_migration`,
  `rebaseline_recorded_snapshots` and `iter_recorded_snapshot_files` gain a
  keyword-only `mission_slug`/`mission` default `None`. Existing callers are
  unaffected.

## Complexity Tracking

No charter violations; nothing to justify.

## Implementation Concern Map

### IC-01 — `--mission` arrival and handle resolution (the scope gate)

- **Purpose**: Make the three commands *accept* a real `--mission` and turn it
  into exactly one canonical Mission slug (or a loud failure), before any backend
  walks anything.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-005, FR-007, FR-008, C-001, C-002, C-003.
- **Affected surfaces**: `src/specify_cli/cli/commands/migrate_cmd.py` (the three
  command decorators/signatures/docstrings, `_scoped_mission_slug`), reuse of
  `src/specify_cli/cli/selector_resolution.py`.
- **Sequencing/depends-on**: none.
- **Risks**: leaving `cls=CorpusWideCommand` on a scoped command would keep
  rejecting the flag; declared-but-unused `--mission` would recreate the very
  silent no-op #5294 closed. Both are pinned by tests.

### IC-02 — Narrow each corpus walk at its discovery seam

- **Purpose**: Teach the three backends to walk one Mission, without changing
  what they do to the files they find.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-006, NFR-001, NFR-004.
- **Affected surfaces**: `src/specify_cli/cli/commands/migrate/backfill_provenance.py`,
  `src/specify_cli/cli/commands/migrate/charter_encoding.py`,
  `src/specify_cli/dossier/rebaseline.py`.
- **Sequencing/depends-on**: IC-01 (the slug parameter arrives from there).
- **Risks**: `backfill-provenance` must keep the `placement_seam` read (a raw
  `kitty-specs/<slug>/acceptance-matrix.json` join would miss coordination-homed
  matrices); `rebaseline` must not turn its glob into an "open every file"
  filter (NFR-001); `charter-encoding` must not let a pre-existing global store
  fail a valid scoped run.

### IC-03 — Report the scope honestly (exclusion diagnostic, exit codes, payloads)

- **Purpose**: An operator running a scoped command can see what was scoped and
  what was deliberately left out — in both human and JSON renderings — and the
  exit code reflects only the work the run actually did.
- **Relevant requirements**: FR-004, NFR-003, and the spec's User Story 2.
- **Affected surfaces**: `charter_encoding.py` (`_ScanSummary`,
  `_emit_json_summary`, `_emit_human_summary`), `migrate_cmd.py` payload assembly
  for `backfill-provenance` and `rebaseline-dossier-hashes`.
- **Sequencing/depends-on**: IC-02.
- **Risks**: a diagnostic in only one rendering half-ships (a scripted caller or
  a human sees silence); a `charter-encoding --mission` run that treats a
  pre-existing global ambiguity as its own failure would fail a valid operation.

### IC-04 — Pin the contract: red-first tests and the shrink-only reject-set ratchet

- **Purpose**: Lock the new behaviour and the reduced reject set with tests that
  fail before the change, so a later refactor cannot re-open either the silent
  no-op or an over-broad rejection.
- **Relevant requirements**: all FRs; SC-001..SC-004; C-004.
- **Affected surfaces**: `tests/migration/test_migrate_mission_scoping.py` (new),
  `tests/cli/test_mission_agnostic_flag.py` (`_REJECT_SET` shrink + a scoped-set
  assertion).
- **Sequencing/depends-on**: IC-01..IC-03 for the green half; the red tests are
  authored first.
- **Risks**: a test that only asserts "no crash" would pass on the current
  reject; each scoping test therefore asserts a *byte-identity* of the
  non-target fixture and a *change* of the target fixture on the same run.
