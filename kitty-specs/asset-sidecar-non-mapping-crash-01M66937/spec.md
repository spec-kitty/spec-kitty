# Mission Specification: Org asset sidecar with non-mapping YAML no longer crashes repository load

**Mission Branch**: `issue-6735-asset-sidecar-non-mapping-crash`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6735, plus operator guidance: fix in
the base loader so a non-mapping document is treated as malformed and skipped with
the usual warning; add a test per repository kind; never merge — a green PR flipped
to ready for review is the terminal state.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Org overlay with a malformed sidecar still loads (Priority: P1)

An operator has an org overlay directory containing an `*.asset.yaml` (or any other
kind's overlay file) whose YAML top level is a list or scalar (for example `- a`).
Today `AssetRepository(org_dirs=[...])` — and every other
`BaseArtifactRepository` consumer — raises
`AttributeError: 'list' object has no attribute 'get'`, which aborts the whole
repository load. In `doctor charter-packs` this makes the org asset containment
check fail closed and hides every other named escape (#6735).

**Why this priority**: this is the reported crash; without it the mission has no
deliverable.

**Independent Test**: construct each repository kind with an org overlay directory
containing one non-mapping sidecar; the repository must construct without raising,
emit the usual `Skipping invalid org <kind> <file>: <reason>` `UserWarning`, and
still load every valid artifact.

**Acceptance Scenarios**:

1. **Given** an org dir with `- a` in `bad.asset.yaml` and a valid second sidecar,
   **When** `AssetRepository(built_in_dir, org_dirs=[org])` is constructed,
   **Then** construction succeeds, the invalid file is skipped with a
   `Skipping invalid …` `UserWarning`, and the valid artifact loads.
2. **Given** the same fixture for each other repository kind sharing
   `BaseArtifactRepository`, **When** that repository is constructed,
   **Then** the same skip-with-warning behavior holds (no `AttributeError`).
3. **Given** a project-layer overlay with a non-mapping document, **When** the
   repository is constructed, **Then** it is skipped the same way (the org and
   project layers share `_apply_overlay_layer`).

---

### User Story 2 - Built-in tier non-mapping document is skipped, not crashed (Priority: P2)

A shipped/built-in YAML file whose top level is not a mapping currently crashes
the built-in load for kinds whose `_pre_validate` does `data.get(...)`
(directives, tactics, toolguides, paradigms, styleguides, procedures), because the
`_pre_validate` hook runs before Pydantic can reject the document. The base loader
should treat a non-mapping document as malformed in **both** tiers.

**Why this priority**: same defect class, same one-line seam; fixing only the
overlay tier would leave the built-in tier crashable and the semantics split.

**Independent Test**: construct `DirectiveRepository` with a built-in dir whose
only file is a top-level list; construction must succeed with the
`Skipping invalid built-in …` warning.

**Acceptance Scenarios**:

1. **Given** a built-in dir with one non-mapping YAML file, **When** a repository
   whose `_pre_validate` reads `data` is constructed, **Then** the file is skipped
   with the usual `Skipping invalid built-in <kind> <file>: <reason>` warning and
   no exception escapes the loader.

### Edge Cases

- Empty file (`yaml.load` → `None`): already returns early today; behavior
  unchanged (an empty file is absence, not malformed).
- Scalar document (string, int, bool) and sequence document: both are non-mapping
  and must be skipped identically.
- The skip warning must keep the pinned
  `Skipping invalid <layer> <kind> <file>: <reason>` shape —
  `_charter_pack_collect` parses that fixed shape to build structured skip
  diagnostics.
- Existing malformed-sidecar skips (YAML syntax error, Pydantic `ValidationError`,
  `OSError`, missing `id`) must be byte-for-byte unchanged in behavior.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Overlay non-mapping skip | As an operator with org/project overlays, I want a sidecar whose YAML document is not a mapping to be skipped with the usual warning so the repository load completes. | High | Open | [build] | no — the pre-fix main crashes with `AttributeError` on this exact fixture |
| FR-002 | Built-in non-mapping skip | As a Spec Kitty maintainer, I want a non-mapping built-in file to be skipped before `_pre_validate` runs so no kind's pre-validation hook can crash the built-in load. | High | Open | [build] | no — `DirectiveRepository` with a list built-in file crashes on pre-fix main |
| FR-003 | Existing malformed-sidecar behavior pinned | As an operator, I want the existing skip semantics for invalid YAML, schema-invalid documents, unreadable files and missing `id` to stay unchanged so no consumer's diagnostics drift. | High | Open | [ratchet] | no — pinned by the existing base-layer tests on the same fixtures |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Single fix site | The non-mapping guard lives once in `src/charter/offering/base.py` (the base loader), not repeated per repository kind; no new public API or import from `specify_cli`. | Maintainability | High | Open |
| NFR-002 | Warning shape stability | The new skip warning matches the pinned `Skipping invalid <layer> <kind> <file>: <reason>` shape consumed by `_charter_pack_collect`; the existing pattern test stays green. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Red-first | The defect gets a failing test through the pre-existing entry point (repository construction with `org_dirs`) before the fix lands. | Process | High | Open |
| C-002 | Operator merges | The mission ends at a green draft PR flipped to ready for review with `ready-for-squad`; never merge, never push `main`. | Process | High | Open |
| C-003 | Proportionate squad | Small defect fix: a couple of reviewers per round, not the full adversarial treatment. | Process | Medium | Open |

### Key Entities

- **`BaseArtifactRepository[T]`**: the three-source loader (built-in rglob → org
  overlay → project overlay) every offering repository kind shares; owns the
  skip-with-warning envelope for malformed files.
- **Overlay sidecar**: a YAML file in an org (or project) directory matching the
  kind's glob (e.g. `*.asset.yaml`), parsed raw before Pydantic validation.
- **Repository kinds**: the `BaseArtifactRepository` subclasses — asset,
  directive, tactic, toolguide, glossary pack, pack skill, styleguide, paradigm,
  procedure, mission step contract, mission type profile.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: the issue's reproduction (an org overlay whose only sidecar is a
  top-level list, against `AssetRepository`) constructs without raising and emits
  one `Skipping invalid …` `UserWarning` — [build] · no-op passable: no
- **SC-002**: every repository kind sharing `BaseArtifactRepository` has a
  regression test that goes red on pre-fix main and green after the fix — [build] ·
  no-op passable: no
- **SC-003**: the existing malformed-sidecar tests in
  `tests/charter_offering/test_base_org_layer.py` pass unchanged — [ratchet] ·
  no-op passable: no
