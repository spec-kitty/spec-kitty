# Implementation Plan: Reduce charter activate/deactivate write latency

**Branch**: `issue-6506-charter-write-roundtrip-latency` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

## Summary

`spec-kitty charter activate` and `charter deactivate` take 17-18 s on a project the size of this repository, against a charter budget of `< 2 s` for "typical projects" (`#6506`). Measurement (see [research.md](./research.md)) puts 45 % of the command inside the single governed-document round-trip writer: one compiled-charter refresh performs **two** full load → render → prepare → apply cycles (one per derived section), and each render parses and re-emits the whole 165 KB `charter.yaml` roughly ten times, including two whole-document equality checks that cost ~1.2 s each because the equality test serialises the entire value and re-parses it.

The approach is to leave every invariant intact and remove the redundant work:

1. make the document-equality check cheap without changing a single verdict — compare contents structurally and fall back to the existing serialise-and-reparse comparison only for the leaves that genuinely differ;
2. refresh all derived sections of the compiled charter in one prepared write instead of one per section, deriving the preserved-timestamp decision from the same read;
3. pin the result with a structural round-trip count (exact, load-independent, runs on every PR) and a repository-scale ratio timing test that never encodes absolute seconds (per the repository's accepted performance-test decision);
4. record the justified budget for repositories of this size, because the 2 s target is unreachable here even for a pure read.

## Technical Context

**Language/Version**: Python 3.11 (pinned 3.11.15)
**Primary Dependencies**: `ruamel.yaml` (round-trip mode) for the governed YAML document; Typer/Click for the CLI surface; pytest for tests
**Storage**: files — the governed `charter.yaml` under `.kittify/charter/`, the activation ledger, the synthesis manifest
**Testing**: pytest; targeted packages only per the charter's `NO_FULL_HEAVY_SUITES_IN_MISSION`; timing tests marked `timing`/`performance` and kept off the PR-blocking path
**Target Platform**: Linux/macOS/Windows 10+ desktop/server CLI
**Project Type**: single Python package (`src/charter/`, `src/specify_cli/`)
**Performance Goals**: `charter activate`/`charter deactivate` at ≤ 0.6× their current median on a repository-scale project (measured 0.62); ≤ 6 whole-document round trips per compiled-charter refresh (from 18)
**Constraints**: no absolute seconds in any test; the governed document's bytes must be unchanged by the optimization; the writer must stay the single authority (INV-9); the shared helper must not import the CLI package (INV-7)
**Scale/Scope**: one module (`charter/activation/charter_yaml_io.py`), one call site (`charter/activation/compiler.py::write_compiled_charter`), their tests, one ADR and one changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|---|---|---|
| Single canonical authority | PASS | The change keeps one writer and one equality rule; it removes a second *pass*, not a second authority. `write_compiled_charter` remains the only compiled-charter writer; `charter_yaml_io` remains the only round-trip writer (INV-9). |
| Architectural alignment / layer rule | PASS | `charter/activation/charter_yaml_io.py` keeps its INV-7 rule (no `specify_cli` import). `tests/architectural/charter_activation_boundary_baseline.yaml` is unaffected. |
| Locality of change (DIRECTIVE_024) | PASS | Two production files, plus tests/ADR/changelog. The compiler's reference-building logic and the CLI command bodies are untouched. |
| ATDD-first / red-first (DIRECTIVE_034) | PASS | The count test is written first and observed to fail against `main` (10 round trips where it asserts ≤ 2), and the equality-equivalence corpus is written first against the old implementation. |
| Tests guard real behaviour (DIRECTIVE_041) | PASS | The two new tests pin a measured invariant and a behaviour-preserving refactor; neither asserts an implementation detail for its own sake. |
| No full heavy suites in mission | PASS | Targeted packages only: `tests/charter/activation/`, `tests/specify_cli/cli/commands/charter/`, `tests/architectural/`, the two new performance files. |
| No absolute performance gate | PASS | C-003: every timing assertion goes through `tests/_perf_helpers.py`; a new limit goes *into* that helper so `tests/architectural/test_perf_limit_authority.py` stays green. |
| Decision documentation (DIRECTIVE_003) | PASS | The justified budget is recorded as an ADR; the two reversals considered (drop the checks, relax the budget) are recorded with why they were rejected. |
| Pre-existing failure reporting | PASS | Any red in the mission's test surface that also reds on pristine `origin/main` is reproduced there, cited to its issue (#6798, #6801, #6816, #5927) and named in the PR's `## Deferred`. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-write-roundtrip-latency-01M68ZVK/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings (measurements, decisions)
├── spec.md              # Mission specification
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── tasks/               # Per-work-package task files (/spec-kitty.tasks)
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/charter/activation/
├── charter_yaml_io.py       # IC-01: the single round-trip writer (equality + multi-section prepare)
├── compiler.py              # IC-02: write_compiled_charter — one cycle per refresh
├── activation_ledger.py     # unchanged; consumes the same public helper
└── pack_manager.py          # unchanged; consumes the same public helper

tests/charter/activation/            # IC-01
tests/specify_cli/cli/commands/charter/  # IC-02 (existing ratio timing test lives here)
tests/performance/                   # IC-03 (count test + repository-scale ratio test)
tests/_perf_helpers.py               # IC-03 (the one limit authority)
docs/adr/4.x/                        # IC-04 (recorded budget)
docs/changelog/CHANGELOG.md          # IC-04
```

**Structure Decision**: single Python package. The production change is confined to
`src/charter/activation/` — the governed-document write path and its one compiled-charter
caller — because that is where the measured cost is and because both files are already the
declared single authorities for their concerns. Tests mirror that layout, plus
`tests/performance/` for the repository-scale measures (the tree where the repository already
keeps its performance tests) and `tests/_perf_helpers.py` for the one limit authority the
architectural guard requires.

## Complexity Tracking

No charter violations. The one deliberate complexity increase is the new optional
`sections_from_document` seam on the multi-section prepare, which exists so the preserved
timestamp is decided from the same read that produces the write instead of a second,
independently-racing read. The simpler alternative (two reads) was rejected because it leaves
a window where the file changes between the decision and the write, and because it pays a
300 ms full parse for one scalar.

## Implementation Concern Map

### IC-01 — Cheap, exact document equality and a single-pass section writer

- **Purpose**: Stop the round-trip writer from paying a full serialise-and-reparse comparison
  for a document it already holds, and let it apply several owned sections in one prepare
  cycle, without changing a single equality verdict or a single output byte.
- **Relevant requirements**: FR-002, FR-003, FR-007, NFR-002, NFR-003, C-001, C-002
- **Affected surfaces**: `src/charter/activation/charter_yaml_io.py`
  (`yaml_documents_equal`, `_yaml_value_events` usage, `prepare_charter_yaml_section`,
  a new `prepare_charter_yaml_sections`)
- **Sequencing/depends-on**: none
- **Risks**:
  - The equality fallback exists to handle opaque tagged round-trip keys and anchors. The new
    implementation must return **exactly** the old verdicts; a corpus test over shipped pack
    YAML plus synthetic tagged/anchored/aliased documents is the guard (NFR-003), and it is
    written before the change.
  - The final `yaml_documents_equal(decoded, document)` in `render_yaml_document` is the
    "Cannot preserve YAML aliases or section boundaries" guard. It stays, and stays exact.
  - `precondition_changed` receipts: the merged prepare must observe inputs once and still
    refuse a write whose inputs moved. Existing receipt tests must keep passing untouched.

### IC-02 — One write cycle per compiled-charter refresh

- **Purpose**: Make a compiled-charter refresh cost one document cycle regardless of how many
  derived sections the compiler owns, and decide the preserved timestamp from that same read.
- **Relevant requirements**: FR-001, FR-003, FR-007, NFR-001
- **Affected surfaces**: `src/charter/activation/compiler.py`
  (`write_compiled_charter`, `_preserved_generated_at`)
- **Sequencing/depends-on**: IC-01 (the merged prepare API)
- **Risks**:
  - Callers: `charter activate`/`deactivate` (through `recompile_catalog`) and
    `charter generate`. Both must keep identical output; `charter generate`'s tests are the
    second caller's guard.
  - The `provision_mission_type_activations` + `restamp_bundle_hash` tail must keep running
    after the charter write, in the same order, so the manifest hash stays in parity.
  - Bootstrap path (no existing `charter.yaml`) is untouched.

### IC-03 — Repository-scale regression tests with no absolute budget

- **Purpose**: Pin "one cycle, ≤ 2 whole-document round trips" so the redundancy cannot come
  back, and add a repository-scale timing measure that survives shared-runner variance.
- **Relevant requirements**: FR-004, FR-005, NFR-001, NFR-002, NFR-004, C-003
- **Affected surfaces**: `tests/performance/` (two new files), `tests/_perf_helpers.py`
  (one new limit constant)
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**:
  - The count test must count at a boundary that actually catches a redundant *parse*, not
    just a redundant call — otherwise a re-parse inside a single render slips past it.
  - The fixture is repository-scale (a copy of this repository's own `.kittify/`); it must be
    copied into `tmp_path` and never mutated in place, and the test must not depend on the
    checkout's absolute path.
  - `tests/architectural/test_performance_marker_guard.py` requires every `assert` in a
    `performance`-marked test to be a timing assertion through the shared helper;
    `tests/architectural/test_perf_limit_authority.py` requires limits to live only in
    `tests/_perf_helpers.py`.

### IC-04 — Record the justified budget

- **Purpose**: Give the next engineer the measured read floor, the post-fix write cost and the
  ratio, and state honestly what would have to change to reach the charter's 2 s.
- **Relevant requirements**: FR-006, SC-005
- **Affected surfaces**: `docs/adr/4.x/` (new ADR), `docs/changelog/CHANGELOG.md`,
  `docs/adr/index.md` + the ADR inventory (generated)
- **Sequencing/depends-on**: IC-02 (needs the post-fix numbers), IC-03 (needs the committed test that
  re-derives them)
- **Risks**: the ADR must record figures that the committed tests can re-derive; a figure that
  only exists in a throwaway profile would rot. The generated docs index / ADR inventory are
  repo-wide surfaces — regenerate only what this ADR needs and verify with the freshness check
  rather than trusting a full rebuild (other agents share this machine).

## Phase 0 — Research

Complete: [research.md](./research.md) records the reproduction, the wall-clock attribution,
the unit costs of each round-trip operation, six decisions with their evidence, and four open
questions. No `[NEEDS CLARIFICATION]` reached the spec.

## Phase 1 — Design

### The equality rule

`yaml_documents_equal(left, right)` becomes a depth-first comparison:

1. `left is right` → equal.
2. `left == right` → equal (unchanged first clause; it is what makes the no-op case free).
3. Both mappings with the same key set → compare the values pairwise.
4. Both sequences of the same length → compare element-wise.
5. Otherwise → the **existing** serialise-and-reparse event comparison, now applied to one
   small value instead of the whole document.

Step 5 keeps the exact old semantics for opaque tagged scalars, anchors and aliases; steps 3
and 4 are the reachability change. Ordering is *not* compared, matching the existing
`left == right` clause, which is also order-insensitive for mappings.

### The multi-section prepare

```
prepare_charter_yaml_sections(path, *, sections | sections_from_document, remove=()) -> PreparedYamlWrite
```

- exactly one of `sections` (a `{section: values}` mapping) or `sections_from_document`
  (a callable given the freshly loaded, not-yet-mutated document) is supplied;
- every section name is validated by the existing `_validate_section`, and `remove=` by the
  existing `_validate_removals` — one code path, not a parallel one;
- the input is observed once, the document is loaded once, all changes are applied, the
  document is rendered once, and one `prepare_yaml_write` returns the receipt-backed write;
- `prepare_charter_yaml_section` becomes a one-section call to it, so the existing eight call
  sites keep working unchanged;
- `update_charter_yaml_section` keeps its signature and delegates.

### The compiled-charter refresh

`write_compiled_charter` replaces its two `update_charter_yaml_section` calls with one
`prepare_charter_yaml_sections(path, sections_from_document=...)` whose callback computes
`preserved_generated_at` (catalog unchanged on disk → keep the stamp) and the metadata dict
from the document it is handed, returning `{"catalog": catalog, "metadata": metadata}`.

### Test design

| Requirement | Test | Shape |
|---|---|---|
| FR-002 / NFR-003 / SC-004 | equivalence corpus: the old event-only comparison vs the new one over this repository's own charter, the shipped pack YAML corpus, and synthetic tagged/anchor/alias documents | pure, fast, PR-blocking |
| FR-001 / FR-007 / SC-003 | byte identity: for a corpus of mutations, the single-cycle path writes exactly the bytes the two-cycle path wrote | pure, fast, PR-blocking |
| FR-004 / NFR-002 / SC-002 | round-trip count: instrument the document-parse boundary, run the real `charter activate` entry point on a repository-scale fixture, assert ≤ 2 whole-document parses; proved non-vacuous by re-running against the two-cycle implementation | structural, fast enough for PR |
| FR-005 / NFR-001 | repository-scale ratio: interleaved command median over a floor measured in the same run, limit held in `tests/_perf_helpers.py` | `timing` + `performance` marked; off the PR-blocking path |
| FR-006 / SC-005 | the ADR's figures are re-derivable from the ratio test's reported values | review + the recorded numbers |

### Entity / contract touchpoints

- **Owned section** — unchanged vocabulary; the merged prepare takes a mapping of them and
  nothing new becomes writable.
- **Prepared write** — unchanged dataclass and receipt; the merge reuses it, it does not fork it.
- **`charter.yaml`** — byte-identical output is the contract (FR-007).

## Phase 2 — Tasks

Decomposed by `/spec-kitty.tasks`; the concern map above is the input. Expected shape: IC-01
and IC-02 are one or two work packages (they share the file and the test corpus), IC-03 is one
or two (the count test depends on IC-02; the ratio test does not), IC-04 is one (docs/changelog,
depends on the measured result of IC-02).
