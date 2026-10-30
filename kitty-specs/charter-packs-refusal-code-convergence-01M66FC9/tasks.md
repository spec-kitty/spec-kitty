---
description: "Work package task list for charter-packs-refusal-code-convergence-01M66FC9"
---

# Work Packages: charter packs refusal code convergence

**Inputs**: Design documents from `kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/`
**Prerequisites**: plan.md (required), spec.md, research.md (decisions D1–D3)

**Tests**: The mission is a defect fix pinned red-first; the re-pinned CLI refusal test IS the acceptance test (ATDD-first, DIRECTIVE_034).

**Organization**: Two work packages: the code+tests seam fix (WP01), then the user-facing docs and changelog (WP02). WP02 depends on WP01 because the docs describe the converged behavior.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`

---

## Work Package WP01: Typed registry error at the fail-closed seam (Priority: P1) 🎯 MVP

**Goal**: `charter activate` and `charter deactivate` refuse a malformed `charter_packs` registry with the same code (`ACTIVE_CHARTER_CONFIG_INVALID`, text and `--json`), via a typed error raised at `require_declared_org_roots`; the "declared pack not fetched" refusal stays `ACTIVATION_FAILED` on activate; every strict reader keeps its contract.
**Independent Test**: With `charter_packs: [1, 2]`, all four CLI invocations (activate/deactivate × text/`--json`) exit 1 with `ACTIVE_CHARTER_CONFIG_INVALID` and leave `.kittify/` byte-identical; with a declared-but-unfetched pack, activate still exits 1 with `ACTIVATION_FAILED` naming `spec-kitty charter fetch`.
**Prompt**: `tasks/WP01-typed-registry-error.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002

### Included Subtasks

T001 Re-pin `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py::test_a_malformed_charter_packs_config_is_refused` red-first: both verbs expect `ACTIVE_CHARTER_CONFIG_INVALID`
T002 Add `OrgPackRegistryUnreadableError` to `src/charter/offering/drg/org_pack_config.py` and raise it from `require_declared_org_roots`' registry-read failure arm only (not-fetched arm keeps plain `ValueError`)
T003 Extend `tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py` with seam assertions: the typed error is raised, subclasses `ActiveCharterConfigError` AND `ValueError`, carries code `ACTIVE_CHARTER_CONFIG_INVALID`, and the not-fetched arm still raises plain `ValueError`
T004 Run the strict readers' regression suites (effective set, preset application, requirement-kinds loader) and the charter CLI activation suites; confirm green

### Implementation Notes

- Red-first order: T001 must fail on `activate` before T002 lands (ATDD-first).
- The typed error subclasses both `ActiveCharterConfigError` (lazy import — C-001) and `ValueError` (FR-004). The CLI needs no change: `_apply_direct_activation`'s `except ActiveCharterConfigError` arm already precedes its `except (ValueError, DRGLoadError)` arm.
- Keep the message lead "the org pack registry cannot be read: ..." so the CLI test's `"org pack registry"` assertion holds for both verbs.

### Parallel Opportunities

- T001 and T003 touch different test files but T003's assertions only pass after T002; sequence T001 → T002 → T003 → T004.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Dropping the `ValueError` base in a future refactor would silently change three strict readers → T003 pins the base explicitly.

---

## Work Package WP02: Docs and changelog for the converged refusal (Priority: P2)

**Goal**: The CLI reference no longer documents the asymmetry and the changelog records the user-facing convergence.
**Independent Test**: `docs/api/charter-commands.md` has no asymmetry edge-case note; its code table explains the malformed-`charter_packs` refusal as `ACTIVE_CHARTER_CONFIG_INVALID` for both verbs; `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry with the `(#6772)` reference, impact-first bold lead, before/after, under 1,200 characters.
**Prompt**: `tasks/WP02-docs-changelog.md`
**Requirement Refs**: FR-005, SC-004

### Included Subtasks

T005 Remove the asymmetry edge-case note from `docs/api/charter-commands.md` and converge the `ACTIVE_CHARTER_CONFIG_INVALID` / `ACTIVATION_FAILED` code-table rows
T006 Add the `[Unreleased]` changelog entry to `docs/changelog/CHANGELOG.md`

### Implementation Notes

- The docs must describe behavior, not the exception class; name the codes and the two cases (malformed registry vs. declared-but-unfetched pack).

### Parallel Opportunities

- T005 and T006 touch different files and can proceed in parallel once WP01 is approved.

### Dependencies

- Depends on WP01 (the docs describe the converged behavior WP01 delivers).

### Risks & Mitigations

- None material; docs-only.
