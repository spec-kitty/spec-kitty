---
work_package_id: WP02
title: Project and provider planners, rechecks and latent Windows sites
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-011
- C-006
- SC-004
planning_base_branch: issue-4927-host-aware-mode-predicate
merge_target_branch: issue-4927-host-aware-mode-predicate
branch_strategy: Planning artifacts for this mission were generated on issue-4927-host-aware-mode-predicate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4927-host-aware-mode-predicate unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-host-aware-mode-predicate-01M7X6B1
base_commit: 4528a142777e108274eb68fb3575f07c87cf1b10
created_at: '2026-11-21T04:24:00.224281+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Remaining planners
history:
- at: '2026-11-20T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- tests/specify_cli/tool_surface/test_latent_windows_mode_sites.py
- tests/specify_cli/skills/test_project_skill_windows_write_bit.py
- tests/charter/test_charter_yaml_host_seam.py
execution_mode: code_change
owned_files:
- src/specify_cli/skills/command_installer.py
- src/specify_cli/skills/installer.py
- src/specify_cli/skills/manifest.py
- src/specify_cli/tool_surface/providers/managed_skills.py
- src/specify_cli/tool_surface/providers/agent_profiles.py
- src/specify_cli/tool_surface/providers/native_config.py
- src/specify_cli/tool_surface/bundles/projection.py
- src/charter/activation/charter_yaml_io.py
- tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py
- tests/specify_cli/skills/test_installer.py
- tests/specify_cli/tool_surface/test_latent_windows_mode_sites.py
- tests/specify_cli/skills/test_project_skill_windows_write_bit.py
- tests/charter/test_charter_yaml_host_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Project and provider planners, rechecks and latent Windows sites

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission host-aware-mode-predicate-01M7X6B1`). Address every item and record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Objectives & Success Criteria

- Every remaining observed-vs-planned mode decision and recheck in `skills/` and `tool_surface/` uses WP01's `effect_action` / `mode_equivalent` / `state_equivalent` / `modes_equivalent` (FR-002, FR-006).
- `windows_dir_mode_only_divergence` is deleted; its three callers are re-pointed (FR-009).
- Windows read-only drift on project skills converges (FR-005); this replaces "ignore Windows file modes" (C-006).
- Latent sites accept host-equivalent modes on emulated Windows: bundle staging + finalize, agent-profile sibling directory, native-config directory postcondition (FR-007).
- Observed-vs-observed guards and planned-vs-planned conflict checks stay exact on both hosts (FR-008).
- `charter_yaml_io.py` uses the `is_windows` seam (FR-011).

## Context & Constraints

- WP01 delivered `tests/specify_cli/tool_surface/ntfs_emulation.py` (`emulate_ntfs`, `ntfs_host`, `posix_host`) and the predicates in `src/specify_cli/tool_surface/operations.py`. Reuse them; do not redefine emulation.
- Research R-2, R-4 list every site and its adjudication; the table below is authoritative for this WP.
- `charter` may import `kernel.paths` only (layer chain); it must not import `specify_cli`.
- Red first: commit T006 tests alone, show red, then implement.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-4927-host-aware-mode-predicate`
- **Merge target branch**: `issue-4927-host-aware-mode-predicate`

Implement with: `spec-kitty agent action implement WP02 --agent claude --mission host-aware-mode-predicate-01M7X6B1`

## Site table (base line numbers on main 873ca367)

