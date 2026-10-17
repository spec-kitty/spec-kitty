# Mission Specification: One meaning for an unclassified mission artifact

**Mission Branch**: `fix/artifact-none-single-meaning`
**Created**: 2026-10-16
**Status**: Draft
**Input**: User description: "artifact-none-single-meaning — Give every unclassified mission artifact one meaning for the kind classifier (#5697)"

## Context

`mission_runtime.kind_for_mission_file(path)` classifies a `kitty-specs/<slug>/…`
path to a `MissionArtifactKind` or returns `None`. Today different consumers
disagree on what `None` means:

- The **write side** (commit router, `coherence.is_coord_residue_churn`) treats
  an unclassified path as **PRIMARY** — it lives with the mission on the target
  branch, and the product literally cannot write a `None`-kind path onto the
  coordination surface (`_translate_to_owning_surface` raises `PATH_UNROUTABLE`).
- The **squash projection** (`bookkeeping_projection._post_checkpoint_mission_paths`)
  treats a `None` path (that is not `meta.json`) as **coordination bookkeeping**,
  projects it, and the content proof then refuses deterministically on
  byte-identical content.
- The **workflow commit partition** (`workflow._partition_paths_by_primary_kind`)
  sends a `None` path to the coordination bucket.

That disagreement is the root cause of #5552 and of the squash-consolidate
refuse verified on `main` on 2026-10-15 (four byte-identical `research/*.py`
evidence scripts were the only paths projected because their kind was `None`,
and all four failed the no-driver content replay). A single canonical authority
for "is this a coordination record" already exists
(`coordination.coherence.is_coordination_kind_file`, `None → not-coord`) and is
shared by three other consumers; the two dissenters re-derive the opposite answer
locally.

This mission (a) routes both dissenters through that one authority so `None`
means exactly one thing everywhere, and (b) classifies every mission file the
built-in mission types legitimately write that is still unclassified, so the
taxonomy is honest rather than relying on the `None` fallback.

