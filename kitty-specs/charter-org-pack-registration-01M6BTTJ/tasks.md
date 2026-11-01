---
description: "Work package task list for charter org pack registration (#6267)"
---

# Work Packages: Register an org Charter Pack with a project from the CLI

**Inputs**: `kitty-specs/charter-org-pack-registration-01M6BTTJ/spec.md`, `plan.md`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently deliverable and testable. Subtasks are reference rows: completion is
recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`.

---

## Work Package WP01: Registry write seam (Priority: P0)

**Goal**: One owner for mutating `charter_packs.org.packs`: strict read, comment/format-preserving
mutation, atomic write, empty-scaffold cleanup.
**Independent Test**: `pytest tests/cli/test_charter_org_registration.py -k seam` — add→remove on a
commented config returns the file byte-identical, and an unreadable config is refused with the file
untouched.
**Prompt**: `/tasks/WP01-registry-write-seam.md`
**Requirement Refs**: FR-002, FR-007, FR-008, NFR-001, NFR-002, C-001, C-002

### Included Subtasks

T001 [P] Write the failing seam tests first in `tests/cli/test_charter_org_registration.py`
(strict-read refusal, add→remove byte round-trip, atomic-write failure leaves the file intact)
T002 Implement `register_org_pack(repo_root, pack, *, replace=False)` in
`src/charter/offering/drg/org_pack_config.py`
T003 Implement `unregister_org_pack(repo_root, name)` in the same module, including empty
`org.packs` / `org` / `charter_packs` cleanup
T004 Write through `kernel.atomic.atomic_write` with the module's existing `_yaml()` round-trip
settings, so comments, quoting and unrelated keys survive
T005 Extend `__all__` and the module docstring; confirm no second shape parser was introduced

### Implementation Notes

- Reuse `load_pack_registry(..., strict=True)` as the precondition; never write a config that could
  not be read.
- Dump only after mutating the in-memory `CommentedMap`; do not re-serialize from the pydantic
  model (that would drop comments).

### Parallel Opportunities

- T001 can be authored alongside T002/T003 but must be seen failing before they land.

### Dependencies

- None (starting package).

### Risks & Mitigations

- ruamel reformatting unrelated blocks → assert byte round-trip in T001, not just semantic equality.
- Empty-block cleanup deleting sibling keys → drop `org`/`charter_packs` only when the mapping is
  left empty.

---

## Work Package WP02: CLI door — `charter org add` / `charter org remove` (Priority: P0) 🎯 MVP

**Goal**: The operator-facing commands from the issue: validate, register, refuse bad input, report
machine-readably.
**Independent Test**: `pytest tests/cli/test_charter_org_registration.py -k cli` with a temporary
project, a scaffolded valid pack and an invalid pack; asserts exit codes, written entries, and that
`charter pack list` reports the registered pack.
**Prompt**: `/tasks/WP02-cli-add-remove.md`
**Requirement Refs**: FR-001, FR-003, FR-004, FR-005, FR-006, FR-009, FR-010, NFR-003, NFR-004, C-003, C-004

### Included Subtasks

T006 [P] Write the failing CLI acceptance tests: no `add`/`remove` command exists today, so the
first run must fail on `No such command 'add'`
T007 Implement `org add` in `src/specify_cli/cli/commands/charter/org.py`: option parsing, reserved
names (`built-in`, `project`), `--ref`/`--source-type` requiring `--url`, `--subdir` validation via
`OrgPackConfig`
T008 Implement the add preconditions: project root required; without `--url` the pack root must
exist and validate through `validate_pack_with_org_charter`; with `--url` an absent root is
registered and the `charter fetch` follow-up printed
T009 Implement duplicate refusal and `--force` in-place replacement (declaration order preserved)
T010 Implement `org remove`: refuse an unknown name listing the configured names; otherwise delete
the entry and report the pack directory still on disk
T011 Add `--json` output for both commands and route refusals through the module's existing coded
error rendering
T012 Verify the commands make no network call (assert in the test that add/remove work with the
network primitives monkeypatched to fail)

### Implementation Notes

- Keep heavy imports lazy inside the command bodies so `--help` stays fast (module precedent).
- All mutual-exclusion and reserved-name refusals happen before any read-modify-write.

### Parallel Opportunities

- T007 and T010 touch the same file; sequence them.
- T012 is independent of the others once the commands exist.

### Dependencies

- Depends on WP01 (the write seam).

### Risks & Mitigations

- Accidental write on a refused path → every refusal test asserts the config is byte-identical.
- Validation of a `~`/`${VAR}` `local_path` → resolve through `effective_root`, store verbatim.

---

## Work Package WP03: Guidance, docs and changelog (Priority: P2)

**Goal**: Remove the hand edit from the documented path and record the change.
**Independent Test**: `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 after
regenerating the touched CLI reference sections, and the how-to's Step 8 shows the command instead
of a raw YAML block.
**Prompt**: `/tasks/WP03-docs-and-changelog.md`
**Requirement Refs**: FR-011, SC-004, C-005