| Site | Kind | Change |
|---|---|---|
| `skills/command_installer.py` `_CommandBatch.effect` ~:850-861 | planner ladder | `action = effect_action(before, after)`; `if action is None: return` |
| `skills/command_installer.py` `windows_dir_mode_only_divergence` ~:713-753 + `_MODE_RELAXABLE_KINDS` | old authority | delete |
| `skills/installer.py` project ladder ~:562-584 | planner ladder | keep the `absent/absent` early return; `action = effect_action(before, replace(after-or-before mtime normalized?))` — see T007 |
| `skills/installer.py` `_command_parent_receipts` ~:480 | stamp recheck | `state_equivalent(item.state, effect.after)` |
| `skills/installer.py` `_apply_project_skill_write` symlink chmod ~:1040 | apply-side | `if not modes_equivalent("symlink", observed, after.mode)` |
| `skills/installer.py` `current != effect.before` ~:1029 | guard | stays exact |
| `skills/manifest.py` ~:179 | apply-side | `modes_equivalent("file", ...)` |
| `tool_surface/providers/managed_skills.py` ~:168 | stamp recheck | `if not state_equivalent(state, effect.after)` (drop the manual mtime normalize: `state_equivalent` ignores mtime by default — confirm the old normalize was mtime only) |
| `tool_surface/bundles/projection.py` `_stage_effect` ~:894-903 | planner ladder | `effect_action(before, after)`; keep "replace" when `before.kind != "file"` (it already matches `effect_action` since after is a file) |
| `tool_surface/bundles/projection.py` `_recheck_selected` ~:162, ~:165 | stamp substitution | substitute the OBSERVED mode when `mode_equivalent(current.state, planned)` so `same_observation` stays exact for every other field |
| `tool_surface/bundles/projection.py` finalize ~:1096 | stamp postcondition | compare `final` against `created` with `state=effect.after` only after the same equivalence substitution |
| `tool_surface/bundles/projection.py` `same_observation`, ~:1089 fstat triple, ~:1030 precondition | guards | stay exact |
| `tool_surface/bundles/projection.py` ~:850 staged member conflict | planned vs planned | stays exact |
| `tool_surface/providers/agent_profiles.py` `_sibling_created_planned_dir` ~:835 | planner acceptance | `mode_equivalent(observed, planned)` |
| `tool_surface/providers/agent_profiles.py` ~:846 `observed != effect.before` | guard | stays exact |
| `tool_surface/providers/native_config.py` `_directory_postcondition_holds` ~:361 | stamp postcondition | `state_equivalent(presence_state(observed), effect.after)` (check `presence_state` field shape first) |
| `charter/activation/charter_yaml_io.py` ~:222 | campsite | `not kernel_paths.is_windows()` instead of `os.name != "nt"` |

## Subtasks & Detailed Guidance

### Subtask T006 – Red tests

- `tests/specify_cli/skills/test_project_skill_windows_write_bit.py` (new): with `ntfs_host`, install project skills (reuse the fixtures in `tests/specify_cli/skills/test_installer.py` around :1646-1908 — import helpers rather than copy), then make one managed skill file read-only → assessment plans exactly one `chmod`; apply; reassess → none. And: a converged project under emulation plans no chmod (this is green already via the old helper; keep it as a ratchet).
- `tests/specify_cli/tool_surface/test_latent_windows_mode_sites.py` (new), each with a POSIX twin:
  - bundles: build a staged bundle (see `tests/specify_cli/tool_surface/bundles/test_projection.py` fixtures), write it once on POSIX-host-in-emulation or apply under emulation, reassess → no `chmod`; finalize of a created directory does not raise `Staged directory changed during finalization`.
  - `_sibling_created_planned_dir(FileState("absent"), FileState("directory", mode=0o777, mtime_ns=1), FileState("directory", mode=0o755))` → True under Windows emulation, False on POSIX. Plus an integration through `_write_profile_effect` where the dir already exists at 0o777 under emulation.
  - native_config `_directory_postcondition_holds` for a created directory under emulation → True.
