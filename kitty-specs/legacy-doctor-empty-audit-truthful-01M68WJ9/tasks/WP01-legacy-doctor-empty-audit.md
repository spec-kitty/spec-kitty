---
work_package_id: WP01
title: Name what the legacy doctor audits did not check
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6891-legacy-doctor-empty-audit-truthful
merge_target_branch: issue-6891-legacy-doctor-empty-audit-truthful
branch_strategy: Planning artifacts for this mission were generated on issue-6891-legacy-doctor-empty-audit-truthful. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6891-legacy-doctor-empty-audit-truthful unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-legacy-doctor-empty-audit-truthful-01M68WJ9
base_commit: a17eeb1b26d4d5df9b87d6094d0d848c96ab0cf8
created_at: '2026-10-31T11:52:42.855204+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 1 - Truthful summaries
history:
- at: '2026-10-31T11:55:00Z'
  actor: claude
  action: created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/_command_surface_doctor.py
- tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py
- tests/specify_cli/cli/commands/test_doctor_slash_commands.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6891'
---

# Work Package Prompt: WP01 – Name what the legacy doctor audits did not check

## ⚡ Do This First: Load Agent Profile

Load the assigned profile before anything else:
`spec-kitty agent profile show python-pedro`, then
`spec-kitty charter context --action implement`. Act within that profile's
boundaries for the whole WP; the review runs under `reviewer-renata`.

## Objective

