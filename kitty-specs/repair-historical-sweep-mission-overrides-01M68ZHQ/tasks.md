# Work Packages: Repair historical sweep-created mission overrides

**Inputs**: Design documents from `/kitty-specs/repair-historical-sweep-mission-overrides-01M68ZHQ/`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Tests**: Required — this is a defect fix. The reproduction runs red through the pre-existing
entry point (the real `spec-kitty upgrade` command and the registry it selects from) before the
repair exists (DIRECTIVE_034).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package must be independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/specify_cli/`, `tests/`

---

## Work Package WP01: One path mapping for a project mission file (Priority: P1) 🎯 MVP

**Goal**: `runtime/migrate.py` exposes one helper that maps a `.kittify/`-relative (or
`.kittify/overrides/`-relative) `missions/<type>/<rest>` onto the shipped mission tree, and
`_find_package_counterpart` resolves through it — behaviour-identical for every existing layout.
**Independent Test**: Call the helper with a nested mission path and with a flat `templates/` path;
the first returns the shipped mission file, the second `None`. The existing classifier tests
(including the #6548/#5280 regression) stay green.
**Prompt**: `/tasks/WP01-shared-mission-path-mapping.md`
**Requirement Refs**: FR-003, C-003, NFR-001

### Included Subtasks

T001 Extract `shipped_mission_counterpart(rel, package_root)` into `src/specify_cli/runtime/migrate.py` and make `_find_package_counterpart` delegate to it
T002 [P] Pin the helper directly (nested mission path → package file; flat path → `None`; missing file → `None`) and the classifier still routing through it
T003 Run the targeted suites and ruff/mypy on the touched files

### Implementation Notes

- The helper must take the `.kittify/`-relative `rel` (both trees are `<tree>/missions/<type>/<rest>`),
  never a hardcoded mission name — that hardcoded default is half of the #6548 bug.
- Keep the existing fallback joins (`package_root/<mission>/<rel>`, `package_root/<rel>`)
  untouched, and keep the `len(rel.parts) > 2` guard: the flat layouts must not change.
- No behaviour change is expected from this WP alone; it exists so the repair migration and the
  classifier ask the same question in one place (spec FR-003, plan Design Decision 6).

### Dependencies

- None (starting package). WP02 depends on it.

### Risks & Mitigations

- Regressing the classifier for the flat `templates/` / `command-templates/` / `scripts/` layouts →
  `tests/upgrade/test_migrate_integration.py` and `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py`
  are the regression net.

---

## Work Package WP02: The repair migration (Priority: P1)

**Goal**: A new registered migration, `4.0.0rc8_repair_historical_sweep_overrides`, removes a
`.kittify/overrides/missions/<type>/…` file proven byte-identical to its shipped counterpart,
preserves and names a differing one, and never reads one with no counterpart — all through the
ownership guard, with no shipped migration body edited.
**Independent Test**: Build a project at `4.0.0rc8` carrying a byte-identical and a differing
`software-dev` template override, run the real `spec-kitty upgrade`, and assert the identical one
is gone (resolution no longer `OVERRIDE`), the differing one is byte-identical and named, and a
re-run changes nothing.
**Prompt**: `/tasks/WP02-repair-migration.md`
**Requirement Refs**: FR-001, FR-002, FR-004, FR-005, FR-006, FR-007, FR-008, NFR-001, NFR-002, NFR-003, C-001, C-002, C-004, SC-001, SC-002, SC-003, SC-004, SC-005

### Included Subtasks

T004 Write the red-first reproduction in `tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py` (real `spec-kitty upgrade` CLI) and prove it fails on the unfixed tree
T005 Add `src/specify_cli/upgrade/migrations/m_4_0_0rc8_repair_historical_sweep_overrides.py` (scan, provenance verdicts, guarded removal, naming warnings, `detect`/`can_apply`/`apply`)
T006 Register the new id in `src/specify_cli/upgrade/migrations/order_manifest.txt` with its tie annotation, and pin the module in `tests/architectural/test_mutation_ownership_routing.py`
T007 [P] Add the unit tests: identical → removed, differing → kept and named, no counterpart → untouched, symlinked tree/file → refused, unreadable → preserved, CRLF copy → preserved, idempotent second apply, `can_apply` refusal without a package root
T008 Run the targeted suites (`tests/upgrade/`, the architectural membership/order/manifest gates) plus ruff/mypy

### Implementation Notes

- The migration must carry **no** raw `unlink`/`rmtree`/`rmdir`: the guard performs the removal
  (architectural gate `test_mutation_ownership_routing.py`, contract C1).
- Prove identity with `CanonicalContentProver(canonical=shipped_bytes, check_marker=False)` — the
  marker alone must never authorize a delete (#4961/#5050), and `check_marker=True` would delete a
  differing file that merely embeds the marker literal.
- `detect()` must be true for a differing candidate too, so the operator is actually told; a
  successful `apply()` records the step as settled, so the naming happens once per project.
- Refuse with a warning (never silently) when a component of `.kittify/overrides/missions` is a
  symlink or not a directory; skip and name a symlinked file. Create no directory, remove none.

### Dependencies

- Depends on WP01 (the shared mapping it resolves through).

### Risks & Mitigations

- The architectural routed-module pin fails until the new module is added → T006 is part of this WP,
  not a follow-up.
- The CLI-level test could creep past the 30-second budget → it builds a bare `.kittify/metadata.yaml`
  project (the `test_retired_hosted_target.py` pattern), not a full `init` tree.

---

## Work Package WP03: Changelog (Priority: P2)

**Goal**: The user-facing change is recorded under `[Unreleased]` → Upgrade Notes with an
impact-first lead, the `(#6548)` reference, and before/after, under 1,200 characters.
**Independent Test**: The changelog entry exists with the `(#6548)` reference; the docs-freshness
gate reports errors=0.
**Prompt**: `/tasks/WP03-changelog.md`
**Requirement Refs**: FR-002, FR-006, SC-003

### Included Subtasks

T009 Add the `[Unreleased]` Upgrade Notes entry (bold impact-first lead, `(#6548)`, before/after, under 1,200 characters)
T010 Verify docs freshness (`check_docs_freshness --ci`, errors=0) and the terminology test

### Implementation Notes

- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the file, never replace
  the symlink.
- Do not regenerate the whole CLI reference (shared machine state); only this entry changes.
- Model it on the existing #5280 Upgrade Notes entry, which is this migration's sibling.

### Dependencies

- Depends on WP02 (the entry must describe shipped behaviour and quote the real warning text).

### Risks & Mitigations

- Docs index drift → run `check_docs_freshness --ci` and `tests/architectural/test_no_legacy_terminology.py`.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → WP03.
- **Parallelization**: WP01's test subtask (T002) is independent of T001's edit; WP03 can be
  drafted while WP02 is reviewed but lands after it.
- **MVP Scope**: WP01 + WP02.
