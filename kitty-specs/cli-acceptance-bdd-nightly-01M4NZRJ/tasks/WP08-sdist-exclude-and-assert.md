---
work_package_id: WP08
title: sdist exclusion + packaging assertion
dependencies:
- WP02
- WP03
requirement_refs:
- FR-013
- C-004
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-acceptance-bdd-nightly-01M4NZRJ
base_commit: 9266188c42edfce7f0d10ebb93f7452ab4ae9460
created_at: '2026-10-11T19:01:17.385827+00:00'
subtasks:
- T024
- T025
phase: Phase 6 - Packaging
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/cross_cutting/packaging/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- pyproject.toml
- tests/cross_cutting/packaging/test_packaging_safety.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – sdist exclusion + packaging assertion

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Exclude the runner and the scenario corpus from the published sdist, and assert it.

Done when:
- `[tool.hatch.build.targets.sdist].exclude` in `pyproject.toml` lists `acceptance-jvm/**` and `tests/scenarios/**`.
- `tests/cross_cutting/packaging/test_packaging_safety.py` has a `@pytest.mark.slow` test asserting both trees are absent from the built sdist, paired with a same-fixture positive control (a `src/` package IS present).
- The wheel is unchanged (both trees are already outside the wheel allowlist — no wheel test change).

## Context & Constraints

- **Depends on WP02 + WP03**: both trees must exist so the built sdist non-vacuously exercises the exclusion (an exclusion that merely matches nothing proves nothing).
- **Current state** (research.md §3): the sdist `exclude` (pyproject ~L221–225) lists `.kittify/**`, `.kittify/active-mission`, `src/specify_cli/**/tests/**` — neither new tree. There is no generic sdist-exclude assertion yet; the nearest is `test_sdist_contains_no_kittify_paths`.
- **Test build mechanics** (research.md §5): the `build_artifacts` session fixture runs `python -m build --no-isolation` ~once/run (~1 min), shared across workers. Reuse it — do NOT trigger a second build. All packaging tests are `@pytest.mark.slow` + `integration`.
- Spec refs: FR-013, C-004.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

## Subtasks & Detailed Guidance

### Subtask T024 – Add the sdist exclusions

- **Purpose**: Keep the runner + scenarios out of the published source distribution (C-004).
- **Steps**: In `pyproject.toml`, add `"acceptance-jvm/**"` and `"tests/scenarios/**"` to `[tool.hatch.build.targets.sdist].exclude`. Keep the list ordering/style consistent; change nothing else in the (very hot) file.
- **Files**: `pyproject.toml`.

### Subtask T025 – Packaging assertion + positive control

- **Purpose**: Prove the exclusion works and is non-vacuous (FR-013).
- **Steps**: Add a `@pytest.mark.slow` (+ `integration`) test to `test_packaging_safety.py` using the existing `build_artifacts` fixture:
  - Open the built sdist (`tarfile.open(sdist_path, "r:gz")`, `getnames()` — mirror `test_sdist_contains_no_kittify_paths`).
  - Assert no member path contains `acceptance-jvm/` or `tests/scenarios/`.
  - **Positive control on the same fixture**: assert a known `src/` package path IS present in the sdist (mirror the `test_wheel_contains_templates` style, `assert present, "…"`), so the absence assertion cannot pass against an empty/broken archive.
- **Files**: `tests/cross_cutting/packaging/test_packaging_safety.py`.
- **Notes**: author red-first conceptually — before T024 the exclusion test would fail (the trees would be in the sdist). Reuse `build_artifacts`; do not build a second time.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest tests/cross_cutting/packaging/test_packaging_safety.py -q` (slow tier — it builds an sdist once). Confirm the new assertion + positive control pass and the existing packaging tests are unchanged-green.

## Risks & Mitigations

- **Second build cost** → reuse the `build_artifacts` session fixture, never a fresh build.
- **Vacuous absence** → the same-fixture positive control (src package present) guarantees the archive is real.
- **Hot pyproject conflict** → the sdist block is stable; keep the diff to the two added lines.

## Review Guidance

- Confirm both globs are excluded, the test asserts absence AND a positive control on the same built sdist, and the wheel tests are untouched.

## Progress & Status

- Record a note: `spec-kitty agent tasks add-history WP08 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP08 --to <status>`

## Activity Log

- 2026-10-11T19:06:55Z – claude – shell_pid=3156902 – T024: added acceptance-jvm/** and tests/scenarios/** to sdist exclude. T025: added slow+integration test_sdist_excludes_acceptance_runner_and_scenarios reusing build_artifacts fixture, asserting both trees absent plus a src/specify_cli positive control.
