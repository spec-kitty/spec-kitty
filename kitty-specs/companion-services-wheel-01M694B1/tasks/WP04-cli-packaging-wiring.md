---
work_package_id: WP04
title: CLI packaging wiring and version lock
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-010
- C-001
- SC-003
planning_base_branch: companion-services-wheel
merge_target_branch: companion-services-wheel
branch_strategy: Planning artifacts for this mission were generated on companion-services-wheel. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into companion-services-wheel unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 3 - Stories
history:
- at: '2026-10-31T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: pyproject.toml
create_intent:
- tests/release/test_validate_release_companion.py
- tests/cross_cutting/packaging/test_companion_version_lock.py
execution_mode: code_change
model: ''
owned_files:
- pyproject.toml
- uv.lock
- scripts/release/validate_release.py
- tests/release/test_validate_release_companion.py
- tests/cross_cutting/packaging/test_packaging_safety.py
- tests/cross_cutting/packaging/test_companion_version_lock.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – CLI packaging wiring and version lock

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: pyproject.toml`.

---

## Branch Strategy

- Planning base and final merge target: `companion-services-wheel`.
- Topology `single_branch`: no lane worktree. Work in the repository root checkout on `companion-services-wheel`.
- Start with `spec-kitty agent action implement WP04 --agent claude --mission companion-services-wheel-01M694B1`.


## Objective

Make `pip install "spec-kitty-cli[services]"` resolve the companion of exactly the CLI's version (FR-008), lock it through a uv workspace member
(Decision Moment `01M694GPQYVGRKCF3B582FWQ1Y`, ruled A), keep the main wheel and sdist free of companion files (FR-010 main half, C-001, C-005),
and enforce the three-place version lock in a test and in `validate_release.py`.

## Subtasks

### T012 — Red tests

`tests/cross_cutting/packaging/test_companion_version_lock.py` (fast, reads TOML only):
1. `packages/spec-kitty-services/pyproject.toml` `[project].version` == root `[project].version`.
2. Root `[project.optional-dependencies].services` == `["spec-kitty-services==<root version>"]` exactly.
3. Root `[tool.uv.workspace].members` contains `packages/spec-kitty-services`; `[tool.uv.sources]."spec-kitty-services"` == `{workspace = true}` and
   no other `[tool.uv.sources]` entry exists (the clarification allows only the first-party member).
4. Root sdist `exclude` contains `packages/**`.
5. `uv.lock` has a `spec-kitty-services` package whose source is the workspace path (not a registry).

### T013 — Root pyproject + lock

Add the extra (with a comment citing the ADR amendment), `[tool.uv.workspace] members = ["packages/spec-kitty-services"]`,
`[tool.uv.sources] spec-kitty-services = { workspace = true }`, sdist exclude `"packages/**"` (comment: the bare README include is gitignore-style).
Run `uv lock` and check the diff touches only the new member and the CLI's `provides-extras`/requires-dist. Run `uv sync --frozen --all-extras` to prove the
editable install of the companion works through the in-tree backend.

### T014 — `validate_release.py`

Add a check (both modes) that the three versions agree; on mismatch raise `ReleaseValidatorError` naming each file and value. Tests in
`tests/release/test_validate_release_companion.py` on a tmp repo: agree → ok; companion version differs → error; extra pin differs → error;
companion pyproject absent → error. Follow the module's existing structure (look at how `load_pyproject_version` and the report work).

### T015 — Packaging-safety guard

In `tests/cross_cutting/packaging/test_packaging_safety.py` extend the existing archive checks: no member under `spec_kitty_services/` in the wheel
and no `packages/` member in the sdist. These tests build real artifacts (slow); add a non-vacuity helper test like `test_service_binary_helper_flags_planted_members`.

## Validation

- `uv run --frozen pytest tests/cross_cutting/packaging/ tests/release/ -q` (includes the slow build-based tests).
- `uv run --frozen pytest tests/architectural/test_pyproject_shape.py tests/architectural/test_shared_package_boundary.py -q`.
- ruff/mypy on changed Python files.

## Commit discipline

- The red test is its own commit **before** the implementation commit (charter ATDD-First, C-011).
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier.
