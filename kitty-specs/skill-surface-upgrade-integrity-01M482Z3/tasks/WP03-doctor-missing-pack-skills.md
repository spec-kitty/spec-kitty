---
work_package_id: WP03
title: Doctor reports and repairs missing pack skills
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- C-002
- C-005
- C-006
- SC-003
- SC-004
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: ccr-11788f1f-qu75jg
merge_target_branch: ccr-11788f1f-qu75jg
branch_strategy: Planning artifacts for this mission were generated on ccr-11788f1f-qu75jg. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-11788f1f-qu75jg unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surface-upgrade-integrity-01M482Z3
base_commit: 613a401c6902c0f89054c6b6705c9b77b96736f5
created_at: '2026-10-06T08:09:01.521535+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 1 - Doctor skill surface
history:
- at: '2026-10-06T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/pack_skill_drift.py
create_intent:
- tests/specify_cli/cli/commands/test_doctor_skills_missing_5801.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/pack_skill_drift.py
- src/specify_cli/cli/commands/_command_surface_doctor.py
- tests/specify_cli/skills/test_pack_skill_drift.py
- tests/specify_cli/cli/commands/test_doctor_skills.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- tests/cli_gate/test_doctor_modes.py
- tests/specify_cli/cli/commands/test_doctor_skills_missing_5801.py
- tests/specify_cli/cli/commands/test_doctor_slash_commands.py
- tests/specify_cli/cli/commands/test_doctor_tool_surfaces_config_error.py
- tests/specify_cli/cli/commands/test_doctor_json_not_in_project.py
- tests/specify_cli/skills/test_vibe_config.py
- tests/specify_cli/tool_surface/integration/**
- tests/architectural/test_json_contract_enumeration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Doctor reports and repairs missing pack skills

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log. Address every feedback item before completing.

---

## Objectives & Success Criteria

- FR-004: `doctor skills` reports a `missing` pack-skill finding per (agent, skill) when a skill is in force and either (a) no pack manifest entry exists for an agent that accepts skill files, or (b) the entry's installed file is absent; exit 1 (#5801).
- FR-005: `doctor skills --fix` installs missing pack skills via `project_pack_skills` (`src/specify_cli/skills/installer.py:1282`), lists projected paths in `repaired`, puts `OSError` into `repair_errors`, recomputes findings. `drift` is never repaired.
- FR-006: `tool_folders` list gets one `no_tool_folder` finding when none of the configured agents' root folders exist; one existing folder suffices; exit 1 when present.
- C-005/C-006: configured tools from `get_agent_dirs_for_project`; JSON contract additive only (see `contracts/doctor-skills-json.md`).
- NFR-001: T010 RED on planning base, GREEN at final commit.

## Context & Constraints

- `src/specify_cli/skills/pack_skill_drift.py`:
  - kinds `:59-63`; `find_pack_skill_findings` `:84-101` early-returns `()` when no pack entries; `current` (in-force names→hashes) computed via `_current_source_hashes` `:136-148`; `_entry_findings` `:110-121` maps absent file → `_installed_hash` None → no finding; test `test_absent_installed_file_is_not_drift` (`tests/specify_cli/skills/test_pack_skill_drift.py:~166`) pins the old behaviour — flip it to expect `missing`.
- In-force set: existing resolver `charter/activation/skill_preparation.py:272 establish_in_force_skill_ids` (gated by `pack_skills_matter`). Reuse; no second rule (C-006).
- Installable agents: reuse the installer's filter (`_installable_agent_keys` near `installer.py:~1260`) so tools without skill support are never `missing`.
- Doctor: `src/specify_cli/cli/commands/_command_surface_doctor.py` `_assemble_skills_payload` (`:643-700`): `--fix` today only `_repair_command_skill_state` + slash-command repair; `ok` from `not pack_findings`.
- Out of scope (C-003): `skills/verifier.py`, `upgrade/assessment.py`.
- User-owned files (C-002): `project_pack_skills` respects manifest ownership; do not write files directly.

## Branch Strategy

- **Planning base branch**: `ccr-11788f1f-qu75jg` · **Merge target branch**: `ccr-11788f1f-qu75jg`. Worktree from `lanes.json`; `spec-kitty agent action implement WP03 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first repro through `doctor skills`

- Create `tests/specify_cli/cli/commands/test_doctor_skills_missing_5801.py`, `@pytest.mark.regression`.
- Use the shared required_skills pack builder `tests/charter/skill_pack_support.py` (plus fixtures from `test_pack_skill_drift.py`) that build a project with a pack declaring a required skill. Ensure no projection happened (empty skills manifest).
- Invoke `doctor skills --json` via the CLI runner. Assert exit 1 and `pack_skills[0]["kind"] == "missing"`. Then `--fix`, assert the `SKILL.md` exists under the agent root and a re-run exits 0.
- Add the no-tool-folder case: configured `claude`+`codex`, both folders absent → exit 1, `tool_folders[0]["kind"] == "no_tool_folder"`; with one folder present → no such finding.
- Record RED in Activity Log; commit test alone first.

### Subtask T011 – `KIND_MISSING`

- Add `KIND_MISSING = "missing"`. Remove the early return so the per-(agent, skill) comparison runs when the manifest has no pack entries; keep the `unresolvable` branch.
- For each installable configured agent × each name in `current`: emit `missing` when no pack entry exists for that pair.
- In `_entry_findings`, distinguish absent file (→ `missing`) from unreadable (keep current handling).
- Update the docstring (`:84-90`) — it no longer delegates absence to the verifier.
- Unit tests in `test_pack_skill_drift.py`: never-installed → one finding per agent; absent file → `missing`; nothing in force → `()`; non-skill agent excluded.

### Subtask T012 – `--fix` projection

- In `_assemble_skills_payload`, when `fix` and any `missing` (or `stale`, if `project_pack_skills` refreshes it) finding: call `project_pack_skills(project_path)`; extend `repaired`; catch `OSError` → `repair_errors`; recompute findings. Report removed orphaned copies in the output.
- Negative test: a drifted copy is byte-identical after `--fix`.
- Extract a helper `_repair_pack_skills(...)` to keep complexity ≤15; test it directly.

### Subtask T013 – `no_tool_folder`

- Helper `_tool_folder_findings(project_path)`: agents via the doctor's existing `_configured_tool_keys` (`_command_surface_doctor.py:705`) and `agent_utils/directories.py:52 get_agent_dirs_for_project` (never the migration copy in `m_0_14_0_*`); if none of their root dirs exist → one finding listing the agents. Add `payload["tool_folders"]`; fold into `ok`. Human output: one line naming the agents and the remedy (`spec-kitty upgrade` recreates configured folders, `agent config remove` drops a tool).

### Subtask T014 – Goldens and focused tests

- Run and, where flipped by the new exit-1 paths, fix: `test_doctor_slash_commands.py`, `test_doctor_tool_surfaces_config_error.py`, `test_doctor_json_not_in_project.py`, `skills/test_vibe_config.py`, `tool_surface/integration/*`, `tests/architectural/test_json_contract_enumeration.py` (fixtures should create one configured folder rather than loosening the check).
- Update `test_doctor_cli_surface_golden.py`, `test_doctor_skills.py`, `tests/cli_gate/test_doctor_modes.py` additively (new `tool_folders: []` key; no existing field changes). Convert T010 to focused tests (drop `regression`).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/skills/ tests/specify_cli/cli/commands/test_doctor_skills*.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/cli_gate/test_doctor_modes.py -q
make test-fast
.venv/bin/ruff check src/specify_cli/skills src/specify_cli/cli/commands/_command_surface_doctor.py
.venv/bin/mypy src/specify_cli/skills/pack_skill_drift.py src/specify_cli/cli/commands/_command_surface_doctor.py
```

## Risks & Mitigations

- False positives for non-skill agents → reuse installer filter; test.
- `--fix` deleting orphaned copies → say so in output (spec edge case).
- Golden churn → additive only.

## Review Guidance

- RED→GREEN evidence; `missing` comes from the existing in-force resolver; no file writes outside `project_pack_skills`; drift untouched by `--fix`.

## Activity Log

- 2026-10-06T08:10:00Z – system – Prompt created.