- Re-pins: in `test_managed_skills_host_aware.py` and `test_installer.py`, any test asserting that a Windows file mode-only divergence is ignored wholesale (e.g. `test_helper_windows_only_dir_mode` and tests importing `windows_dir_mode_only_divergence`) is updated to the write-bit rule and to the new names. Judge each test (charter Standing Order #4): stale pins → re-pin to the new ruling; never delete a valid assertion.
- `tests/charter/test_charter_yaml_host_seam.py` (new): patch `kernel.paths.is_windows` to True and make the written file's mode differ from `prepared.mode` (e.g. patch the stat the writer reads, or chmod after write via a hook) → no `precondition_changed` refusal; with False → refusal. If exercising the writer is heavy, look at `tests/charter/test_charter_yaml_write_refusal.py` for an existing harness.
- Commit red tests alone; record the red run.

### Subtask T007 – Unify ladders

- `command_installer._CommandBatch.effect`: replace the if/elif chain with `effect_action`. Behaviour is unchanged on POSIX (the old chain lacked `retarget`; command outputs are never symlinks — confirm with grep; if `retarget` could now appear, it is the validator's existing expectation anyway, so it is strictly more correct).
- `installer` project ladder: today it normalizes `mtime_ns` before the old helper because `after` from `_expected_project_entries` carries no mtime. `effect_action` does not compare mtime (it compares kind, sha256, target, mode), so no normalization is needed. Keep the docstring note concise.

### Subtask T008 – Stamp rechecks + delete the old helper

- Re-point `installer._command_parent_receipts` and `managed_skills._recheck_command_completion` to `state_equivalent`.
- Delete `windows_dir_mode_only_divergence` and `_MODE_RELAXABLE_KINDS`; remove imports (`skills/installer.py:53`, `tool_surface/providers/managed_skills.py:51`). `git grep windows_dir_mode_only_divergence` must return only the changelog/ADR text, if any.

### Subtask T009 – Latent sites

- projection `_recheck_selected`: for a parent path in `run.parents` it currently forces `original.state.mode = effect.after.mode`; for a written path it builds `replace(effect.after, mtime_ns=written.state.mtime_ns)`. After observing `current`, if `mode_equivalent(current.state, <that planned state>)`, carry `current.state.mode` into `original` before `same_observation`. Extract a small helper `_equivalent_stamp(planned: FileState, observed: FileState) -> FileState` (returns planned with observed mode when equivalent) and use it at :162, :165 and :1096. Unit-test the helper directly (Sonar new-code coverage).
- agent_profiles and native_config per the table.

### Subtask T010 – Apply-side chmods and campsite

- `installer._apply_project_skill_write` symlink branch and `skills/manifest.py` chmod-if-differs via `modes_equivalent`.
- `charter_yaml_io.py`: `from kernel import paths as kernel_paths` (check existing imports; module-attribute call), replace `os.name != "nt"`. Drop `import os` only if unused.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/skills/test_project_skill_windows_write_bit.py tests/specify_cli/tool_surface/test_latent_windows_mode_sites.py tests/charter/test_charter_yaml_host_seam.py -q
.venv/bin/python -m pytest tests/specify_cli/tool_surface tests/specify_cli/skills tests/specify_cli/runtime tests/runtime -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/charter/test_charter_yaml_write_refusal.py tests/upgrade/test_preview_oracle.py tests/architectural/_no_follow_symlinks_apply_scan.py tests/architectural/test_no_follow_symlinks_apply_ban.py tests/architectural/test_os_detection_ban.py tests/architectural/test_layer_rules.py -q
make test-fast
.venv/bin/ruff check <changed> && .venv/bin/ruff format --check --force-exclude <changed>
.venv/bin/mypy --explicit-package-bases <changed src files>
```

## Risks & Mitigations

- **Semantic change** on Windows project skills (C-006): disclosed in WP03's changelog fragment.
- **Projection substitution** could mask a real non-mode change if done wrong: the helper only swaps `mode`, never other fields; test a sha256 change still refuses under emulation.
- **Guard over-reach** (the #4805 lesson): do not route `same_observation`, the fstat triple, `current != effect.before` or `check_assets` through the predicate.

## Review Guidance

- Red→green for T006; every re-pinned test justified in the history note.
- `git grep -n "windows_dir_mode_only_divergence"` empty in `src/` and `tests/`.
- Guards listed above are still exact (read each line).
- ruff/format/mypy clean.

## Progress & Status

Use `spec-kitty agent tasks add-history WP02 --note "..."` and `spec-kitty agent tasks move-task WP02 --to <status>`.