Out of scope: the distinct #5847 window (the coordination branch is also the
lane-merge branch); per the issue triage, fixing one does not fully fix the
other. Four paths stay deliberately unclassified: `lint-report.json` (lives under
`.kittify/`), `docs/**` (project-root repo content), `answers.yaml` (lives under
`.kittify/charter/interview/`), and `mission-events.jsonl` (deliberately not a
kind, #5669 keep-local real-dirt).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consolidation stops falsely refusing byte-identical mission files (Priority: P1)

An operator finishes a mission whose work committed evidence files under
`kitty-specs/<slug>/research/` (for example read-only code-grounding scripts).
The files are byte-identical on the target and the lanes. The operator runs
`spec-kitty consolidate`.

**Why this priority**: This is the reported defect (#5697 / #5552 class). A
deterministic squash refuse on content that is objectively correct blocks a
legitimate merge and forces a manual workaround; it erodes trust in the merge
gate.

**Independent Test**: On a git fixture shaped like the verified refused run
(unclassified `research/**` files byte-identical between coord and target, absent
from the checkpoint), the squash projection selects nothing to project for those
paths and `consolidate` completes without a refuse. Fully testable through the
pre-existing `_post_checkpoint_mission_paths` / `projected_content_matches_target`
entry points.

**Acceptance Scenarios**:

1. **Given** a mission with byte-identical unclassified `research/*.py` files on
   coord and target, **When** the squash projection computes its post-checkpoint
   path set, **Then** those files are not in the projected set and the content
   proof passes.
2. **Given** the same fixture with a genuine coordination file
   (`traces/approach.md`), **When** the projection runs, **Then** the tracer file
   is still projected and still passes the proof (coordination carry-forward is
   preserved).

---

### User Story 2 - A new, still-unclassified mission file routes consistently (Priority: P1)

A maintainer introduces a new kind of mission file that the classifier does not
yet recognise.

**Why this priority**: #5697 is the second instance of this class after #5552.
If `None` keeps meaning two different things, the next unclassified file silently
re-triggers the same refuse. Giving `None` one meaning retires the class, not one
instance.

**Independent Test**: For a path that classifies to `None`, the write partition
routes it PRIMARY and the squash projection does not project it — the same answer
on both sides — with no new classifier entry required.

**Acceptance Scenarios**:

1. **Given** a mission-relative path that classifies to `None`, **When** the
   workflow commit partition splits staged paths, **Then** the path is
   primary-bound (matching the write-side authority), and **When** the squash
   projection runs, **Then** the path is not projected.

---

### User Story 3 - Every mission file is honestly classified (Priority: P2)

An operator runs any of the four built-in mission types; each file those types
write under `kitty-specs/<slug>/` resolves to a real `MissionArtifactKind` in the
correct partition.

**Why this priority**: Honest classification makes write placement, the accept
gate, and the projection agree by construction and removes silent reliance on the
`None` fallback. It is the durable follow-through to Story 1/2 but not itself the
refuse fix.

**Independent Test**: A parametrized classification test asserts the expected kind
and PRIMARY partition for each newly classified path, and asserts the four
deliberately-excluded paths still classify to `None`.

**Acceptance Scenarios**:

1. **Given** each newly classified path (`research/**`, the research deliverables,
   `gap-analysis.md`, `audit-report.md`, `occurrence_map.yaml`, `goals.md`,
   `release.md`, `meta.json`), **When** `kind_for_mission_file` classifies it,
   **Then** it returns the assigned kind and `is_primary_artifact_kind` is true.
2. **Given** a deliberately-excluded path (`lint-report.json`, `docs/x.md`,
   `answers.yaml`, `mission-events.jsonl`), **When** it is classified, **Then** it
   still returns `None`.

### Edge Cases

- A pathological misplacement (`research/meta.json`, `research/mission-events.jsonl`)
  is classified RESEARCH by the directory-anchored rule; this is accepted as
  low-harm because the dirty-state gates already treat those as real dirt
  independently of the kind classifier (no filename-exclusion leg is added).
- A path belonging to another mission (wrong `mission_slug`) continues to classify
  to `None` — the slug filter is unchanged.
- The two status byte-sets (`status.events.jsonl` / `status.json`) and the two gate
  matrices (`issue-matrix` / `acceptance-matrix`) keep their existing preservation
  paths and are unaffected by the projection change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Projection uses the one coord authority | As an operator, I want the squash projection to project a mission path only when it is a coordination-partition record (via `is_coordination_kind_file`) so that an unclassified (`None`) path is never carried as coordination bookkeeping. | High | Open | [build] | no — paired on one fixture with a `traces/` coord file that MUST still project |
| FR-002 | Workflow partition uses the one coord authority | As an operator, I want `_partition_paths_by_primary_kind` to route an unclassified path to primary-bound (via the same authority) so that the write partition agrees with the write-side placement. | High | Open | [build] | no — paired with `status.events.jsonl` which MUST stay coord-bound |
| FR-003 | research/ subtree classified | As an operator, I want the whole `research/` subtree classified RESEARCH (PRIMARY, directory-anchored) so that research evidence files resolve to a real primary kind. | High | Open | [build] | no |
| FR-004 | Research deliverables classified | As an operator, I want `findings.md`, `report.md`, `methodology.md`, `synthesis.md`, `literature-review.md` classified to a new PRIMARY `RESEARCH_OUTPUT` kind, distinct from the sw-dev `research.md` note. | Medium | Open | [build] | no |
| FR-005 | Analysis reports classified | As an operator, I want `gap-analysis.md` and `audit-report.md` classified ANALYSIS_REPORT (PRIMARY) so that documentation/research analysis outputs resolve honestly. | Medium | Open | [build] | no |
| FR-006 | occurrence_map classified | As an operator, I want `occurrence_map.yaml` classified to a new PRIMARY `OCCURRENCE_MAP` kind so that the bulk-edit classification map resolves to the mission's own surface. | Medium | Open | [build] | no |
| FR-007 | goals classified | As an operator, I want `goals.md` classified to a new PRIMARY `MISSION_GOALS` kind so that the plan mission's goals resolve honestly (not by borrowing SPEC). | Medium | Open | [build] | no |
| FR-008 | release record classified | As an operator, I want `release.md` classified to a new PRIMARY `RELEASE_RECORD` kind so that the documentation publish handoff resolves honestly. | Medium | Open | [build] | no |
| FR-009 | meta.json classified | As an operator, I want the mission-root `meta.json` classified PRIMARY_METADATA so a path-only consumer (safe-commit by path, append-history) no longer gets `None`. | Medium | Open | [build] | no |
| FR-010 | Partition stays total and disjoint | As a maintainer, I want every new kind to land in exactly one partition frozenset (all PRIMARY) so that `assert_partition_invariant` (P-1) stays total and disjoint. | High | Open | [ratchet] | no — a new member omitted from a partition fails the invariant test |
| FR-011 | Excluded paths stay unclassified | As a maintainer, I want `lint-report.json`, `docs/**`, `answers.yaml`, and `mission-events.jsonl` to keep classifying to `None` so that non-mission-artifact paths are not swept in. | High | Open | [ratchet] | no — paired on the same test with a positively classified path |
| FR-012 | Squash consolidate no longer refuses the #5697 repro | As an operator, I want a squash consolidate carrying byte-identical unclassified `research/**` content to complete without a spurious refuse, exercised through the pre-existing consolidate projection entry points. | High | Open | [build] | no — the same fixture refuses before the fix (issue-pinned regression repro) |
| FR-013 | Inverse basename map stays honest | As a maintainer, I want `mission_file_basenames_for_kind` to return only the basenames truly mapped to each kind so that the inverse map does not lie after the new basename entries are added. | Medium | Open | [ratchet] | no — asserted against the concrete basename sets |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No change for already-classified paths | Every path already classified before this mission (spec.md, plan.md, tasks/**, traces/**, status pair, matrices, decisions/**, contracts/**, quickstart.md, …) returns a byte-identical kind after the change; the pre-existing classification tests pass unchanged. | Compatibility | High | Open |
| NFR-002 | One canonical authority, no local re-derivation | The meaning of an unclassified kind is derived from exactly one authority (`is_coordination_kind_file`); zero consumers re-derive a local `None → coord` branch. Verified by an architectural/AST check over the two former dissenters (0 residual local re-derivations). | Maintainability | High | Open |
| NFR-003 | Complexity ceiling | Every function touched or added stays at cyclomatic complexity ≤ 15 (Ruff C901 / Sonar S3776). | Maintainability | Medium | Open |
| NFR-004 | Coordination carry-forward preserved | The real coordination bookkeeping the projection must carry (`traces/**`, `decisions.events.jsonl`, `tasks/<wp>/review-cycle-*.md`) is still projected after the change; the projection's one selection-pinning regression assertion stays green. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | #5847 out of scope | Do not change the behaviour of the distinct #5847 window (coordination branch is also the lane-merge branch); this mission does not fold it. | Technical | High | Open |
| C-002 | Partition is PRIMARY for every classified file | Every file this mission classifies lands in the PRIMARY partition; none is added to `_PLACEMENT_ARTIFACT_KINDS`. | Technical | High | Open |
| C-003 | No suppressions | No new blanket `# noqa`, `# type: ignore`, or Sonar suppression is added to pass lint/type/quality gates; fix the code instead. | Technical | High | Open |
| C-004 | Red-first discipline | Each defect behaviour (FR-001, FR-002, FR-012) lands an issue-pinned `@pytest.mark.regression` repro that is RED through the pre-existing entry point before its fix, per ADR 2026-07-17-1. | Process | High | Open |
| C-005 | Canonical classifier source | All kind/partition changes are made in `src/mission_runtime/artifacts.py` (the single file→kind authority); no consumer hard-codes a parallel classification. | Technical | High | Open |

### Key Entities

- **MissionArtifactKind**: the enum of mission artifact categories; gains four new PRIMARY members (`RESEARCH_OUTPUT`, `OCCURRENCE_MAP`, `MISSION_GOALS`, `RELEASE_RECORD`).
- **Classifier maps**: `_MISSION_FILE_KIND_BY_BASENAME` (basename→kind) and `_COORD_RESIDUE_DIRS` (first-segment dir→kind) in `mission_runtime.artifacts`.
- **Partition frozensets**: `_PRIMARY_ARTIFACT_KINDS` / `_PLACEMENT_ARTIFACT_KINDS`, kept total and disjoint by `assert_partition_invariant` (P-1).
- **Coordination authority**: `coherence.is_coordination_kind_file` — the one predicate the projection and the workflow partition adopt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A squash consolidate of a mission carrying byte-identical unclassified `research/**` evidence files completes with no spurious refuse (the verified #5697 repro passes). — [build] · no-op passable: no
- **SC-002**: 100% of the files the four built-in mission types write under `kitty-specs/<slug>/` classify to a non-`None` kind, except exactly the four deliberately-excluded paths. — [build] · no-op passable: no
- **SC-003**: A path that classifies to `None` routes identically on both sides (primary-bound on the write partition, not projected by the squash projection) with no classifier entry added — one meaning for `None`. — [build] · no-op passable: no
- **SC-004**: Zero consumers retain a local `None → coordination` re-derivation; the only authority is `is_coordination_kind_file`. — [ratchet] · no-op passable: no
