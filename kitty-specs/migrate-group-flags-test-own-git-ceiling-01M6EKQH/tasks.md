# Work Packages: Make the migrate group-flag acceptance module own its git-discovery ceiling

**Inputs**: Design documents from `kitty-specs/migrate-group-flags-test-own-git-ceiling-01M6EKQH/`
**Prerequisites**: `spec.md` (requirements), `plan.md` (design), `research.md` (grounding evidence)

**Tests**: The mission *is* a test change; both new guards are written and observed red before the
fixture change (ATDD-first, C-011).

**Organization**: Five subtasks roll up into one work package. The mission is a single test module, so
one WP is the honest slice — two WPs would create a worktree per WP for a two-file diff.

**Prompt Files**: `tasks/WP01-pin-module-git-ceiling.md`

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `tests/`, `src/`, `docs/`.

---

## Work Package WP01: Pin the module's own git-discovery ceiling (Priority: P0)

**Goal**: `tests/cli/test_migrate_group_flags_4964.py` no longer depends on a process-wide
`GIT_CEILING_DIRECTORIES` for its hermeticity: its autouse isolation appends the test root as a ceiling,
and two non-vacuous guards pin that property.
**Independent Test**: Clear `GIT_CEILING_DIRECTORIES` on a host whose temp root is inside a repository
and run `uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q` — the non-dry-run
positive control stays green, and Guard A fails if the fixture append is reverted.
**Prompt**: `tasks/WP01-pin-module-git-ceiling.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002,
C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Add the two non-vacuity guards to `tests/cli/test_migrate_group_flags_4964.py` (red-first, no fixture change yet)
T002 Witness the red: run the module and record both guards failing (and the pre-existing positive control red with the ambient ceiling cleared)
T003 Implement the append-only ceiling in `_hard_repo_isolation` plus the `_append_ceiling` helper
T004 Prove non-vacuity both ways: revert the fixture append → Guard A red again; restore → module green; confirm the 76 pre-existing tests are untouched
T005 Write the changelog fragment `docs/changelog/unreleased/<pr>.internal.md` and record the tracer/PR evidence

### Implementation Notes

- Guard A asserts `tmp_path.resolve() in git_ceiling_dirs()` — host-independent, fails on every host
  before the fixture change.
- Guard B clears `GIT_CEILING_DIRECTORIES`, re-applies the module pin through the same helper the
  fixture uses, then runs the real CLI seam (`_invoke(["backfill-runtime-state", "--json"])` with
  `_LOCATE` patched) and asserts `exit_code == 0` / `flipped == 1`; it `pytest.skip`s with a reason
  when no repository encloses the temp root, so it never reports a vacuous green.
- The append must preserve the harness value verbatim (git treats a leading empty entry as meaningful)
  and be idempotent, with `monkeypatch` restoring the previous value at teardown.
- No file outside `tests/cli/test_migrate_group_flags_4964.py` and the changelog fragment may change.

### Parallel Opportunities

- None: all subtasks touch one file except T005 (changelog), which is trivial and serialized after T004.

### Dependencies

- None (single-WP mission).

### Risks & Mitigations

- Guard B is skipped on CI (no enclosing repository) → Guard A is the always-on gate; the skip reason is
  explicit, never a silent pass.
- Appending to a shared environment variable leaks → `monkeypatch` teardown restores it; append-only,
  never replace.
