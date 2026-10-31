# Implementation Plan: pack-skill body_path containment uses the shared primitive

**Branch**: `issue-6734-pack-skill-body-path-containment` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/pack-skill-body-path-containment-01M66FEC/spec.md`
**Input**: Mission specification from `kitty-specs/pack-skill-body-path-containment-01M66FEC/spec.md` (issue #6734)

## Summary

Route both pack-skill `body_path` read paths through the shared containment
primitive `charter.offering.drg.org_pack_config.resolve_relative_path_within_root`,
anchored at the declaring `*.skill.yaml` file's directory (today's anchor), and
delete the hand-rolled containment. `validation.py::_read_body` replaces its
`resolve().is_relative_to(base)` check with the primitive; a new shared helper
in the pack-skills package turns the primitive's `OrgPackSubdirEscapeError`
into a `PackSkillViolation` naming the escape, and
`repository.py::body_text` calls the same helper before reading, so an
escaping `body_path` (absolute, `..`, symlink-resolved outside) is refused
identically on both paths, fail-closed. Tests in
`tests/charter_offering/pack_skills/` prove the identical refusal plus a
positive control; docstrings that count or claim containment authorities are
corrected; a `[Unreleased]` changelog entry records the tightened `..` edge.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pydantic (PackSkill model), ruamel.yaml, pytest
**Storage**: N/A (filesystem paths only)
**Testing**: pytest, `tests/charter_offering/pack_skills/` (unit/fast tier);
`make test-fast` baseline plus the pack-skills test directory (owning
subsystem for `src/charter/offering/**` is `tests/charter/` +
`tests/charter_offering/`, but only the pack-skills package is touched — run
both directories' fast tiers)
**Target Platform**: cross-platform (Linux/macOS/Windows; the primitive already
refuses Windows absolute/UNC forms)
**Project Type**: single (CLI/library, `src/` layout)
**Performance Goals**: none new (path resolution only; the primitive does one
`resolve(strict=False)`)
**Constraints**: no new containment authority (NFR-001); no semantic change to
well-formed skills (NFR-002); diff-cover ≥90% on changed lines (NFR-003)
**Scale/Scope**: 2 source files, ~3 test files, 2-3 docstring sites, changelog

## Charter Check

- Single canonical authority (DIRECTIVE_044): PASS by construction — the
  mission *deletes* a hand-rolled authority and routes through the existing
  primitive.
- ATDD-first / red-first (DIRECTIVE_034): the repository-path escape tests are
  written first and fail on pristine `main` (proven during grounding).
- Smallest-viable-diff + Boy Scout inside the touched file set (RECONCILE_CHANGE_SCOPE_TENSIONS):
  the shared helper lives in `pack_skills/validation.py` (already the
  containment owner); no files added beyond tests and the changelog.
- Locality (DIRECTIVE_024): no changes outside `pack_skills/`, its tests, and
  docstring/changelog claim corrections.
- Terminology canon: PASS (Mission vocabulary; "containment" is the term the
  issue uses).

## Project Structure

### Documentation (this mission)

```
kitty-specs/pack-skill-body-path-containment-01M66FEC/
├── plan.md              # This file
├── research.md          # Discovery/grounding output
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/charter/offering/pack_skills/
├── validation.py        # _read_body routes through the primitive; shared
│                        #   body-path resolution helper (exported for the
│                        #   repository) raising PackSkillViolation
├── repository.py        # body_text calls the shared helper before reading
└── models.py            # untouched

tests/charter_offering/pack_skills/
├── conftest.py          # builders (prompt_skill/write_skill) — reused as-is
├── test_validation.py   # absolute/../symlink escapes refused via validate_pack_skill
└── test_repository.py   # identical refusals via body_text (red-first) +
                         #   TOCTOU symlink-swap case + positive control
```

**Structure Decision**: single-project layout; the shared helper lives in
`validation.py` (the package's pure-validation module, already imported by
`repository.py`) so both read paths import one function and no new module is
created.

## Implementation Concern Map

### IC-01 — Shared body-path resolution helper (validation path)

- **Purpose**: One function that anchors `skill.body_path` at the skill file's
  directory through `resolve_relative_path_within_root` and raises
  `PackSkillViolation` naming the escape; `_read_body` becomes its caller.
- **Relevant requirements**: FR-002, FR-003, C-001, C-002
- **Affected surfaces**: `src/charter/offering/pack_skills/validation.py`
- **Sequencing/depends-on**: none
- **Risks**: the primitive is stricter than the hand-roll at the `..` edge
  (accepted deliberately, recorded in spec edge cases and changelog); refusal
  message wording is pinned — the helper composes `skill {id!r}: body_path
  {body_path!r} escapes the skill directory ({reason})` so the existing
  `match="escapes"` assertions hold, and a contained-but-missing body keeps
  the separate `not found` finding via a post-containment `is_file()` check
  (the primitive never checks existence, `strict=False`). A raw resolve
  `ValueError` (embedded NUL byte) is also wrapped by the helper.

### IC-02 — Repository read path (body_text) containment

- **Purpose**: `PackSkillRepository.body_text` resolves the body through the
  IC-01 helper before reading, so an escaping record (post-load symlink swap,
  or a record that reached the catalog by another route) is refused
  fail-closed instead of reading outside the skill directory.
- **Relevant requirements**: FR-001, FR-003, C-001, C-002
- **Affected surfaces**: `src/charter/offering/pack_skills/repository.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: callers of `body_text` — verified: the sole production caller is
  `charter/activation/skill_preparation.py::_prepare_one`, and the raise
  propagates to `specify_cli/skills/catalog.py`'s stage-2 boundary, which
  classifies any exception as a controlled `PackSkillCatalogError` with
  `__cause__` preserved — a `PackSkillViolation` surfaces as a clean refusal,
  so NO `SkillPreparationError` conversion is added; the `_SkillSource`
  Protocol contract now permits a raise. `None` stays reserved for a
  non-prompt-form skill or an unknown id.

### IC-03 — Tests proving identical refusal on both paths

- **Purpose**: Red-first tests over the pre-existing entry points: for each
  escape kind (absolute, `..`, symlink swap after load), both
  `validate_pack_skill` and `body_text` refuse with `PackSkillViolation`;
  plus a positive control (contained body loads and reads unchanged).
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-003
- **Affected surfaces**: `tests/charter_offering/pack_skills/test_validation.py`,
  `tests/charter_offering/pack_skills/test_repository.py`
- **Sequencing/depends-on**: IC-01, IC-02 (written first, failing on `main`)
- **Risks**: the repository-path tests need a record with an escaping
  `body_path` in the catalog — load-time validation skips those files, so the
  tests use the TOCTOU symlink swap (public entry point) and a directly
  injected record for the absolute/`..` kinds, with a comment saying why;
  symlink tests carry the repo's `skipif(not hasattr(os, "symlink"))`
  convention (`tests/charter/test_symlink_loop_guards.py`); the Windows
  absolute-form refusals are platform-independent (pure `PureWindowsPath`
  checks in the primitive).

### IC-04 — Claim corrections and changelog

- **Purpose**: Correct containment-authority claims that the mission makes
  true or stale: the primitive's "single canonical escape-detection"
  docstring and the pack validator's hand-rolled-count ordinal
  ("a sixth hand-rolled") after `_read_body` is routed; keep (deliberately,
  recorded here) the one-line read-time clarification in
  `docs/development/how-to/create-a-pack-skill.md`; one `[Unreleased]`
  changelog entry with the before/after and the tightened `..` edge.
- **Relevant requirements**: FR-004, C-003
- **Affected surfaces**: `src/charter/offering/drg/org_pack_config.py`
  (docstring), `src/charter/offering/packs/pack_validator.py` (ordinal),
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: none material (docstring/changelog only); the merged mission
  spec `kitty-specs/doctor-body-path-containment-01M5ZD3C/` is a historical
  snapshot and is NOT edited.
