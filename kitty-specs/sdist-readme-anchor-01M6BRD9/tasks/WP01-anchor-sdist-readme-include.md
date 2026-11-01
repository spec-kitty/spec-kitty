---
work_package_id: WP01
title: Anchor the sdist README include, red first
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-002
planning_base_branch: issue-6926-sdist-readme-anchor
merge_target_branch: issue-6926-sdist-readme-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-6926-sdist-readme-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6926-sdist-readme-anchor unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-11-01T14:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/cross_cutting/packaging/
create_intent:
- docs/changelog/unreleased/6926-sdist-readme-anchor.fixed.md
execution_mode: code_change
model: ''
owned_files:
- pyproject.toml
- tests/cross_cutting/packaging/test_packaging_safety.py
- docs/changelog/unreleased/6926-sdist-readme-anchor.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Anchor the sdist README include, red first

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- The source distribution carries no member under `docs/`, `kitty-specs/` or `site/` (SC-001; 745 stray README / CHANGELOG members on the base).
- The root `README.md` and `CHANGELOG.md` still ship; every `packs/built-in/**` member is unchanged; nothing is added (FR-004, SC-002).
- A packaging-safety test reads the BUILT archive, fails on the base, passes after the fix (FR-003, C-005).
- `site/**` is in the sdist exclude list (FR-002).

## Context & Constraints

- Evidence: `kitty-specs/sdist-readme-anchor-01M6BRD9/research/code-grounding.md` (counts per tree, hatchling's `pathspec.GitIgnoreSpec` semantics, existing guards, PR #7004 collision).
- Charter Standing Order 4 (red first through the pre-existing entry point: the real sdist build) and 5 (non-vacuous check: positive control + planted self-test).
- CLAUDE.md "Pack Tiers": `packs/internal/` never ships; built-in content stays present. The existing internal-pack assertions stay untouched.
- Wheel contents must not change (C-001). No `site/` folder is created (C-004).
- **Do not touch** the `services/**` / `contracts/**` exclude lines or the comment above them (C-003; PR #7004 rewrites them).
- Changelog by fragment (`docs/changelog/unreleased/README.md`), never `CHANGELOG.md`.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-6926-sdist-readme-anchor
- **Merge target branch**: issue-6926-sdist-readme-anchor

> Populated automatically by `spec-kitty agent mission finalize-tasks`. This is a `single_branch` Mission: the WP runs in the repository root checkout on the write branch; there is no lane worktree.

Implementation command: `spec-kitty agent action implement WP01 --agent claude --mission sdist-readme-anchor-01M6BRD9`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first archive check

- **Purpose**: pin the defect on the built archive before fixing it.
- **Steps**:
  1. In `tests/cross_cutting/packaging/test_packaging_safety.py`, add a module constant naming the trees that must never ship in the sdist: `("docs/", "kitty-specs/", "site/")`.
  2. Add a pure helper `sdist_stray_tree_members(rooted: list[str]) -> list[str]` returning the members (already stripped of the `<name>-<version>/` root) under those trees, mirroring `service_binary_leaks` / `companion_leaks`.
  3. Add a planted self-test (no build): planted `docs/README.md`, `docs/changelog/CHANGELOG.md`, `kitty-specs/x/README.md`, `site/README.md`, `site/dist/index.html` are flagged; clean `README.md`, `CHANGELOG.md`, `src/charter/README.md`, `packs/built-in/missions/README.md`, `pins/README.md`, and a nested look-alike `src/specify_cli/docs/x.py` are not.
  4. Add the `@pytest.mark.slow` archive test using `_sdist_rooted_members(build_artifacts)`: assert the helper returns `[]` (message shows the count and the first 10), with a same-archive positive control: `README.md`, `CHANGELOG.md` and `pyproject.toml` at the root and a `src/specify_cli/` member present.
  5. Add a config-level twin (no build): `site/**` is in `[tool.hatch.build.targets.sdist].exclude`, and the include list has no bare (unanchored) `README.md` / `CHANGELOG.md` entry.
  6. Run `uv run --frozen pytest tests/cross_cutting/packaging/test_packaging_safety.py -q`. Expected: the archive test and the config twin FAIL on the base; the self-test passes. Record the red output, then commit the test alone.
- **Files**: `tests/cross_cutting/packaging/test_packaging_safety.py`.
- **Notes**: reuse the session `build_artifacts` fixture (NFR-001); keep each function under complexity 15.

### Subtask T002 – Anchor the include and exclude `site/**`

- **Steps**: in `pyproject.toml` `[tool.hatch.build.targets.sdist]`, change `"README.md"` → `"/README.md"` and `"CHANGELOG.md"` → `"/CHANGELOG.md"`, with a short comment (gitignore semantics: a leading `/` anchors to the root; #6926). Append `"site/**"` to `exclude` after `packages/**` with a comment citing ADR `2026-10-31-1` D-12. Nothing else changes.
- **Validation**: T001's tests go green.

### Subtask T003 – Before/after archive comparison

- **Steps**: build the sdist on the base commit and after the fix (`uv build --sdist -o <dir>`), strip the archive root, `comm` the sorted listings. Expected: 0 added; 745 removed (698 `kitty-specs/`, 33 `docs/`, 11 `tests/`, 2 `scripts/`, `packs/README.md`); 0 `packs/built-in/` removed; also compare `packs/built-in/**` bytes (sha256 of each member) between the two archives. Record the summary for the PR.

### Subtask T004 – Changelog fragment

- **Steps**: write `docs/changelog/unreleased/6926-sdist-readme-anchor.fixed.md` (rename to the PR number once known) with one entry in the changelog style; run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

### Subtask T005 – Verification

- `make test-fast`
- `uv run --frozen pytest tests/cross_cutting/packaging/ -q`
- `uv run --frozen pytest tests/architectural/test_pyproject_shape.py tests/ci/test_mission_status_api_build.py -q`
- `uv run --frozen ruff check <changed .py>`; `uv run --frozen ruff format --check --force-exclude <changed .py>`; `uv run --frozen mypy <changed .py>`

## Test Strategy

Required (FR-003). The archive test is the acceptance test; the self-test proves the helper non-vacuous; the config twin keeps `site/**` pinned even while no `site/` folder exists.

## Risks & Mitigations

- Vacuous pass → positive control on the same archive.
- A future include widening re-admits `docs/` → the archive test catches it.
- PR #7004 conflict → disjoint hunks; rebase whichever lands second.

## Review Guidance

- Confirm red on the base (run the new test against the base `pyproject.toml`) and green on the WP's final commit.
- Confirm the diff to `pyproject.toml` is exactly two include edits plus one exclude line (and comments).
- Confirm the before/after archive comparison: removal only, built-in unchanged.
- Confirm mypy and ruff are clean on the changed test file.

## Progress & Status

Progress lives in `status.events.jsonl`; use `spec-kitty agent tasks add-history WP01 --note "..."` and `spec-kitty agent tasks status`.
