# Mission Specification: Reduce charter activate/deactivate write latency

**Mission Branch**: `kitty/mission-charter-write-roundtrip-latency-01M68ZVK`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "Issue spec-kitty/spec-kitty#6506 — charter activate/deactivate take 9-15 s on this repository, far over budget. Measure where the time goes, fix the cause, add a repository-scale timing test, and either reach the 2 s charter budget or record a justified budget for repositories of this size."

**Guidance recorded from the operator brief**: scale the mission honestly (this is a small issue — a tight mission beats a bloated one); fix the cause, not the budget; never weaken a gate; the operator merges.

## Grounding (measured before any code change)

Reproduced on `main` at `dfe9efb0e8` against a scratch git project holding a copy of **this repository's own `.kittify/`** (165 KB / 1,937-line `charter.yaml`, 264 catalog references), warm second run each:

| Command | Observed |
|---|---|
| `spec-kitty charter deactivate tactic analysis-extract-before-interpret` | 17.3 s |
| `spec-kitty charter activate tactic analysis-extract-before-interpret` | 17.9 s |
| `spec-kitty charter list` (pure read, the floor) | 2.6 s |

Wall-clock attribution of the 19.1 s instrumented `deactivate` run:

| Cost centre | Time | Share |
|---|---|---|
| Compiled-charter refresh → owned-section prepare ×2 → document render ×2 | 8.6 s | 45 % |
| … of which the whole-document equality checks (two per render) | 3.4 s | 18 % |
| Catalog recompile (reference building) | 2.8 s | 15 % |
| Preserved-timestamp decision (a third full read, for one scalar) | 1.2 s | 6 % |
| CLI start-up + the command's own activation write | 4.2 s | 22 % |

The dominant cost is that the governed-document round-trip writer re-parses and re-emits the **whole** document about ten times per owned-section write, and one compiled-charter refresh runs **two** such writes back to back (one per derived section). Each document render makes two whole-document equality checks that cost ~1.2 s each, because the equality test serialises the entire value and re-parses it. This is not a fixture-scale artefact: the existing fixture-scale timing test (`test_deactivate_cli_timing.py`) deliberately asserts no absolute budget, and its own docstring already names "the repository-scale latency" as "the pre-existing gap #6506".

**Budget reality check.** The charter's `< 2 s` CLI budget is measured against a *typical* project. On a repository this size a **pure read** already costs 2.6 s, so 2 s for a command that also recompiles the catalog and rewrites the compiled charter is arithmetically unreachable without re-architecting the compiler. This mission therefore fixes the cause and records a justified, measured budget for repositories of this size.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A contributor activates or deactivates doctrine without a coffee break (Priority: P1)