In a project whose `.kittify/config.yaml` has **no** `agents.available` list (the
#6501 every-agent fallback), `spec-kitty doctor skills` prints
`Command Skills: all manifest entries healthy (0 file(s))` and
`spec-kitty doctor tool-surfaces` prints
`Tool Surfaces: all surfaces healthy (0 checked)` — both exit 0, both asserting
health over a set they never examined (issue #6891).

Make an empty examined set say the truth it can prove: the project states no
agent list, so the CLI cannot tell which surfaces to verify, and nothing was
checked. Change **only** the summary text and the plumbing that gets the already
loaded `AgentConfig` to it. Exit codes, `--json` key sets, audit coverage and
`--fix` behaviour do not change.

Spec: FR-001…FR-006, NFR-001…NFR-003, C-001…C-005.

## Context

- The defect is reproduced on `origin/main` `6f73b2a98e`; transcripts are in
  `../research/repro-1.txt` … `repro-5.txt`, the code survey in `../research.md`,
  and the `load_agent_config` baseline in `../research/load-counts.txt`
  (`doctor skills` 3 calls, `doctor tool-surfaces` 1).
- Both summaries live in `src/specify_cli/cli/commands/_command_surface_doctor.py`:
  `_print_command_skill_report` (gated on `payload["ok"]` alone) and
  `_print_tool_surface_human` (gated on `report.ok and not report.findings`).
- "Nothing examined" is already computable and must not be redefined:
  - skills: the fused report is clean **and** `len(manifest.entries) == 0`.
    `command_installer.verify()` scans manifest entries *and* on-disk canonical /
    legacy folders regardless of config, so any on-disk leftover sets
    `ok=False` — `ok && entries == 0` therefore means "nothing was examined".
    `research/repro-3.txt` proves the on-disk half still fires in the legacy shape.
  - tool-surfaces: `report.summary.surfaces == 0` with `report.ok`.
- The cause is `AgentConfig.explicit_agent_list` (`False` = legacy no-list,
  #6501; `True` with `available == []` = stated empty, #6494). Do **not** add a
  second predicate: #6493 / PR #6894 owns the stated-empty shape and adds
  `no_cli_managed_agents(config)`; this WP must read `explicit_agent_list` and
  must not change the stated-empty decisions.
- **Do not add a config read.** `_load_command_skill_state` already loads the
  `AgentConfig`; carry that same object as a seventh element of the state tuple
  (`_SkillState` and its unpack in `_assemble_skills_payload`). For
  `doctor tool-surfaces`, `_configured_tool_keys_or_exit` already loads the
  config: add a sibling that returns it so `run_tool_surfaces_audit` can pass
  the answer to the printer, keeping `_configured_tool_keys` for
  `_tool_folder_findings`. NFR-002 is a call-count test, not a refactor.
- **Order matters in `_assemble_skills_payload`.** `payload["ok"]` is set twice —
  once by `_command_skill_payload`, then again after the fused slash-command,
  pack-skill and tool-folder checks. Attach the truthful note only after the
  **final** `ok` computation, and only when `ok` is true; otherwise a project
  with a real slash-command gap would lose its findings behind a
  "nothing to check" line.
- **`--json` contract.** The reason must ride a payload key listed in
  `_HUMAN_ONLY_KEYS` (stripped from the JSON envelope by `run_skills_audit`), so
  the emitted key set is byte-identical to today's. `doctor tool-surfaces` JSON
  comes from `outcome.to_json()`; do not touch it.

## Wording (C-002: name the state, prescribe nothing)

Summary line, one shared constant for the clause:

```
Command Skills: no stated agent list (every agent is available) — nothing to check
  ! 0 manifest entries and no agent surface were examined. .kittify/config.yaml states
    no agents.available list, so the CLI cannot tell which surfaces to verify.
```

```
Tool Surfaces: no stated agent list (every agent is available) — nothing to check
  ! 0 surfaces were examined. .kittify/config.yaml states no agents.available list, so
    the CLI cannot tell which surfaces to verify.
```

- Never print `healthy` in this branch; colour the summary yellow, not green.
- Do not suggest `agent config add` / `upgrade` / installing surfaces: for a
  project whose surfaces a plugin supplies that is #6493's duplicate-surface harm.
- `--fix` in this shape repairs nothing and must not claim a repair.

## Tests (red first, through the production entry point)

New file `tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py`,
`pytestmark = [pytest.mark.unit, pytest.mark.fast]`, `CliRunner()` on
`specify_cli.cli.commands.doctor.app`; patch `locate_project_root` on
`specify_cli.cli.commands.doctor` for `skills` and on
`specify_cli.cli.commands._command_surface_doctor` for `tool-surfaces` (the
existing `test_doctor_tool_surfaces_config_error.py` shows the seam).

1. **Red (FR-001, SC-001)**: legacy config (`agents: {auto_commit: true}`) +
   a real `.claude/commands` tree → `doctor skills` exits 0, output contains
   `no stated agent list` and `nothing to check`, and does **not** contain
   `all manifest entries healthy`.
2. **Red (FR-002, SC-001)**: same fixture → `doctor tool-surfaces` exits 0, same
   assertions against `all surfaces healthy`.
3. **Positive control (FR-004, SC-002)**: same fixture *family* with
   `agents.available: [codex]` and `command_installer.install(tmp_path, "codex")`
   → `all manifest entries healthy` with a non-zero count; and after deleting
   `.agents/skills/spec-kitty-tasks/SKILL.md` → exit 1 with the gap named. This is
   the same-fixture control the non-vacuity tactic requires: the assertion "no
   health claim" is paired with an assertion that the probe *can* see a health
   claim and a real finding.
4. **Legacy with a real finding (C-001 no regression)**: legacy config + an
   unrecorded `.agents/skills/spec-kitty-plan/SKILL.md` collision → still exits 1
   with the collision named (`research/repro-3.txt`); the truthful line must not
   replace it.
5. **JSON freeze (FR-005, SC-003)**: `doctor skills --json` on the legacy fixture
   → `set(payload) == ` the key set captured from `origin/main` (list them
   literally in the test); `doctor tool-surfaces --json` → unchanged top-level
   keys. Also assert the human-only reason key is absent from the JSON.
6. **Call count (FR-006, NFR-002)**: wrap `specify_cli.core.agent_config.load_agent_config`
   with a counter and assert `doctor skills` = 3 and `doctor tool-surfaces` = 1 on
   the legacy fixture (baseline in `../research/load-counts.txt`).
7. **`--fix` (spec edge case, T010)**: on the legacy fixture, `doctor skills --fix`
   exits 0, prints the same truthful line, prints no `Repaired`, and leaves the
   tree byte-identical (snapshot before/after).
8. **`command-files` ratchet (C-003, T011)**: `doctor command-files` on the legacy
   fixture keeps its finding count and exit code (the sibling command must not be
   swept into this change).
9. **Half-by-half (SC-004)**: revert the skills half only → test 1 red, test 2
   green; revert the tool-surfaces half only → test 2 red, test 1 green. Record
   the two runs in `../research/half-fix-revert.txt`.

Keep the existing suites green:
`tests/specify_cli/cli/commands/test_doctor_skills.py`,
`test_doctor_tool_surfaces_config_error.py`, `test_doctor_cli_surface_golden.py`,
`test_doctor_shim_reexports.py`, `test_doctor_slash_commands.py`,
`tests/agent/test_agent_config_unit.py`.

## Changelog (T008)

`docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink) under
`[Unreleased]`: bold impact-first lead with `(#6891)`, then before/after, under
1,200 characters. T009: grep for `all manifest entries healthy` /
`all surfaces healthy` under `docs/` and record the result in
`../research/doc-mentions.txt`; update only a page that actually shows the old
line.

## Done means

- Both summaries truthful in the legacy shape, unchanged everywhere else.
- No new public symbol, no new CLI flag, no `--json` key change, no added
  `load_agent_config` call, no exit-code change.
- Red-first transcript, half-fix revert transcript, call-count and doc-grep
  records committed under `../research/`.
- `uv run ruff check` / `uv run ruff format --check` clean on touched files;
  `uv run mypy --strict src/specify_cli/cli/commands/_command_surface_doctor.py`
  no worse than the pre-existing baseline (#5917's two `no-any-return` errors).
