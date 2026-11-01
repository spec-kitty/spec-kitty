# Work Packages: Anchor the sdist README include to the repository root

**Inputs**: Design documents from `kitty-specs/sdist-readme-anchor-01M6BRD9/`
**Prerequisites**: plan.md, spec.md, research.md, research/code-grounding.md, quickstart.md

**Tests**: Required. The spec (FR-003, C-005) demands a red-first archive test.

**Organization**: One work package. The red-first archive test and the fix are one atomic deliverable (C-005 needs the test committed failing, then turned green in the same package); splitting them would leave one package permanently red.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Anchor the sdist README include, red first (Priority: P1)

**Goal**: The source distribution ships the root `README.md` / `CHANGELOG.md` only, excludes `site/**`, and a packaging-safety test on the built archive proves it.
**Independent Test**: `uv run --frozen pytest tests/cross_cutting/packaging/test_packaging_safety.py -q` is red on the base for the new archive test and green after the fix.
**Prompt**: `tasks/WP01-anchor-sdist-readme-include.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003, C-004, C-005, SC-001, SC-002

### Included Subtasks

T001 Add the archive check (helper, planted self-test, built-archive test, `site/**` config twin) to `tests/cross_cutting/packaging/test_packaging_safety.py`; run it red on the base and commit it (WP01)
T002 Anchor `README.md` / `CHANGELOG.md` to `/README.md` / `/CHANGELOG.md` and add `site/**` to the sdist exclude in `pyproject.toml` (WP01)
T003 Compare the before/after sdist listings: removal only, `packs/built-in/**` unchanged, root `README.md` / `CHANGELOG.md` present (WP01)
T004 Add the changelog fragment under `docs/changelog/unreleased/` (WP01)
T005 Run the targeted suites, the specific architectural gate, lint, format and mypy on changed files (WP01)

### Implementation Notes

- T001 first, committed red; then T002 in its own commit.
- Do not touch the `services/**` / `contracts/**` lines or their comment (PR #7004 owns them).

### Parallel Opportunities

- None; the package is sequential by design (red, then green).

### Dependencies

- None (starting package).

### Risks & Mitigations

- Vacuous pass on an empty archive → same-archive positive control.
- Rebase conflict with PR #7004 → disjoint hunks.
