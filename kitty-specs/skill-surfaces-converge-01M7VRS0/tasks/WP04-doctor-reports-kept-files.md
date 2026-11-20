---
work_package_id: WP04
title: doctor tool-surfaces reports kept files
dependencies:
- WP03
requirement_refs:
- FR-003
- FR-004
- FR-012
- SC-002
planning_base_branch: issue-7700-skill-surfaces-converge
merge_target_branch: issue-7700-skill-surfaces-converge
branch_strategy: Planning artifacts for this mission were generated on issue-7700-skill-surfaces-converge. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7700-skill-surfaces-converge unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surfaces-converge-01M7VRS0
base_commit: a5b656b3833684a33e32bb434378bec88161037a
created_at: '2026-11-20T10:28:12.580320+00:00'
subtasks:
- T018
- T019
- T020
- T021
- T022
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T07:00:00Z'
  actor: claude::planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/
create_intent:
- tests/specify_cli/tool_surface/test_global_skill_kept_findings.py
- docs/changelog/unreleased/5983.added.md
execution_mode: code_change
owned_files:
- src/specify_cli/tool_surface/service.py
- src/specify_cli/tool_surface/findings.py
- src/specify_cli/tool_surface/repair.py
- tests/specify_cli/tool_surface/test_global_skill_kept_findings.py
- docs/changelog/unreleased/5983.added.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – doctor tool-surfaces reports kept files

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## Review Feedback

Check `review_ref` in the event log. Address every item before handing back.

## Objectives & Success Criteria

- `spec-kitty doctor tool-surfaces [--json]` lists every kept canonical global skill file (`global-skill-kept-stale`) and every kept edited retired copy (`retired-skill-kept-edited`), severity `warning`, each with `path`, a message naming the reason, and a `repair_command`/remedy line (e.g. "review, then remove the file and run any spec-kitty command to reinstall it"). Nothing is written by the report.
- `--fix` output does not read as convergence for a surface it skipped: the skipped project charter-skill surface (#2527 shape, a file that is neither proven nor consented) is reported with its reason.
- Finding codes are append-only public JSON API (`findings.py` module docstring).

## Context & Constraints

- Plan IC-03; spec FR-003, FR-004, FR-012; ruling #7700 (b), #5983.
- Data comes from WP03's `kept_global_skill_files(assess_global_agent_skills(selection=None))` — read-only assessment, no apply.
- Respect `--tool`/`--kind` filters: global findings belong to kind `charter-skill`; attach `tool_key` from the agent whose global root contains the path (several agents may share `~/.agents/skills`: then `tool_key=None`).

## Branch Strategy

Populated by finalize-tasks. Planning base and merge target: `issue-7700-skill-surfaces-converge` via the Mission branch `kitty/mission-skill-surfaces-converge-01M7VRS0`.

```bash
spec-kitty agent action implement WP04 --agent claude --mission skill-surfaces-converge-01M7VRS0
```

## Subtasks & Detailed Guidance

### Subtask T018 – Red tests

`tests/specify_cli/tool_surface/test_global_skill_kept_findings.py` (isolated HOME, project from `spec-kitty init` helper or the existing tool_surface test fixtures — check `tests/specify_cli/tool_surface/integration/` for a project fixture):
1. edited canonical global skill → `doctor tool-surfaces --json` has one `global-skill-kept-stale` finding with that path; file bytes unchanged.
2. edited retired copy → `retired-skill-kept-edited` finding.
3. clean install → no such findings (positive control).
4. `--kind command-skill` filter → no global skill findings.
5. #2527: project managed file edited by the user (not historical) under `--fix` → the skipped surface carries a reason (assert on the JSON field you add, e.g. `repair.skipped_reasons`).

### Subtask T019 – Codes

- `GLOBAL_SKILL_KEPT_STALE = "global-skill-kept-stale"`, `RETIRED_SKILL_KEPT_EDITED = "retired-skill-kept-edited"` in `findings.py`; if there is a schema contract under `src/specify_cli/tool_surface/contracts/`, extend it additively.

### Subtask T020 – Wire into `run_tool_surfaces`

- After `collect` (and after the refreshed collect under `--fix`), append the global findings to the report (a small helper `_global_skill_findings(kinds, tool_filter)` in `service.py`). Keep `report.ok` semantics consistent with other warnings (check `status.py`'s rule; warnings do not flip `ok` today — keep it so).

### Subtask T021 – Skipped reasons

- In the repair result, carry the disposition reason for each skipped surface (additive JSON key). Locate where `RepairResult.skipped` is built for managed skills (`providers/managed_skills.py::_repair_prepared`) — that file is owned by WP06; if a change there is needed, coordinate: prefer deriving the reason in `repair.py`/`service.py` from the assessment dispositions. Record any out-of-map edit with a one-line rationale.

### Subtask T022 – Changelog

- `5983.added.md`.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/tool_surface/
make test-fast
```

## Risks & Mitigations

- Doctor must not apply global assets as a side effect beyond today's behaviour: use the assessor only.

## Review Guidance

- Codes are kebab-case and documented; JSON additions are additive only.
