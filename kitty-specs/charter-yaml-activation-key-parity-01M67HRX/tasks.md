---
description: "Work package task list for #6556 CharterYaml activation-key parity"
---

# Work Packages: CharterYaml activation-key parity

**Inputs**: Design documents from `kitty-specs/charter-yaml-activation-key-parity-01M67HRX/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (grounding and import-cycle evidence)

**Tests**: Required — this is a defect fix (charter ATDD-First Discipline, DIRECTIVE_034): the
failing test comes before the fix, through the pre-existing activation-writer entry point.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into two work packages (`WPxx`).

**Prompt Files**: `/tasks/WP01-schema-activation-key-parity.md`,
`/tasks/WP02-changelog-entry.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log snapshot is
  the sole subtask-completion authority — there is no `- [ ]` box to tick.

## Path Conventions

- **Single project**: `src/`, `tests/` (this repository's layout).

---

## Work Package WP01: Schema/authority parity for the charter.yaml activation keys (Priority: P1) 🎯 MVP

**Goal**: Make `CharterYaml` accept exactly the flat activation-key vocabulary that
`ACTIVATION_YAML_KEYS` defines and that the legacy activation writer writes into
`charter.yaml`, proven red-first through the writer, and pinned so it cannot drift again.
**Independent Test**: `uv run pytest tests/charter/test_charter_yaml_model.py
tests/charter/test_activation_vocabulary_setequal.py -q` — the writer→`charter.yaml`→model
regression and the authority parity gate both pass, and the pre-existing strictness tests
pass unmodified.
**Prompt**: `/tasks/WP01-schema-activation-key-parity.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Write the red-first writer→model regression (legacy fixture + `prepare_activation_write` + `CharterYaml.model_validate`) for `activated_skills`, `activated_glossary_packs`, `activated_anti_patterns`; capture the failing run
T002 Parametrize the flat-root field test over `ACTIVATION_YAML_KEYS` instead of the hard-coded ten-name list; capture the failing run
T003 Declare `activated_glossary_packs`, `activated_skills`, `activated_anti_patterns` on `CharterYaml` (typed `list[str] | None = None`) and correct the class docstring's "ten `activated_*` fields" claim
T004 Add the both-directions parity gate in `tests/charter/test_activation_vocabulary_setequal.py`, plus the explicit no-`activated_assets` case (C-001)
T005 Add the strictness-retained case (unknown `activated_not_a_kind` still rejected) and confirm the pre-existing forbid/nested/three-state tests pass unmodified
T008 Validate one document that carries every legal activation key at once (the spec's all-keys edge case), so set-level acceptance is proven and not only per-key

### Implementation Notes

- Order matters: T001 and T002 are the red proof and must be run and recorded **before** T003.
- The only `src/` edit is `src/charter/activation/schemas.py` (NFR-003); no writer, ledger,
  migration or serializer changes.
- The parity test must derive its expected set from `ACTIVATION_YAML_KEYS` (lazy function
  scope, the established idiom) — never restate the names (C-002).
- Do not add `activated_assets` (C-001): `ASSET` is not charter-activatable and the writer
  refuses the key.

### Parallel Opportunities

- None: T001/T002 (red) gate T003 (green), and T004/T005 depend on the field block.

### Dependencies

- None (starting package). Everything else in this mission depends on it.

### Risks & Mitigations

- A module-level `from charter.activation.pack_manager import …` in `schemas.py` would be a
  circular import (research.md R5) → keep the import inside the test helper, as the existing
  vocabulary tests do.
- Turning `extra="forbid"` into `extra="allow"` would "fix" the symptom and delete the
  structural guard → T005 pins strictness.

---

## Work Package WP02: Changelog entry for the schema/authority parity fix (Priority: P2)

**Goal**: Record the user-facing effect — `CharterYaml` is now usable as the `charter.yaml`
schema, and a legacy charter carrying any legal activation key validates — under
`[Unreleased]`.
**Independent Test**: `python packs/internal/assets/validate-pr-body.py` is unrelated; the
check here is the changelog's own shape: an `[Unreleased]` bullet with an impact-first bold
lead, `(#6556)`, before/after, under 1,200 characters.
**Prompt**: `/tasks/WP02-changelog-entry.md`
**Requirement Refs**: FR-001, C-001

### Included Subtasks

T006 Add the `[Unreleased]` `### Fixed` entry with the bold impact-first lead, `(#6556)`, before/after, under 1,200 characters
T007 Cross-check `docs/architecture/doctrine-kinds.md` for a claim that the schema rejects these keys; correct it only if the sentence is now false, then run the docs freshness check if a doc page changed

### Implementation Notes

- The root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the latter.
- Keep it impact-first and operator-readable; no internal-only jargon beyond the key names,
  which operators see in their own `charter.yaml`.

### Parallel Opportunities

- Can be prepared in parallel with WP01, but must be committed after WP01's behaviour is
  final (the entry describes the shipped behaviour).

### Dependencies

- Depends on WP01 (describes its shipped behaviour).

### Risks & Mitigations

- Over-long entry → keep under 1,200 characters and say what changed for the reader, not a
  file-by-file account.
- A stale doc sentence → correct only what the change makes false; do not re-document the
  activation ledger (#6496 owns that).
