# Implementation Plan: DRG orphan residual — a live, non-frozen record

**Branch**: `issue-6513-drg-orphan-residual-live-record` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/drg-orphan-residual-live-record-01M68ZV0/spec.md`

## Summary

Issue #6513's literal red is already fixed: `bd7fdb7f36` raised `DOCUMENTED_ORPHAN_RESIDUAL`
21 -> 25 for the four `mission_step_contract:plan/*` nodes vendored by #6379, which are
edge-less by construction. This mission completes the other half of the issue's remedy without
touching the ceiling or the graph: it gives the shipped-graph residual a **live** current-state
record (the file the gate currently points at is an immutable archive), retargets the gate's
failure message and docstring at that record plus the pinned membership ledger, and adds a guard
that the recorded URN set equals the measured shipped orphan set — so a silent ceiling raise or
an unrecorded orphan fails a test.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: none new — `charter.offering.drg.loader.load_built_in_graph` (already
imported by the ceiling test module), `pathlib`, `pytest` (already in the module)
**Storage**: files in the repository: one live Markdown record, one test module
**Testing**: `pytest`; the guard lives beside the ceiling assertion it binds, in
`tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`
**Target Platform**: repository test suite (CI `module-tests` lane for `tests/specify_cli/cli/commands`)
**Project Type**: single (CLI + doctrine packs)
**Performance Goals**: the guard reads one small Markdown file and reuses the single
`load_built_in_graph()` already loaded by the module's own test; <= 2 s over module load (NFR-001)
**Constraints**: no network, no clock dependence (NFR-002); docs gates green without a
whole-reference regeneration (NFR-003); ceiling unchanged at 25; no `kitty-specs/` edit; no gate
weakened (C-001..C-003)
**Scale/Scope**: 3 files touched (1 new live doc + 1 test module + 1 changelog entry) plus mission
artifacts; no production code change

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — one live record for the current-state residual; the frozen
  archive stays the historical, as-of-date record and is cited, never edited. The pure-view
  membership ledger (`_SHIPPED_ORPHANS`) keeps its existing role; the new record is bound to the
  *measured shipped* set, the same frame the ceiling measures.
- **ATDD-first / red-first** — the guard is written first and shown failing (the live record does
  not exist yet), then the record is authored to satisfy it. `DIRECTIVE_034` test-first-bug-fixing.
- **C-003 / D-C2 (no metric gaming)** — no manufactured edge, no deleted artifact, ceiling fixed
  at 25. `packs/built-in/` untouched.
- **Test policy** — `NO_FULL_HEAVY_SUITES_IN_MISSION`: run the touched module, not a directory.
- **Docs discipline** — the record is a `docs/architecture/` explanation page already registered in
  `docs/development/page-inventory.yaml` and its ToC, so no inventory/ToC churn; frontmatter
  `updated:` moves with the edit.

## Project Structure

### Documentation (this mission)

```
kitty-specs/drg-orphan-residual-live-record-01M68ZV0/
├── spec.md              # Mission specification
├── plan.md              # This file
├── tasks.md             # Task outline
├── tasks/WP01-*.md      # Work package
└── traces/              # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
docs/
├── architecture/
│   └── charter-synthesis-drg.md        # gains the live "shipped-graph orphan residual" section
└── changelog/CHANGELOG.md              # [Unreleased] entry (#6513)
tests/
└── specify_cli/cli/commands/
    └── test_doctrine_regenerate_graph.py   # guard + retargeted message/docstring (ceiling stays 25)
```

**Structure Decision**: the live record goes into the existing DRG architecture explanation page
(`docs/architecture/charter-synthesis-drg.md`) rather than a new page. Two reasons: the page is
already in the page inventory and the explanation ToC, so a new page would drag inventory, ToC,
redirect and spelling surfaces into a documentation-truth-up change (blast radius beyond the
issue); and the orphan residual is a property of the DRG that page already explains. The section is
self-contained and machine-parseable: a single fenced block enumerating the 25 URNs.

## Approach

1. **Guard first (red).** Add to the ceiling test module:
   - `LIVE_RESIDUAL_RECORD` — path to `docs/architecture/charter-synthesis-drg.md`.
   - `_documented_orphan_urns(record_path)` — parse the record's current-state fenced block
     (delimited by `<!-- drg-orphan-residual:begin -->` / `<!-- drg-orphan-residual:end -->`),
     returning the set of backticked URNs in it. Only that block counts, so prose and the frozen
     historical sections cannot accidentally satisfy the guard.
   - `_orphan_urns(graph)` — extract the URN-set form of the existing `_count_orphans` (which
     becomes `len(_orphan_urns(...))`, no behaviour change).
   - `test_documented_residual_matches_measured_shipped_orphans` — asserts set equality between
     `_documented_orphan_urns(...)` and `_orphan_urns(load_built_in_graph())`, with a failure message
     naming both drift directions (an unrecorded orphan; a recorded node that is no longer an
     orphan) and telling the reader to update the record and `DOCUMENTED_ORPHAN_RESIDUAL` together.
   Run it: it must fail (record block absent).
2. **Author the live record.** Add the section to `docs/architecture/charter-synthesis-drg.md`:
   method (recompute, don't copy), the 25 URNs in the fenced block grouped by disposition
   (21 edge-less-by-construction step contracts; `glossary_pack:spec-kitty-core`;
   `agent_profile:human-in-charge`; `styleguide:deployable-skill-authoring`;
   `toolguide:powershell-syntax`), the per-group rationale, the ceiling ledger (14 -> 18 -> 14 ->
   29 -> 30 -> 21 -> 25) with #6379/#6432 and this mission's #6513, the pointer to
   `_INTENTIONAL_ORPHANS`/`_SHIPPED_ORPHANS`, and an explicit note that the
   `kitty-specs/.../drg-orphan-residual.md` record is a frozen archive and stays as-of-date.
   Re-run the guard: green.
3. **Retarget the gate's instructions (FR-003).** In the same test module, update
   `DOCUMENTED_ORPHAN_RESIDUAL`'s docstring entries that say "Full narrative in
   `drg-orphan-residual.md`" to name the live record and say the archive file is frozen, and
   rewrite the assertion message to: wire a real inbound edge, or add the URN to the live record
   **and** raise this ceiling, together. Do not change the constant.
4. **Negative proof (edge cases).** Prove the guard in both directions with temporary mutations
   during implementation (drop a URN from the record -> fail naming it; add a stale URN -> fail
   naming it), then restore. Record the commands and outputs in the PR.
5. **Changelog.** `docs/changelog/CHANGELOG.md` `[Unreleased]` -> `### Fixed` entry, impact-first,
   `(#6513)`, before/after, under 1,200 characters.
6. **Gates.** `pytest tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`,
   `uv run python -m scripts.docs.check_docs_freshness --ci`, markdownlint on touched docs, and
   `tests/architectural/test_archive_root_byte_identical.py` (proves `kitty-specs/` is untouched).

## Complexity Tracking

No charter violations. One judgement call: binding a *docs* file to a *test* constant. It is
justified because the issue is precisely "the documented residual and the ceiling disagree and
nothing notices"; the guard is the only mechanism that makes the documented residual
load-bearing. It is additive (C-003) and cheap (NFR-001).

## Implementation Concern Map

### IC-01 — Record parseability and drift messages

The record must be machine-parseable without brittle Markdown table parsing: a fenced block of
URN bullets inside HTML-comment delimiters. Failure messages must name the exact URNs and the
remedy, in both directions.

### IC-02 — The ceiling's own instructions

The docstring is a long historical ledger whose recent entries point at a frozen file. Retarget
the pointers (and the assertion message) without rewriting the history: the historical entries
keep their as-of-date wording, and one new entry explains the live record and the frozen archive.
