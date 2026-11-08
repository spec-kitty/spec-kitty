# Implementation Plan: Render only the charter scope the command reads (#6462)

**Branch**: `kitty/mission-issue-6462-charter-render-scope-per-call-01M69065` (lands on `main` via `issue-6462-charter-render-scope-per-call`) | **Date**: 2026-10-31 | **Spec**: `kitty-specs/issue-6462-charter-render-scope-per-call-01M69065/spec.md`
**Input**: Mission specification from `kitty-specs/issue-6462-charter-render-scope-per-call-01M69065/spec.md`; discovery evidence in `research.md`.

## Summary

A persona render (`charter context`, and the prompt build behind `next` / `agent
action`) parses the entire shipped catalog — 265 documents across eight built-in
domains — although the governance resolution it feeds reads only paradigms, directives
and template sets (52 documents). A read-only board additionally parses 26 profile files
and 13 DRG fragments to answer one structural boolean. This plan makes the read set
match the read: an explicit, validated domain scope on the catalog loader; the two
governance call sites declare their scope; the profile repository builds its lineage
graph on first use instead of in its constructor. Output is unchanged; the census
guards count parsed documents, so a wider render fails a test rather than quietly
taxing every CLI call.

## Technical Context

**Language/Version**: Python 3.11 (repository `requires-python >= 3.11`; `mypy --strict` on the touched `src/` packages)
**Primary Dependencies**: Typer/Click (CLI), `ruamel.yaml` (doctrine parsing), Pydantic (artifact models), pytest (tests)
**Storage**: N/A — reads shipped pack YAML under `packs/built-in/`, `.kittify/charter-packs/` (project layer) and the activation ledger; writes nothing new
**Testing**: `uv run --frozen pytest`; new deterministic census tests in `tests/charter/`, plus the existing charter/conformance suites
**Target Platform**: Linux/macOS/Windows CLI (path handling and encoding already abstracted by the existing seams)
**Project Type**: single project (`src/` + `tests/`)
**Performance Goals**: `charter context --action <step>` parses ≤ 60 shipped documents (baseline 265) and `agent tasks status` parses 0 DRG fragments (baseline 13) and ≤ 70 shipped documents (baseline 107); wall clock reported, not asserted (shared host, #6858)
**Constraints**: no cross-process cache, TTL or bypass flag; `load_offering_catalog()` with no arguments keeps today's behaviour; charter reads stay behind the `charter.activation`/`charter.offering` seam
**Scale/Scope**: ~6 source files touched, 2 new test modules, 1 changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status |
|---|---|
| Single canonical authority | PASS — one catalog loader keeps owning the scan; the scope is a parameter of it, not a second loader. |
| ATDD-first | PASS — a census test through the pre-existing entry point fails on `main` (265 parses, 13 graph parses) and passes after; behaviour-parity tests stay green. |
| Tiered rigour / DDD | PASS — the change is inside `charter`'s own bounded context (`activation` for orchestration, `offering` for artifact repositories); `specify_cli` sees no new import. |
| `DIRECTIVE_024` locality of change | PASS — six files, each edit local to the read being scoped; no public signature removed. |
| `DIRECTIVE_025` boy-scout | PASS — the two stale "parses at most once per change" comments that the change invalidates are corrected in place. |
| Canonical sources / terminology | PASS — "domain" matches `OfferingCatalog.domains_present`; no new vocabulary. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | PASS — targeted charter/test-census suites locally; CI owns the full sweep. |
| Pre-existing Failure Reporting Rule | PASS — #5927, #6801, #6816, #6798 are recorded in the issue matrix as context-only; any red matching them is classified, not skipped. |
| No governance bypass | PASS — no cache architecture, no `--no-charter-render` flag, warning contract untouched (spec C-001, C-003). |

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6462-charter-render-scope-per-call-01M69065/
├── plan.md              # This file
├── research.md          # Discovery evidence (already written)
├── data-model.md        # Phase 1: the scoped catalog and lazy lineage shapes
├── quickstart.md        # Phase 1: how to measure the read set
├── contracts/           # Phase 1: the scoped-loader contract and the census invariant
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/charter/activation/catalog.py             # domain scope on load_offering_catalog
src/charter/activation/resolver.py            # resolve_project_governance declares its scope
src/charter/activation/interview.py           # default_interview declares its scope
src/charter/offering/agent_profiles/repository.py  # lazy lineage graph
tests/charter/test_charter_render_scope_6462.py    # census guards (new)
tests/charter/activation/test_offering_catalog_scope_6462.py  # loader scope unit tests (new)
docs/changelog/CHANGELOG.md                   # [Unreleased] entry
```

**Structure Decision**: single project — the change lives in the existing `src/charter`
bounded context and its existing `tests/charter` suites; no new package, no new module
namespace, no CLI surface added.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

### IC-01 — Scoped catalog load

- **Purpose**: Let a caller name the built-in domains it reads so a persona render stops parsing the five domains its resolution never consults.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-006, NFR-001, NFR-003, C-004
- **Affected surfaces**: `src/charter/activation/catalog.py`, `src/charter/activation/resolver.py`, `src/charter/activation/interview.py`
- **Sequencing/depends-on**: none (first)
- **Risks**: the unscanned-domain semantics (empty set, absent from `domains_present`) must never be read as "domain not deployed" by a caller that did not scope it — guarded by default-all behaviour and by a test that pins each call site's scope to the fields it reads.

### IC-02 — Lazy lineage graph

- **Purpose**: Stop `AgentProfileRepository` from parsing 13 DRG fragments for callers that only read the profile map (`sentinel`, provenance, list).
- **Relevant requirements**: FR-004, NFR-002, C-002
- **Affected surfaces**: `src/charter/offering/agent_profiles/repository.py` (constructor, `_lineage_parent`, `_build_hierarchy_index`, channel reachability)
- **Sequencing/depends-on**: none (parallel to IC-01; different files)
- **Risks**: the `DRGLoadError` degrade-to-empty-graph contract must survive the move from constructor time to first-use; an explicit `drg=` argument must bypass the lazy path entirely.

### IC-03 — Census guards and evidence

- **Purpose**: Make the read set a pinned invariant with deterministic counts, and record the measurement in the changelog and traces so the next "CLI is slow" report lands on a named guard.
- **Relevant requirements**: FR-005, FR-007, NFR-001, NFR-002, NFR-004, SC-001..SC-004
- **Affected surfaces**: `tests/charter/test_charter_render_scope_6462.py`, `tests/charter/activation/test_offering_catalog_scope_6462.py`, `docs/changelog/CHANGELOG.md`, mission traces
- **Sequencing/depends-on**: IC-01, IC-02 (the guards must be red before them)
- **Risks**: the census spy must count production parses only (the `parse_shipped_yaml` seam and the repository loader), must be per-test isolated, and must not assert wall clock.

## Phases

- **Phase 0 (research)** — done in `research.md`: repro, what is already cached (#5526, #6858, #4211, #6638), decisions D-1..D-6.
- **Phase 1 (design)** — `data-model.md`, `contracts/`, `quickstart.md`; the two seams above.
- **Phase 2 (tasks)** — two work packages (IC-01+IC-03-red, IC-02+IC-03-green) with the census guard landing red-first in WP01 and staying green in WP02.
