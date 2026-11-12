---
work_package_id: WP05
title: Path-convention message frame (#7602)
dependencies:
- WP01
requirement_refs:
- FR-010
- NFR-002
- NFR-003
- C-006
planning_base_branch: fix/7546-settled-placement-surface
merge_target_branch: fix/7546-settled-placement-surface
branch_strategy: Planning artifacts for this mission were generated on fix/7546-settled-placement-surface. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7546-settled-placement-surface unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/validators/
create_intent:
- tests/specify_cli/acceptance/test_path_convention_frame_settled.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/validators/paths.py
- tests/specify_cli/acceptance/test_path_convention_frame_settled.py
role: implementer
tags: []
tracker_refs: []
---

# WP05 — Path-convention message frame (#7602)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

`accept` names a missing artifact-tagged path-convention deliverable relative to the checkout that
holds it (`kitty-specs/<slug>/contracts/`), not as `.worktrees/<slug>-coord/kitty-specs/<slug>/contracts/`
(FR-010, #7602). Build paths (`src/`, `tests/`) keep rendering relative to the project.

## Context

- `acceptance/__init__.py:≈1587` passes `placement_seam(...).read_dir(SPEC)` (the coordination copy
  after settlement) as `feature_dir` to `acceptance/summary_core.py::evaluate_path_conventions`, which
  calls `validators/paths.py::validate_mission_paths`. An artifact-tagged token resolves to
  `full_path = feature_dir / candidate` (≈ line 446) and a miss is rendered as
  `full_path.relative_to(project_root)` (≈ line 472) → `.worktrees/<slug>-coord/…`.
- The file named is correct; only the frame is wrong. Low severity.
- Use the WP01 kernel primitive `kernel.git_topology.checkout_root_containing` (if WP01 has landed) or
  render relative to the checkout containing `feature_dir`; never parse `.worktrees` names
  (`test_topology_inference_retired.py`).

Implement with: `spec-kitty agent action implement WP05 --agent claude --mission settled-placement-surface-01M78GR4`

### Subtask T017: Red

Create `tests/specify_cli/acceptance/test_path_convention_frame_settled.py`: build a project root with a
linked worktree (real `git worktree add`) whose `kitty-specs/<slug>/` lacks `contracts/`; call
`validate_mission_paths(feature_dir=<worktree mission dir>, project_root=<root>, …)` with the
path-convention config the existing tests use (see `tests/specify_cli/acceptance/test_missing_artifacts_from_config.py`
and `tests/agent/test_validators_unit.py` for the call shape) and assert the message names
`kitty-specs/<slug>/contracts/` and does not contain `.worktrees`. Also add one end-to-end case on the settled fixture that drives
`spec-kitty accept` (C-007: the pre-existing entry point), not only `validate_mission_paths`. Commit red:
`test(acceptance): pin the path-convention message frame on a coordination Mission (#7602)`.

### Subtask T018: Render relative to the holding checkout

In `validate_mission_paths`, for artifact-tagged candidates render `full_path` relative to the checkout
containing `feature_dir` — use WP01's `kernel.git_anchor.checkout_root_containing` (do not write
another walk) — and fall back to `project_root` when the walk returns nothing or `full_path` is not
under it. #3085a (`validators/paths.py:≈466-468`) requires the remediation to name the location
actually tested, and a bare `kitty-specs/<slug>/contracts/` is ambiguous from the repository root
checkout: so when the holding checkout is not the project root, name it too, e.g.
"`kitty-specs/<slug>/contracts/` (in `<holding checkout path>`)". Leave build-path rendering untouched. Keep it a small helper (≤ 15 complexity) with a
unit test.

### Subtask T019: Regression

Run `pytest tests/specify_cli/acceptance tests/agent/test_validators_unit.py tests/specify_cli/test_validate_mission_paths_single_caller.py tests/architectural/test_lifted_root_validate_mission_paths_single_caller.py -q`;
add a `single_branch` control (feature_dir under the root → unchanged message).

## Definition of Done

Red first; green after; the listed suites green; ruff/format/mypy clean; mark-status T017–T019 done.

## Risks

Message text consumers (tests asserting the old string) — update only those that encode the bug.

## Reviewer Guidance

Confirm only artifact-tagged misses changed and that no `.worktrees` string parsing was added.
