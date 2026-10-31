---
description: "Work package task list for pack-skill body_path containment"
---

# Work Packages: pack-skill body_path containment (issue #6734)

**Inputs**: Design documents from `kitty-specs/pack-skill-body-path-containment-01M66FEC/`
**Prerequisites**: plan.md (required), spec.md, research.md

**Tests**: Required — the mission is a defect fix; red-first tests are part of the deliverable (charter ATDD-First Discipline, DIRECTIVE_034).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are reference rows: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`

---

## Work Package WP01: Shared containment on both pack-skill read paths (Priority: P1) 🎯 MVP

**Goal**: Route `pack_skills/validation.py::_read_body` and `PackSkillRepository.body_text` through `resolve_relative_path_within_root` anchored at the skill file's directory, raising `PackSkillViolation` on an escape, with red-first tests proving absolute/`..`/symlink escapes are refused identically on both paths.
**Independent Test**: `uv run --frozen pytest tests/charter_offering/pack_skills/ -q` is green, including the new escape-refusal tests that fail on pristine `main`; `grep -rn "is_relative_to" src/charter/offering/pack_skills/` returns nothing.
**Prompt**: `tasks/WP01-shared-containment-both-read-paths.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, C-002

### Included Subtasks

T001 Red-first repository-path tests: escaping `body_path` (absolute, `..`, post-load symlink swap) refused by `body_text` with `PackSkillViolation` + positive control
T002 Red-first validation-path tests: absolute and symlink escapes refused by `validate_pack_skill` (the `..` case exists already); pin "not found" vs "escape" distinction
T003 Shared helper in `validation.py` resolving the body path through `resolve_relative_path_within_root`, raising `PackSkillViolation` naming the escape
T004 Rewire `_read_body` onto the helper (delete the hand-rolled `resolve().is_relative_to(base)`)
T005 Rewire `PackSkillRepository.body_text` onto the helper (fail-closed before reading)
T006 Run the owning test surface and the fast baseline; record commands + counts

### Implementation Notes

- Red-first: T001/T002 are written and run against pristine `main` before T003–T005; the repository-path tests must FAIL on `main` (proven during grounding).
- The repository-path tests need an escaping record in the catalog; load-time validation skips such files, so use the TOCTOU symlink swap (public entry point) and a directly injected record for the absolute/`..` kinds, each with a one-line comment saying why.
- Keep the refusal message continuous with today's ("escapes the skill directory"), appending the primitive's reason.
- `sub/../body.md` (string-level `..` that resolves back inside) becomes refused — deliberate, single-authority rule; record in the WP history note.

### Parallel Opportunities

- T001 and T002 can be authored in parallel; T003–T005 are sequential (helper first).

### Dependencies

- None (starting package).

### Risks & Mitigations

- The primitive is stricter at the `..` edge → covered by a dedicated test and the changelog entry (WP02).
- `body_text`'s only caller (`skill_preparation.py::_prepare_one`) sees `PackSkillViolation` instead of an outside read → fail-closed is intended; verify no existing test depends on the leak.

---

## Work Package WP02: Containment-authority claims and changelog (Priority: P2)

**Goal**: Correct the containment-authority claims the mission makes true or stale, and record the user-facing change (including the tightened `..` edge) in the changelog.
**Independent Test**: Docstrings in `org_pack_config.py` and `pack_validator.py` state the post-change truth; `docs/changelog/CHANGELOG.md` `[Unreleased]` carries the entry with `(#6734)`; `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py` passes.
**Prompt**: `tasks/WP02-claims-and-changelog.md`
**Requirement Refs**: FR-004, C-003

### Included Subtasks

T007 Correct the primitive's docstring claim in `org_pack_config.py` (now names the pack-skill read paths among its consumers)
T008 Verify/correct the pack validator's hand-rolled-count ordinal in `pack_validator.py` ("a sixth hand-rolled…" — the pack-skill hand-roll is gone)
T009 Clarify `docs/development/how-to/create-a-pack-skill.md`: enforcement also holds at read time (one line)
T010 Add the `[Unreleased]` changelog entry (bold impact-first lead with `(#6734)`, before/after, under 1,200 characters)

### Implementation Notes

- Do NOT edit `kitty-specs/doctor-body-path-containment-01M5ZD3C/` — historical immutable snapshot.
- Changelog format: `docs/changelog/CHANGELOG.md` under `[Unreleased]` (root `CHANGELOG.md` is a symlink).

### Parallel Opportunities

- None (small, sequential).

### Dependencies

- Depends on WP01 (the claims are only true once both read paths route through the primitive).

### Risks & Mitigations

- None material (docstring/docs/changelog only).

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none across WPs (WP02's claims depend on WP01's code).
- **MVP Scope**: WP01.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first repository-path escape tests | WP01 | P1 | Yes (with T002) |
| T002 | Red-first validation-path escape tests | WP01 | P1 | Yes (with T001) |
| T003 | Shared body-path helper on the primitive | WP01 | P1 | No |
| T004 | Rewire `_read_body` | WP01 | P1 | No |
| T005 | Rewire `body_text` | WP01 | P1 | No |
| T006 | Run owning test surface + baseline | WP01 | P1 | No |
| T007 | Primitive docstring claim | WP02 | P2 | No |
| T008 | Pack validator ordinal | WP02 | P2 | No |
| T009 | Pack-skill how-to clarification | WP02 | P2 | No |
| T010 | Changelog entry | WP02 | P2 | No |
