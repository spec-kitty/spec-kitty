---
description: "Work package task list for accept-path-conventions-name-overrides-01M66F7N"
---

# Work Packages: Name the path-convention override routes in accept's failure text

**Inputs**: Design documents from `kitty-specs/accept-path-conventions-name-overrides-01M66F7N/`
**Prerequisites**: plan.md (required), spec.md, research.md, data-model.md, quickstart.md
**Tracked issue**: spec-kitty/spec-kitty#6633

**Tests**: This is a defect fix — the regression test is part of the deliverable (red-first, per ATDD-First Discipline and DIRECTIVE_034).

**Organization**: Two work packages: the code+test slice (WP01) and the docs+changelog slice (WP02). WP02 depends on WP01 only for the final text wording; both stay small.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Failure-text guidance — data, rendering, red-first test (Priority: P1) 🎯 MVP

**Goal**: The strict path-convention failure text names `project.path_conventions` in `.kittify/config.yaml` (with the exact missing remappable keys in a copy-pasteable example) and the `.kittify/overrides/missions/<type>/mission.yaml` drop route, while the #3783 contract stays green.
**Independent Test**: `uv run pytest tests/agent/test_validators_unit.py -q` — the new regression test fails on pre-fix `main` and passes after the fix; the existing `test_format_errors_names_lenient_before_mkdir_and_drops_unconditional_claim` passes unmodified.
**Prompt**: `/tasks/WP01-failure-text-guidance.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002

### Included Subtasks

T001 Write the red-first regression test in `tests/agent/test_validators_unit.py`: strict-mode `validate_mission_paths` on a Go-style repo (missing `src/`, `tests/`, `docs/`) raises an error whose text names `project.path_conventions`, `.kittify/config.yaml`, each missing remappable key (`workspace`, `tests`, `documentation`) inside a YAML snippet, and the mission-override route — assert key names, not a literal snapshot
T002 Extend `PathValidationResult` in `src/specify_cli/validators/paths.py` with `remappable_missing_keys: list[str]` and `mission_type: str | None`, both default-empty
T003 Populate the fields in `validate_mission_paths`: record each missing key not in `ARTIFACT_ROUTED_KEYS`; derive the mission-type slug from `mission.path.name` when meaningful, `None` otherwise (hand-built stubs, neutral org missions)
T004 Render the guidance in `format_errors()`: after the `--lenient` sentence, a block naming `project.path_conventions` with a copy-pasteable YAML example listing exactly `remappable_missing_keys`, and a line naming `.kittify/overrides/missions/<mission_type>/mission.yaml` as the drop route; blocks render only when their inputs are non-empty
T005 Verify: focused unit suite green, existing #3730 contract test unmodified and green, `ruff check` and `mypy` clean on changed files

### Implementation Notes

- Red-first: T001 lands (and is shown failing against the pre-fix entry point) before T002-T004.
- The example must list ONLY the keys actually missing and remappable (SC-002's partial-missing scenario: `docs/` existing drops `documentation` from the snippet).
- Never suggest `deliverables` (C-002); `ARTIFACT_ROUTED_KEYS` is importable from `specify_cli.config.path_conventions`.
- Ordering: `--lenient` before `mkdir -p` (C-001) — the new blocks go between the `--lenient` sentence and `Required Actions:`.

### Parallel Opportunities

- None within this WP; T002-T004 are one coherent change on one file.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Hand-built `PathValidationResult` fixtures render degraded-but-valid text → default-empty fields, blocks gated on non-empty inputs.
- Wrong mission-type slug for exotic missions → derive only from `mission.path.name`, fall back to a generic `<mission-type>` placeholder.

---

## Work Package WP02: Accept how-to and changelog (Priority: P2)

**Goal**: `docs/guides/how-to/missions/accept-and-merge.md` names both project-level routes where the `contracts: none` bullet says other conventions "stay in force"; the `[Unreleased]` changelog entry documents the improved failure text.
**Independent Test**: The how-to section names `project.path_conventions` and `.kittify/overrides/missions/`; the changelog has a bold impact-first lead with `(#6633)` and before/after, under 1,200 characters.
**Prompt**: `/tasks/WP02-accept-howto-changelog.md`
**Requirement Refs**: FR-004

### Included Subtasks

T006 In `docs/guides/how-to/missions/accept-and-merge.md`, extend the path-conventions passage (the `contracts: none` bullet that says other conventions "stay in force") to name the `project.path_conventions` remap route and the `.kittify/overrides/missions/<type>/mission.yaml` drop route, cross-linking the ADR
T007 Add an `[Unreleased]` entry to `docs/changelog/CHANGELOG.md`: bold impact-first lead with `(#6633)`, before/after, under 1,200 characters
T008 Verify docs gates: `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` and the docs-freshness check stay green (no new doc page or ADR, so no index regen)

### Implementation Notes

- Keep the how-to addition short: two bullets, cross-linked to `docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md`.
- Changelog: root `CHANGELOG.md` is a symlink — edit `docs/changelog/CHANGELOG.md`.

### Parallel Opportunities

- T006 and T007 touch different files and can proceed in parallel once WP01's wording is settled.

### Dependencies

- Depends on WP01 (the docs describe the landed text).

### Risks & Mitigations

- Changelog length drift → keep the entry under 1,200 characters.