A maintainer working in a large Spec Kitty project (this repository's own `.kittify/`) runs `spec-kitty charter activate directive <id>` or `charter deactivate directive <id>`. The command currently takes 9-18 s, dominated by the compiled-charter write path. After the change the command performs the minimum number of whole-document round trips and takes materially less time on the same machine, with byte-identical `charter.yaml` output.

**Why this priority**: This is the reported defect and the whole point of the issue. Every other story exists to prove or protect it.

**Independent Test**: Run both commands against a scratch project seeded with a copy of this repository's `.kittify/`, interleaved with the same commands from a pristine `main` checkout on the same machine, and compare medians. Independently: count whole-document round trips through the writer's public entry point.

**Acceptance Scenarios**:

1. **Given** a project whose `charter.yaml` is this repository's own (165 KB, 264 references), **When** `charter deactivate <kind> <id>` runs, **Then** the command completes with the same exit code, the same console output, and a byte-identical `charter.yaml` except for the intended section change.
2. **Given** the same project, **When** `charter activate <kind> <id>` runs, **Then** the median wall time is at most half of the pre-change median measured interleaved on the same machine in the same run.
3. **Given** the same project, **When** either command runs, **Then** the compiled-charter writer parses the whole `charter.yaml` at most twice (down from ten).

---

### User Story 2 - The maintenance team can see, and keep, the improvement (Priority: P2)

A future change reintroduces a whole-document round trip into the charter write path. A test that does not depend on machine speed fails on the pull request, and a repository-scale timing measure records the read floor next to the write cost so the two can never be confused again.

**Why this priority**: The regression is what makes the fix durable. Without it the defect returns the next time someone touches the writer. It is not P1 because the fix itself delivers the user value.

**Independent Test**: Revert one part of the fix and confirm the new test fails; run the new repository-scale timing test on a machine under heavy concurrent load and confirm it stays green.

**Acceptance Scenarios**:

1. **Given** the new round-trip-count test, **When** the two-write `write_compiled_charter` is restored, **Then** the test fails and names the extra cycle.
2. **Given** the new repository-scale timing test, **When** it runs on a shared machine with unrelated load, **Then** it asserts a runner-relative ratio (never absolute seconds) and stays green, per ADR `2026-10-05-2`.

---

### User Story 3 - A maintainer can find the budget for a large repository (Priority: P3)

Someone asks "why does `charter activate` take 9 s here when the charter says 2 s?". They find a recorded decision: the measured read floor, the measured write cost, the ratio between them, and what would have to change to reach 2 s.

**Why this priority**: The issue explicitly allows "record a justified budget for repositories of this size" as an alternative to 2 s. It is P3 because the decision only matters once the fix has landed and someone re-measures.

**Independent Test**: Read the recorded decision document and check that every number in it can be re-derived from the committed test output.

**Acceptance Scenarios**:

1. **Given** the recorded budget, **When** an engineer re-runs the committed repository-scale timing test, **Then** the measured floor, write cost and ratio match the recorded figures within the recorded tolerance.

---

### Edge Cases

- **Nothing to write.** An activate/deactivate that changes nothing must still not rewrite the file: the writer returns the original bytes and `apply_yaml_write` reports no change (existing `changed` contract). The one-write merge must not turn a no-op into a mtime churn.
- **A section is absent from the document.** Adding `catalog` or `metadata` to a document that lacks one must still append it in the same position and formatting as the two-write path did.
- **A key is removed.** `prepare_charter_yaml_section(..., remove=...)` must keep working for the `activation` section after the sections are merged; the removal path and the write path must not be able to disagree about which keys are owned.
- **Opaque tagged scalars and aliases.** The cheap equality must return exactly what the dump-and-reparse equality returned for tagged scalars, anchors and aliases; the "Cannot preserve YAML aliases or section boundaries" guard must not weaken.
- **A malformed or non-mapping document.** Existing `ValueError` refusals must be raised at the same point, before any write.
- **The file changes between read and write.** The `precondition_changed` receipt contract must be unaffected by doing one cycle instead of two.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One write cycle per compiled-charter refresh | As a maintainer, I want the compiled charter's derived sections refreshed in a single prepared write, so that one command does not load, render and re-verify the whole governed document once per derived section. | High | Open | [build] | no |
| FR-002 | Cheap document equality with unchanged verdicts | As a maintainer, I want the document-equality check to decide by comparing the two documents' contents and to round-trip only the parts that actually differ, so that comparing two large documents stops dominating the command while every verdict the writer depends on stays the same. | High | Open | [ratchet] | no |
| FR-003 | Decide the preserved timestamp from the document being written | As a maintainer, I want the "has the compiled content actually changed?" decision taken from the same document read that produces the write, so that a recompile with nothing to change still does not restamp, and one less full read is paid. | Medium | Open | [build] | no |
| FR-004 | A repository-scale, load-independent regression test | As a member of the maintenance team, I want a test that pins how many times one command reads and re-emits the whole governed document and that fails when a redundant cycle is reintroduced, so that this class of regression cannot land silently. | High | Open | [build] | no |
| FR-005 | A repository-scale timing measure with no absolute budget | As a member of the maintenance team, I want a timing test at this repository's scale that compares the command against a floor measured in the same run, so that it never false-reds on a shared runner and never encodes a fixed number of seconds. | High | Open | [build] | no |
| FR-006 | Record the justified budget for repositories of this size | As a maintainer, I want the read floor, the post-fix write cost and the ratio between them recorded as a decision, so that the charter's 2 s budget can be discussed with numbers instead of re-measured from scratch. | Medium | Open | [build] | no |
| FR-007 | Byte-identical output preserved | As a maintainer, I want the document written by the single-cycle path to be byte-identical to what the previous path wrote for the same change, so that the optimization cannot silently reformat, reorder or drop part of a governed document. | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Command latency halves at repository scale | On a scratch project seeded from this repository's own `.kittify/`, the interleaved median wall time of `charter activate` and of `charter deactivate` is at most 0.6× their pre-change medians, both measured in the same run on the same machine. | Performance | High | Open |
| NFR-002 | Whole-document round-trip budget | One compiled-charter refresh makes at most 6 whole-document round trips of the governed charter (from 18), and this is counted structurally in a test rather than timed. | Performance | High | Open |
| NFR-003 | Equality verdicts are unchanged | For every document pair in a committed corpus (this repository's own charter, the shipped doctrine pack documents, and synthetic tagged, anchored and aliased documents), the new equality returns exactly the verdict of the previous implementation. | Correctness | High | Open |
| NFR-004 | No wall-clock limit in any test | No test or constant added by this mission asserts an absolute number of seconds; every timing assertion goes through the repository's shared performance helper. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single write authority (INV-9) | Every writer of the governed document keeps going through the one load → mutate-owned-section → round-trip-save helper; this mission must not add a second writer, and no caller may mutate a section it does not own. | Technical | High | Open |
| C-002 | Layer rule (INV-7) | The shared document-write helper keeps its layer rule: it must not import the CLI package. | Technical | High | Open |
| C-003 | No absolute performance gate | Timings follow the repository's accepted decision that repository-scale performance tests assert runner-relative ratios with all limits in one shared helper. | Technical | High | Open |
| C-004 | Blast radius | Changes stay inside the governed-document write path, the compiler's write call site, and their tests. No change to the compiler's reference-building logic, to the charter's stated 2 s budget, or to any CI gate. | Technical | High | Open |

### Key Entities

- **`charter.yaml`**: the governed compiled charter. A round-trip (comment- and formatting-preserving) YAML document with six top-level keys, of which `catalog` and `metadata` are *derived* (written by the compiler) and `governance`, `directives`, `overrides` and the flat activation keys are *authored* (byte-preserved).
- **Owned section**: a top-level key a caller is allowed to replace: `governance`, `directives`, `catalog`, `metadata`, `overrides`, and the `activation` pseudo-section (a set of flat root keys).
- **Prepared write**: the exact desired bytes plus the observed inputs and a receipt that refuses a write whose inputs changed since preparation. The unit that makes "one cycle instead of two" safe.
- **Whole-document round trip**: one parse or one emit of the entire `charter.yaml`. The quantity this mission minimizes and pins.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Activating and deactivating doctrine each take at most 0.6× their previous wall time on a project the size of this repository, measured against the previous behaviour in the same run on the same machine — [build] · no-op passable: no
- **SC-002**: One compiled-charter refresh makes at most 6 whole-document round trips of the governed charter, down from 18, counted structurally in a committed test — [build] · no-op passable: no
- **SC-003**: The governed document's bytes are unchanged by the optimization: the single-cycle path produces the same bytes as the previous path for the same change, across a corpus of documents — [ratchet] · no-op passable: no
- **SC-004**: The equality check returns the previous implementation's verdict on every pair in the committed corpus, so no alias or tag guard becomes either weaker or spuriously stricter — [ratchet] · no-op passable: no
- **SC-005**: A recorded decision states the measured read floor, the post-fix write cost and their ratio, and no test asserts an absolute seconds budget for this path — [build] · no-op passable: no
