# Mission Specification: Nightly census re-pin and timeout headroom

**Mission Branch**: `issue-5367-nightly-census-and-timeout-headroom`
**Created**: 2026-09-29
**Status**: Draft
**Input**: User description: "#5367 #5378 — remove inert supply-chain toolguide inline references and re-pin the SC-011 census; re-derive ci-nightly timeout caps from measured wall-clock. One PR, draft first."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The SC-011 census reflects only real raw material (Priority: P1)

A maintainer running the nightly `interpreter-3.13-shard-4` / `specify-cli-out-of-matrix` legs sees
`test_governance_occurrences_and_files_match_sc011` pass, because the RAW_MATERIAL census counts only
genuine non-artefact file pointers. The three supply-chain toolguides no longer carry bare artefact ids
(`DIRECTIVE_051`, `supply-chain-install-safety`) as inline `references`, which the extractor silently
drops and which ADR `2026-07-26-1` forbids on new artefacts. The one legitimate new entry
(`common-docs` → `packs/built-in/assets/docs_structural_lint.config.yaml`) is re-pinned with provenance.

**Why this priority**: It is the only test red keeping the nightly from going green (#5367, #5258).

**Independent Test**: `pytest tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py` goes from
RED (26 ≠ 19) to GREEN; `spec-kitty doctrine regenerate-graph --check` stays fresh with no `*.graph.yaml`
edge change.

**Acceptance Scenarios**:

1. **Given** `main` at `f8ef65cf`, **When** the census test runs, **Then** it fails with `26 == 19` (red-first).
2. **Given** the toolguide `references` blocks are removed, **When** the inventory runs, **Then** RAW_MATERIAL = 20 and no DRG edge changes.
3. **Given** the census is re-pinned to 20 with `common-docs` in the RAW file set and RAW∩MIGRATE overlap, **When** the test runs, **Then** it passes.

### User Story 2 - Nightly legs have measured timeout headroom (Priority: P1)

A release operator sees each interpreter shard and the out-of-matrix leg conclude with its suite's real verdict
(green or an honest `failure`) instead of `cancelled`, because each `timeout-minutes` is re-derived as `ceil((max observed suite step + 0:30 measured job overhead) × 1.5)`
over the five measured runs (36300726806, 36393904544, 36482214935, 36517786727, 36553997695) rather than a
single fast sample.

**Why this priority**: A `cancelled` leg is not green, so the release gate stays shut (#5378) even after US1. A raised cap turns `cancelled` into the suite's real verdict; it does not by itself make a red suite green.

**Independent Test**: parse `ci-nightly.yml` and assert each re-derived leg carries a structured `# headroom:` comment
and its `timeout-minutes` ≥ `ceil((max + 0:30) × 1.5)` of that comment's value (the workflow stays the single authority); `test_interpreter_shard_coverage.py` / `test_module_shard_registry.py`
stay green.

**Acceptance Scenarios**:

1. **Given** the committed caps, **When** compared with the measured maxima, **Then** shard 2 (20 < 31) and out-of-matrix (45 < 69) fail the 1.5× rule (red-first).
2. **Given** the re-derived caps, **When** the workflow-shape test runs, **Then** every capped leg satisfies the rule and the derivation is recorded next to each cap.

### Edge Cases

- A leg whose measured max × 1.5 is below its current cap keeps its current cap (never tighten on this evidence).
- The shard roster/coverage gates key on shard identity, not caps, and must not move.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Drop inert toolguide references | As a doctrine maintainer, I want the java/javascript/python supply-chain toolguides to carry no inline bare-id `references` so that relationships live only in DRG edges (ADR 2026-07-26-1). | High | Open | build | no |
| FR-002 | Re-pin SC-011 census with provenance | As a maintainer, I want the RAW_MATERIAL census re-pinned 19 → 20 (adding `common-docs`) with a provenance note naming `3e09226f`/#5324 so that the pin tracks real raw material. | High | Open | build | no |
| FR-003 | Re-derive nightly caps | As a release operator, I want each `interpreter-matrix-shard-<N>` and the `specify-cli-out-of-matrix` leg's `timeout-minutes` set to `ceil((max observed suite step + 0:30 job overhead) × 1.5)` (never lowered) with the derivation recorded in the workflow so that runner variance cannot cancel a finished suite. | High | Open | build | no |
| FR-004 | Pin the headroom rule | As a CI maintainer, I want each re-derived cap to carry a structured `# headroom:` comment (measured max, runs, formula) in `ci-nightly.yml` and a workflow-only shape test asserting cap ≥ formula(comment) so that the workflow stays the single authority and a tightening below 1.5× is caught. | Medium | Open | build | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | DRG unchanged | Removing the toolguide references changes zero `*.graph.yaml` edges (only `pack-manifest.yaml` hashes). | Reliability | High | Open |
| NFR-002 | Targeted tests only | Only targeted tests and the named architectural gate files run locally (NO_FULL_HEAVY_SUITES_IN_MISSION). | Performance | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No retry-to-green | Tune budgets from measurements; never add retries or skip tests. | Technical | High | Open |
| C-002 | No re-shard | Shard boundaries (count-balanced roster) are out of scope; splitting the out-of-matrix leg and a conclusion-keyed "budget overrun" escalation are follow-ups for the operator. | Technical | Medium | Open |
| C-003 | Hands off in-flight slices | Do not touch S4/S6/S8/#5328/slice-10 surfaces. | Business | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_governance_occurrences_and_files_match_sc011` passes locally on 3.11 (was RED 26 ≠ 19).
- **SC-002**: `regenerate-graph --check` is fresh; the diff touches no `*.graph.yaml`.
- **SC-003**: Shard 2 headroom goes from −0:33 (job 20:33 vs cap 20) to ≥ +10 min; out-of-matrix from −0:25 (45:25 vs 45) to ≥ +23 min. Both inputs are censored lower bounds (the jobs were cancelled at their caps); the first post-merge nightly must confirm out-of-matrix finishes under 69 min.
- **SC-004**: `test_interpreter_shard_coverage.py`, `test_module_shard_registry.py`, `tests/ci/test_nightly_exit_code_honesty.py`, `ruff check`, `ruff format --check` green.
