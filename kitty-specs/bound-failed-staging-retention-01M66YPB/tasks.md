# Work Packages: Bound failed-synthesis staging retention

**Inputs**: Design documents from `kitty-specs/bound-failed-staging-retention-01M66YPB/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, quickstart.md

**Tests**: Required — the mission is a defect fix; the spec demands a failing-first
test through the pre-existing entry point (C-004, SC-001..SC-007).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages
(`WPxx`). Each work package must be independently deliverable and testable.

**Prompt Files**: The work package references a matching prompt file in
`kitty-specs/bound-failed-staging-retention-01M66YPB/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Bound the preserved failures in the staging lifecycle (Priority: P0)

**Goal**: A refused synthesis keeps only the newest 3 `.staging/<run_id>.failed/`
directories, always retains the failure it just reported, never touches a live
staging directory, and states the bound to the operator and in the docs.
**Independent Test**: Six refusals on one temporary project leave exactly 3
failed directories with the newest `cause.yaml` readable; a pre-existing overflow
is reduced to 3; a live staging directory survives byte-identical.
**Prompt**: `kitty-specs/bound-failed-staging-retention-01M66YPB/tasks/WP01-staging-retention-bound.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, C-004, C-005

### Included Subtasks

T001 Write the failing-first retention tests in `tests/charter/synthesizer/test_staging_retention_6723.py` (six refusals leave 3; newest preserved with `cause.yaml`; overflow reduced; live staging untouched; mtime tie determinism; removal failure does not raise) and run them red.
T002 Add the real-CLI refusal case to the same test file: refuse `charter synthesize` more times than the bound on a temporary project and assert the count stays at 3 and the directory named in the output still exists.
T003 Implement `DEFAULT_KEEP_FAILED_RUNS = 3` and the retention helper in `src/charter/activation/synthesizer/staging.py`, called at the end of `commit_to_failed`, deleting through `PathGuard.rmtree`.
T004 State the bound in the refusal hint in `src/specify_cli/cli/commands/charter/synthesize.py`, importing the constant instead of restating the number.
T005 [P] Update the `.staging` row in `docs/context/governance-files.md` and the retention sentences in `docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md`.
T006 [P] Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (bold impact-first lead, `(#6723)`, before/after, under 1,200 characters).
T007 Run the targeted suite (`tests/charter/synthesizer/`), `make test-fast`, ruff check/format, mypy on the changed module, and the terminology guard; record the counts.

### Implementation Notes

- The retention belongs in `StagingDir.commit_to_failed` after the rename and the
  `cause.yaml` write: that is the one place every refusing caller passes through.
- Order candidates by directory mtime, newest first, with the directory name as a
  descending tiebreak; pass the current `<run_id>` as `preserve`.
- Only names ending in `.failed` are candidates. Never select a live `<run_id>/`.
- Suppress listing/removal errors: retention must never replace the real failure.
- No allowlist change, no `shutil.rmtree` at the call site, no config key.

### Parallel Opportunities

- T005/T006 (docs) can proceed alongside T003/T004 once the constant exists.

### Dependencies

- None. Single work package.

### Risks & Mitigations

- **Deleting the current run**: mitigated by the explicit `preserve` argument and a
  test asserting the reported directory exists after the command.
- **Touching a live run**: mitigated by filtering on the `.failed` suffix and a
  test with a populated non-`.failed` directory.
- **Doc drift**: the ADR currently says failed dirs are "not deleted"; update it in
  the same change and keep the number sourced from the constant.

---
