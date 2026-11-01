---
work_package_id: WP02
title: Contract record — C-003, README and changelog
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
- C-004
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Record
history:
- at: '2026-11-01T15:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/offering/api.py
- src/charter/offering/README.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6285'
- '#6218'
---

# Work Package Prompt: WP02 – Contract record: C-003, README and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

---

## Objectives & Success Criteria

Make the module and the maintainer-facing documentation state the frozen surface and the
ADR-0004 generated-DTO direction honestly, so a consumer author is no longer told that today's
hand-written types are permanent.

Done when:

- `src/charter/offering/api.py`'s C-003 no longer says "OpenAPI conventions do not apply"; it
  states that the seam's return types become contract-generated DTOs and that the hand-written
  types recorded in the census are transitional, and it points at the census file.
- The `c003` header note in `tests/architectural/charter_offering_public_surface.yaml` and the
  docstring say the same thing in substance (neither is a second, different rule).
- `src/charter/offering/README.md` gains a "Public contract surface" section: what is frozen,
  where the census lives, how to change the surface, and what is deliberately not on it.
- `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry with the `(#6285)` reference.
- `tests/architectural/test_no_legacy_terminology.py` and
  `uv run python -m scripts.docs.check_docs_freshness --ci` stay green (freshness baseline is
  0 errors; its 13 warnings pre-date this branch).

## Context & Constraints

- **Docstring-only in `api.py`.** Do not touch `__all__`, the imports, sorting or any symbol —
  WP01 pins that surface and a change here would be an unrecorded surface change.
- **#6218 stays distinct** (C-004): this WP consumes its direction, it does not close it, does
  not restate spec-kitty-charter ADR-0004, and does not implement or claim any DTO generation.
- **No new docs page** under `docs/`: a new page would need an inventory entry and retrieval
  index regeneration, and the offering README is the maintainer-facing home for this seam
  (plan.md, "Structure Decision").
- Terminology canon: "Mission", "surface", "seam". Never "feature".

## Branch Strategy

- **Strategy**: single mission branch; planning base and merge target are both
  `kitty/mission-charter-offering-surface-freeze-01M6BTTR`.
- **Planning base branch**: `kitty/mission-charter-offering-surface-freeze-01M6BTTR`
- **Merge target branch**: `kitty/mission-charter-offering-surface-freeze-01M6BTTR`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change them
> manually unless the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T007 – Reword C-003

- **Purpose**: Remove the stale assertion that contradicts the accepted decision.
- **Steps**:
  1. Replace the C-003 section of the `charter.offering.api` module docstring with a short
     statement: the public contract is an in-process Python surface today, its return types
     become DTOs generated from the spec-kitty-charter OpenAPI contract (ADR-0004, tracked in
     core by #6218), and the hand-written types listed in the census
     (`tests/architectural/charter_offering_public_surface.yaml`) are transitional.
  2. Keep the rest of the docstring intact (FR-001 note, layering invariant C-001, disposition
     provenance). Do not restate the ADR's reasoning.
  3. Cross-check the census `c003` note in the same pass; if the two disagree, change the census
     note in this WP (it is a `tests/` file owned by WP01, so a one-line consistency edit is
     acceptable under the ownership-map leeway rule — record the rationale in the WP history).
- **Files**: `src/charter/offering/api.py`
- **Notes**: the section heading "Contract kind (C-003)" may stay; the sentence that must go is
  the one asserting OpenAPI conventions do not apply.

### Subtask T008 – Offering README public-surface section

- **Purpose**: A maintainer who never opens a gate file should find the frozen surface.
- **Steps**:
  1. Add a "Public contract surface" section to `src/charter/offering/README.md`, after the
     "Design principle" section.
  2. Content: the surface is `charter.offering.api.__all__` plus the `charter.*` facades that
     front it by identity; the frozen census is
     `tests/architectural/charter_offering_public_surface.yaml`; changing the surface means
     editing both and re-running the gate file; reached-but-not-public paths are FACADE-ONLY /
     TICKETED-BASELINE / CONSTRUCTION-ROUTED / INTERNAL and are not part of the contract; the
     hand-written types are transitional per ADR-0004 (#6218).
  3. Keep it under ~25 lines and link nothing outside the repository.
- **Files**: `src/charter/offering/README.md`

### Subtask T009 – Changelog and verification

- **Purpose**: User-facing record and gate evidence.
- **Steps**:
  1. Add an `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a
     symlink to it): bold impact-first lead with `(#6285)`, then before/after, under 1,200
     characters. Say what a maintainer can now rely on: the offering public surface is enumerated
     in one committed census and the gates fail when the live surface, the facades or the
     dispositions drift from it; C-003 now states the generated-DTO direction.
  2. Run and record:
     ```bash
     uv run pytest -q tests/architectural/test_no_legacy_terminology.py
     uv run python -m scripts.docs.check_docs_freshness --ci
     uv run ruff check src/charter/offering/api.py
     uv run mypy src/charter/offering/api.py
     ```
  3. Confirm `git diff` on `api.py` touches only the docstring.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Notes**: if freshness reports a new error introduced by this WP, fix it; its pre-existing
  warnings are out of scope (Pre-existing Failure Reporting Rule).

## Test Strategy

- `tests/architectural/test_no_legacy_terminology.py` guards the wording.
- `scripts.docs.check_docs_freshness --ci` must stay at 0 errors.
- `mypy`/`ruff` on the touched Python file; the change is a docstring, so no new tests are needed
  beyond WP01's census gate (DIRECTIVE_041: no test without behaviour to guard).

## Risks & Mitigations

- Wording drift between the census `c003` note and the docstring → T007 step 3 makes them agree
  in the same WP.
- Reader confusion about #6218 status → state "tracked by #6218" and do not claim it landed.
- Freshness baseline noise → compare against the baseline recorded in research.md (0 errors,
  13 warnings), not against zero warnings.

## Review Guidance

- Confirm `api.py`'s diff is docstring-only (`git diff -- src/charter/offering/api.py`).
- Confirm C-003 no longer states that OpenAPI conventions do not apply and does not promise a
  DTO implementation that does not exist.
- Confirm the README names the census path and the change procedure, and does not duplicate the
  census table (one canonical authority).
- Confirm the changelog entry leads with impact, carries `(#6285)`, and stays under 1,200
  characters.

## Progress & Status

Record each subtask with `spec-kitty agent tasks mark-status T007 --status done` (and so on),
and append decisions with
`spec-kitty agent tracer-append --mission charter-offering-surface-freeze-01M6BTTR --category design-decisions --entry "..."`.