### Included Subtasks

T013 Update `charter fetch`'s "no org charter packs configured" message and hint in
`src/specify_cli/cli/commands/charter/authoring.py` to name `spec-kitty charter org add`
T014 Regenerate the `spec-kitty charter org add` / `spec-kitty charter org remove` sections of
`docs/api/cli-commands.md` from a temp build (not a whole-file rebuild) and add the `org` row to
`docs/api/charter-commands.md`
T015 Rewrite Step 8 of
`docs/guides/how-to/governance/create-an-org-doctrine-pack.md` to lead with the command and keep the
YAML as the reference shape
T016 Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (impact-first lead with
`(#6267)`, before/after, under 1,200 characters)

### Implementation Notes

- The CLI reference lives inside a `<!-- BEGIN GENERATED -->` envelope; splice only the touched
  sections.
- Changelog style is checked by `scripts/docs/check_changelog_style.py`.

### Parallel Opportunities

- T013 and T015 are independent of T014/T016.

### Dependencies

- Depends on WP02 (the text must name flags that exist).

### Risks & Mitigations

- Full CLI-reference rebuild races the shared CLI asset cache on this host → targeted splice, then
  verify with the freshness checker.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → WP03.
- **Parallelization**: within WP01 the seam tests and implementation can be authored together; WP03's
  doc prose can be drafted while WP02 lands.
- **MVP Scope**: WP01 + WP02 — that is the issue's "done when" (a project can be pointed at an org
  pack without hand-editing config).

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP02 |
| FR-002 | WP01 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP02 |
| FR-006 | WP02 |
| FR-007 | WP01 |
| FR-008 | WP01 |
| FR-009 | WP02 |
| FR-010 | WP02 |
| FR-011 | WP03 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP02 |
| NFR-004 | WP02 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP02 |
| C-004 | WP02 |
| C-005 | WP03 |
| SC-001 | WP02 |
| SC-002 | WP01, WP02 |
| SC-003 | WP02 |
| SC-004 | WP03 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Failing seam tests (strict read, byte round-trip, atomic failure) | WP01 | P0 | Yes |
| T002 | `register_org_pack` | WP01 | P0 | No |
| T003 | `unregister_org_pack` + empty cleanup | WP01 | P0 | No |
| T004 | Atomic write via `kernel.atomic` + ruamel round-trip | WP01 | P0 | No |
| T005 | `__all__` / docstring / single-authority check | WP01 | P0 | Yes |
| T006 | Failing CLI acceptance tests | WP02 | P0 | Yes |
| T007 | `org add` option parsing and input refusals | WP02 | P0 | No |
| T008 | Add preconditions (root, existence, validation) | WP02 | P0 | No |
| T009 | Duplicate refusal + `--force` replacement | WP02 | P0 | No |
| T010 | `org remove` | WP02 | P0 | No |
| T011 | `--json` and coded refusals | WP02 | P1 | Yes |
| T012 | No-network assertion | WP02 | P1 | Yes |
| T013 | `charter fetch` guidance message | WP03 | P2 | Yes |
| T014 | CLI reference + charter-commands table | WP03 | P2 | Yes |
| T015 | How-to Step 8 rewrite | WP03 | P2 | Yes |
| T016 | Changelog entry | WP03 | P2 | Yes |
