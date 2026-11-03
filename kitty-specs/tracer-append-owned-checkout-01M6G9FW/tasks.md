# Work Packages: tracer-append routes through the owned Mission checkout

**Inputs**: Design documents from `kitty-specs/tracer-append-owned-checkout-01M6G9FW/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tracer-append-owned-selector.md, quickstart.md

**Tests**: red-first. WP01 begins by writing the failing guard for the reported scenario on a
two-checkout fixture, then makes it pass; the refusal case is added before the refusal path is
wired.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently reviewable; WP02 depends on WP01 because it documents and records the
delivered behaviour.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different file, no shared state).
- Subtasks are reference rows, not checkboxes: completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Owned fact decides the tracer write surface (Priority: P1)

**Goal**: `tracer-append` resolves the owned Mission fact (explicit flag or flagless adoption)
before computing any write input, refuses typed before writing on an invalid target, and threads
the fact into the tracer writer so the write lands in the checkout that owns the Mission.
**Independent Test**: `uv run pytest tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py -q` passes; the same module fails on unmodified `src` because `--owned-checkout` does not exist and the entry lands in the repository root.
**Prompt**: `/tasks/WP01-owned-fact-write-surface.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004, SC-005

### Included Subtasks

- T001 Red-first owned-routing test through the real `tracer-append` entry point (two-checkout fixture).
- T002 Red-first refusal test: `--owned-checkout <repository root>` exits 1 typed with zero writes.
- T003 Declare `--owned-checkout` with `OwnedCheckoutOption` and validate once via `resolve_owned_or_refuse`.
- T004 Replace the four root-derived inputs with the fact-derived ones (root, branch, policy, owned passthrough).
- T005 Add the `owned` keyword to `append_tracer_finding` and thread it into `write_artifact` and the two `placement_seam` calls.
- T006 Pin the unchanged non-owned path (payload keys, refusal shapes, exit codes) and run the owned single-authority gate.

### Implementation Notes

- The CLI already imports `OwnedCheckoutOption`'s module siblings; keep the import list local to
  the command module and do not create a new owned-resolving module.
- `owned.write_branch` replaces `get_feature_target_branch(...)` only on the owned path; the
  non-owned path keeps its best-effort `except Exception` fallback verbatim.
- The refusal must be rendered through `emit_owned_refusal` (inside `resolve_owned_or_refuse`), so
  the command's own `_error_payload` shape is untouched.
- `append_tracer_finding`'s new keyword defaults to `None`; its existing callers must not change.

### Parallel Opportunities

- T001 and T002 are the same new module: write both before T003. T005 is a different file from
  T003/T004 and can proceed in parallel once T001 exists.

### Dependencies

- None (root).

### Risks & Mitigations

- **Swallowing the writer's structured refusals** → the owned refusal exits inside
  `resolve_owned_or_refuse`, before the `try` that catches the writer's exceptions; T006 pins the
  existing shapes.
- **Second ownership interpretation** → the single-authority gate (`tests/architectural/
  test_owned_checkout_single_authority.py`) runs in T006 with its allowlist still empty.
- **Accidentally changing the non-owned payload** → T006 asserts the payload key set and exit codes
  for the non-owned invocation.

---

## Work Package WP02: Changelog fragment, docs and mission record (Priority: P2)

**Goal**: The change is documented where users and maintainers look, and the Mission's own record
(issue matrix, tracers) is complete.
**Independent Test**: `uv run --frozen python -m scripts.docs.check_changelog_style` and
`check_spelling --pass unreleased` pass on the new fragment; `docs/api/agent-subcommands.md`
documents the owned selector; the issue matrix carries a resolved `#7081` row.
**Prompt**: `/tasks/WP02-changelog-docs-record.md`
**Requirement Refs**: FR-001, FR-005, SC-004

### Included Subtasks

- T007 Changelog fragment `docs/changelog/unreleased/<pr>.fixed.md` with the impact-first lead.
- T008 Document `--owned-checkout` for `tracer-append` in `docs/api/agent-subcommands.md`.
- T009 Close the Mission tracers and resolve the `#7081` issue-matrix row.

### Implementation Notes

- Fragments, not `docs/changelog/CHANGELOG.md` (#6988): `check_changelog_style` rejects the old
  `[Unreleased]`-entry shape.
- If the docs page carries an embedded help-output fixture, update it in place and verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci` (errors=0); do not rebuild the whole
  CLI reference on a shared machine.
- Name the fragment with the PR number once the PR exists, per `docs/changelog/unreleased/README.md`.

### Parallel Opportunities

- T007 and T008 touch different files and can proceed in parallel.

### Dependencies

- WP01 (the documented behaviour must exist).
