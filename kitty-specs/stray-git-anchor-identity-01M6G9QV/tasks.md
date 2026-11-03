# Work Packages: A stray `.git` name is not an identity refusal

**Inputs**: Design documents from `kitty-specs/stray-git-anchor-identity-01M6G9QV/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md
**Issue**: spec-kitty/spec-kitty#7084

**Tests**: the mission is a defect fix, so testing work is explicit (`DIRECTIVE_034`: a defect gets a
failing test through the pre-existing entry point before the fix).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into two work packages. Each is
independently deliverable and testable.

**Prompt Files**: `tasks/WP01-*.md`, `tasks/WP02-*.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks subtasks safe to parallelize (different files/concerns).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log snapshot is the
  sole completion authority.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Narrow the anchor predicate, red-first (Priority: P0)

**Goal**: `backfill_mission` mints an identity for a mission in a folder git holds nothing for, even
when an ancestor carries a `.git` entry that is not a repository, while every shape that can hide a
real tracked copy still refuses.
**Independent Test**: `uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py
tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py
tests/lanes/test_refinalize_mission_branch.py -q` is fully green, and the new tests were observed red
before the predicate changed.
**Prompt**: `/tasks/WP01-narrow-the-anchor-predicate.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-003

### Included Subtasks

T001 Write the red probe-level regression in `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`: a bare directory named `.git` above the temp root is *not* a refusal, with the anchor-shape control (a `.git` directory carrying `HEAD`, and the existing marker-file case) on the same fixture family.
T002 Write the red entry-point regression in `tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`: `backfill_mission` reports `wrote`, mints a fresh ULID and writes it, under the same stray-anchor shape.
T003 Reproduce and record the issue's own node red (`tests/lanes/test_refinalize_mission_branch.py::test_backfill_then_refinalize_keeps_mission_branch_byte_identical`) before the fix, and note that the skipping call is `backfill_mission`, not the refinalize.
T004 Implement `_is_repository_home` and narrow `_has_no_git_anchor` in `src/specify_cli/mission_metadata.py`; update the two docstrings that describe the refusal rule.
T005 Verify: the four targeted test files, `ruff check` and `mypy` on the changed module; record every command and its result.
T006 Half-fix proof: revert the predicate narrowing alone and confirm the new tests go red again, so the coverage depends on the change and not on the fixture.

### Implementation Notes

- Keep the existing ancestor loop; do not add a walk or a ceiling (C-003, in-flight PR #7082).
- `.git` *file* → anchor; `.git` *directory carrying `HEAD`* → anchor; `.git` *directory without
  `HEAD`* → not an anchor; unreadable → anchor (`OSError`, unchanged).
- The new tests must fail on unmodified `main` for the mission's reason (the refusal `reason`
  carrying `[TRACKED_META_UNAVAILABLE]`), not for an unrelated fixture error.

### Parallel Opportunities

- T001 and T002 touch different test files and can be written in parallel; T003 is read-only.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A fixture that leaves a *real* repository above the temp root would pass for the wrong reason →
  the stray anchor is a bare directory named `.git`, exactly the shape the host demonstrates.
- Over-widening → the anchor-shape control must stay red-capable; T006 proves it.

---

## Work Package WP02: Operator-facing changelog and upgrade-guide wording (Priority: P1)

**Goal**: the release notes and the upgrade guide say what is and is not refused, matching the
delivered behaviour.
**Independent Test**: `uv run --frozen python -m scripts.docs.check_changelog_style` and
`uv run --frozen python -m scripts.docs.check_spelling --pass unreleased` pass, and the guide's new
sentence names the same rule as the delivered predicate.
**Prompt**: `/tasks/WP02-changelog-and-guide-wording.md`
**Requirement Refs**: FR-001, FR-004, SC-002

### Included Subtasks

T007 Add `docs/changelog/unreleased/<pr>.fixed.md` — content only, US spelling, no `[Unreleased]` heading — naming the defect, the before/after and the issue.
T008 Add one sentence to `docs/guides/how-to/installation/upgrade-project.md` in the "If a Mission's `meta.json` is missing" section: a folder git does not track is minted normally, and the refusal only covers a repository git cannot read.
T009 Rename the fragment to the pull request number once the PR exists, and re-run the changelog style and spelling checks against the final name.

### Implementation Notes

- The fragment is a per-PR file; never edit `docs/changelog/CHANGELOG.md`.
- Wording must not promise more than the code does: a `.git` directory carrying `HEAD` still refuses.

### Parallel Opportunities

- T007 and T008 touch different files and can be drafted in parallel with WP01's implementation.

### Dependencies

- Describes WP01's delivered behaviour; T009 needs the pull request number, so it runs last.

### Risks & Mitigations

- `check_changelog_style` rejects the old `[Unreleased]` entry shape and British spellings →
  run both checks before opening the PR.
