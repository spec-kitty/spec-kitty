---
work_package_id: WP05
title: doctor skills/command-files converge and report leftovers
dependencies:
- WP01
- WP02
requirement_refs:
- FR-005
- FR-009
- FR-011
- SC-003
planning_base_branch: issue-7700-skill-surfaces-converge
merge_target_branch: issue-7700-skill-surfaces-converge
branch_strategy: Planning artifacts for this mission were generated on issue-7700-skill-surfaces-converge. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7700-skill-surfaces-converge unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surfaces-converge-01M7VRS0
base_commit: b242ee84fa8dff7016f4ca13d6290a96f2dd5f4f
created_at: '2026-11-20T09:12:52.945612+00:00'
subtasks:
- T023
- T024
- T025
- T026
- T027
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T07:00:00Z'
  actor: claude::planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/_command_surface_doctor.py
create_intent:
- tests/specify_cli/runtime/test_old_root_leftovers.py
- docs/changelog/unreleased/5281.fixed.md
- docs/changelog/unreleased/7723.added.md
execution_mode: code_change
owned_files:
- src/specify_cli/skills/command_installer.py
- src/specify_cli/runtime/doctor.py
- src/specify_cli/cli/commands/_command_surface_doctor.py
- tests/specify_cli/skills/test_crlf_skill_render_4998.py
- tests/specify_cli/runtime/test_old_root_leftovers.py
- docs/changelog/unreleased/5281.fixed.md
- docs/changelog/unreleased/7723.added.md
- tests/specify_cli/cli/commands/test_doctor_skills.py
- tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py
- tests/specify_cli/cli/commands/test_doctor_stated_empty_reports.py
- tests/specify_cli/tool_surface/integration/fixtures/doctor_skills_baseline.json
- src/specify_cli/tool_surface/contracts/migration-compatibility.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – doctor skills/command-files converge and report leftovers

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

- #5281: `command_installer.verify` reports `outdated` paths (on-disk hash == manifest hash, but != `canonical_digest(repo_root, command)`); `doctor skills --fix` treats `outdated` as a repair trigger and converges via the existing `install()` path (the one `doctor tool-surfaces --kind command-skill --fix` and `upgrade` already use). The strict xfail `test_doctor_skills_fix_converges_self_consistent_drift` flips to pass and its marker is removed; module docstring updated.
- #7723 (operator ruling Q2=A, report only): when an agent's resolved user-global root differs from its home mirror (`Path.home() / ".claude/commands"`, `Path.home() / ".claude/skills"`), `doctor command-files` and `doctor skills` list Spec Kitty-owned files there with a removal hint; nothing is written or deleted. Opt-in removal is follow-up #7758 (mention in the hint text is not required).
- Proof per file: ownership record (global inventory entry matching bytes), equality with today's render, a historical skill render (WP01), or — commands only — the #4609 canonical-predecessor version marker. Unproven files are not listed.
- With `CLAUDE_CONFIG_DIR` unset: output unchanged (positive control).

## Context & Constraints

- Plan IC-04 (#5281 half), IC-06; research R-5, R-6.
- `doctor command-files --json` emits a list of issue dicts (`agent, command, file, issue, severity`): add leftover rows with `severity: "info"` and `issue: "leftover copy under the previous user-global root"`; exit code stays driven by non-info issues (check `run_command_files`: today any issue → exit 1; change to ignore `info` rows for the exit code, documented in the changelog).
- `doctor skills --json`: add an additive key `old_root_leftovers: [paths]`; does not flip `ok`.

## Branch Strategy

Populated by finalize-tasks. Planning base and merge target: `issue-7700-skill-surfaces-converge` via the Mission branch `kitty/mission-skill-surfaces-converge-01M7VRS0`.

```bash
spec-kitty agent action implement WP05 --agent claude --mission skill-surfaces-converge-01M7VRS0
```

## Subtasks & Detailed Guidance

### Subtask T023 – Red

- Remove nothing yet: run the strict xfail (it XPASSes only after the fix). Red-first here = drop the `xfail` marker in its own commit (now failing), then fix.
- `tests/specify_cli/runtime/test_old_root_leftovers.py`: isolated HOME; seed `~/.claude/commands/spec-kitty.specify.md` with today's render bytes and `~/.claude/skills/spk-run-next/SKILL.md` with a historical render; plus an unproven `~/.claude/skills/spk-run-next/notes.md`; set `CLAUDE_CONFIG_DIR=tmp/cfg`. Assert both doctors list exactly the proven files, write nothing (snapshot the tree before/after), and with the variable unset list nothing.

### Subtask T024 – `outdated`

- `VerifyReport.outdated: list[str]`; in `_verify_entries`, for canonical command entries where `on_disk == entry.content_hash` compute `canonical_digest` once per command (cache per verify call) and append when different and not `None`.
- `_command_surface_doctor._repair_command_skill_state`: include `report.outdated` in the trigger; payload key `outdated`; `has_issues` counts it.

### Subtask T025 – Discovery

- `runtime/doctor.py`: `find_old_root_leftovers() -> list[LeftoverFile]` with `kind` (`command`/`skill`), `path`, `proof`. Old roots: for each agent in `AGENT_PROJECT_CONFIG_DIRS` whose resolved global command dir / skill root differs from `Path.home() / <project-relative dir>`, scan that home-mirror dir (non-recursive for commands; per skill dir for skills, only canonical or retired skill names). Never follow symlinks.

### Subtask T026 – Report

- Human output: a short section "Leftover copies under <old root> (Spec Kitty no longer reads them for this config)" listing paths and the hint `rm <paths>` (quote paths). JSON as above.

### Subtask T027 – Changelog

- `5281.fixed.md`, `7723.added.md` (mention #7758 as the follow-up).

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/skills/test_crlf_skill_render_4998.py tests/specify_cli/runtime/test_old_root_leftovers.py tests/specify_cli/skills/ tests/specify_cli/runtime/ tests/specify_cli/cli/commands/ -k "doctor or skill or command_file"
make test-fast
```

## Risks & Mitigations

- `canonical_digest` renders templates: cache per verify call to keep doctor fast.
- `tests/specify_cli/cli/commands` is out-of-matrix (nightly only): run the doctor tests there locally.

## Review Guidance

- The xfail marker is gone and the test passes; leftover listing is proven-only and write-free.
