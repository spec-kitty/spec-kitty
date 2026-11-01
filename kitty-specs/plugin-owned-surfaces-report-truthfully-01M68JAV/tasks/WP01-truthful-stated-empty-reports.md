---
work_package_id: WP01
title: Truthful reports for the stated-empty project shape
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-6493-plugin-owned-surfaces-report-truthfully
merge_target_branch: issue-6493-plugin-owned-surfaces-report-truthfully
branch_strategy: Planning artifacts for this mission were generated on issue-6493-plugin-owned-surfaces-report-truthfully. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6493-plugin-owned-surfaces-report-truthfully unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-plugin-owned-surfaces-report-truthfully-01M68JAV
base_commit: 1ae78540e3b06ebd0d6c7f2d11dc4736b70ca03b
created_at: '2026-10-31T09:45:31.589744+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- Seeded by /spec-kitty.tasks (single-WP decomposition: one predicate, four read-path reporters)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_doctor_stated_empty_reports.py
- tests/init/test_init_stated_empty_agents.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/core/agent_config.py
- src/specify_cli/cli/commands/init.py
- src/specify_cli/cli/commands/agent/config.py
- src/specify_cli/cli/commands/_command_surface_doctor.py
- tests/agent/cli/commands/test_agent_config.py
- tests/specify_cli/cli/commands/test_doctor_stated_empty_reports.py
- tests/init/test_init_stated_empty_agents.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Truthful reports for the stated-empty project shape

## ⚡ Do This First: Load Agent Profile

Load the agent profile named in the frontmatter and behave according to it before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

A project whose `.kittify/config.yaml` states `agents.available: []` is reported as
set up by `spec-kitty agent config list`, `spec-kitty init` (including
`init --ai <agent>`) and `spec-kitty doctor skills|tool-surfaces|command-files`.
None of those outputs claims "healthy"/"verified" over zero managed surfaces, and
none presents `init`/`agent config add` as the repair for a broken setup.

- Success: every red-first test in T001 passes.
- Success: SC-003 ratchet still exits 1 for a *listed* agent whose command skills
  are missing.
- Success: `doctor skills --json` key set unchanged (SC-004).

## Context & Constraints

- Spec: `kitty-specs/plugin-owned-surfaces-report-truthfully-01M68JAV/spec.md`; plan
  `plan.md`; evidence `research.md` (+ `research/repro-*.txt`).
- Glossary: "CLI-managed agent", "stated-empty agent list", "legacy absent agent
  list" are defined in the spec's Key Entities; use those words.
- Red-first (DIRECTIVE_034): write T001, run it, record it red on the pre-change
  tree before any source edit.
- No ownership record, no plugin probe, no config schema change (C-001). The
  predicate must read `AgentConfig.explicit_agent_list` (C-002).
- JSON envelopes keep their keys and values (NFR-002); the new wording is
  human-output only.
- Quality: `ruff check`, `ruff format --check`, `mypy --strict` on touched files.
- Targeted tests only (`NO_FULL_HEAVY_SUITES_IN_MISSION`): the files listed in T006.

## Branch Strategy

- **Planning base branch**: `issue-6493-plugin-owned-surfaces-report-truthfully`
- **Merge target branch**: `issue-6493-plugin-owned-surfaces-report-truthfully`
- Work on this branch directly (single-WP mission; the operator merges the PR).

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first CLI tests

- **Purpose**: pin the six reports and the two truthfulness shapes before the fix.
- **Steps**: add
  - `tests/specify_cli/cli/commands/test_doctor_stated_empty_reports.py` —
    `CliRunner` invocations of the real `doctor skills`, `doctor tool-surfaces`,
    `doctor command-files` commands (import the `app` the existing doctor tests
    use) on a `tmp_path` fixture that writes `.kittify/config.yaml` with
    `agents: {available: []}`; assert each output names the no-CLI-managed state
    and contains none of `all manifest entries healthy`, `all surfaces healthy`,
    `all files healthy`. Add the `doctor skills --json` key-set assertion (SC-004)
    and a `doctor skills --fix` "writes nothing" assertion.
  - `tests/init/test_init_stated_empty_agents.py` — `init` re-run exits 0 and its
    output does not claim verification/restoration; `init --ai claude` exits 0,
    output says the stated list wins, and the command-skill file set on disk is
    unchanged (SC-002); plus the FR-007 ratchet: the same fixture with
    `available: [claude]` still exits 1 with `agent config sync`.
  - extend `tests/agent/cli/commands/test_agent_config.py` — stated-empty list
    names the no-CLI-managed state and does not print `Run 'spec-kitty init'` /
    `agent config add` as a repair; legacy config with no `available` key names
    the all-agents fallback.
- **Tips**: the existing tests patch `find_repo_root` for `agent config`; reuse
  their fixture style. For `init`, reuse the injection seams the neighbouring
  `tests/init/test_init_idempotent.py` uses rather than shelling out.
- **Record**: paste the red run (failures + counts) into the Activity Log.

### Subtask T002 – The predicate

- **Steps**: in `src/specify_cli/core/agent_config.py` add

  ```python
  def no_cli_managed_agents(config: AgentConfig) -> bool:
      """Whether the project *states* that Spec Kitty manages no agent surfaces.

      ``agents.available: []`` written on purpose means "no CLI-managed agents"
      (#6494): the command surfaces a harness plugin or another writer supplies
      are not the CLI's to install, sync or check. A config with no list at all
      is the legacy all-agents fallback (#6501) and is not this state.
      """
      return config.explicit_agent_list and not config.available
  ```

  Export it in the module `__all__` and re-export where the sibling config
  helpers are re-exported if such a facade exists.

### Subtask T003 – `agent config list`

- **Steps**: in `list_agents` (`src/specify_cli/cli/commands/agent/config.py`),
  branch on the loaded config:
  - `no_cli_managed_agents(config)` → first line `No CLI-managed agents.`; state
    that the project says its command surfaces are managed outside the CLI (for
    example by a harness plugin), so the CLI installs, syncs and checks none of
    them; do not print the `init`/`agent config add` repair sentence. May add one
    neutral line that adding an agent hands its surface to the CLI.
  - `not config.explicit_agent_list` → `No stated agent list in .kittify/config.yaml.`
    + the truth: the CLI treats every supported agent as available (legacy
    fallback) and `spec-kitty init` states the list.
  - else: unchanged.
- Keep the rest of the command (auto-commit, "Available but not configured") intact.

### Subtask T004 – `init`

- **Steps**: in `src/specify_cli/cli/commands/init.py`:
  - `_validated_agent_selection` gains the stated-empty case: when the authored
    config states no CLI-managed agents, a requested `--ai` selection is ignored
    rather than raising `Requested agents are not configured`. Pass the flag from
    the caller (the config is already loaded there); do not re-read YAML.
  - `_check_initialized_command_skills` keeps its #4425 gap diagnosis unchanged
    for listed agents.
  - the Already-Initialized panel gets a stated-empty body: "Already initialized",
    the project states no CLI-managed agents, so nothing was installed, verified
    or restored, and (when `--ai` was given) the stated list wins over the flag.
    Exit 0. The existing panel body stays for the stated-list shape.
- Do not change what `_repair_requested_command_skills` writes; in the stated-empty
  shape it already filters on the stated list and writes nothing.

### Subtask T005 – `doctor`

- **Steps**: human output only, in
  `src/specify_cli/cli/commands/_command_surface_doctor.py`:
  - `run_skills_audit` path: `_load_command_skill_state` also returns whether the
    project states no CLI-managed agents; when it does, the summary line reads
    e.g. `Command Skills: no CLI-managed agents — nothing to check.` instead of
    `all manifest entries healthy (0 file(s))`. Keep `--json` output identical
    (the flag must not enter the payload; if a human-only key is needed, use the
    existing `_HUMAN_ONLY_KEYS` mechanism).
  - `run_tool_surfaces_audit` path: when the project states no CLI-managed agents,
    print `Tool Surfaces: no CLI-managed agents — nothing to check.` instead of
    `all surfaces healthy (0 checked)`.
  - `run_command_files`: same treatment for `Command Files: all files healthy`.
- Keep exit code 0 in all three (nothing is wrong).

### Subtask T006 – Sweep, types, docs

- **Steps**: run the targeted sweep, `ruff check`/`format --check` on touched
  files, `mypy --strict` on the four touched source modules; add the
  `[Unreleased]` changelog entry (`(#6493)`, bold impact-first lead, before/after,
  under 1,200 characters); update any doc page that describes the empty agent
  list semantics if it now states something false (`docs/` grep for
  `available: []`, `No agents configured`).
- Append tracer entries for anything that shifted.

## Test Strategy

Targeted files only:
`tests/agent/cli/commands/test_agent_config.py`,
`tests/specify_cli/cli/commands/test_doctor_stated_empty_reports.py`,
`tests/specify_cli/cli/commands/test_doctor_slash_commands.py`,
`tests/init/test_init_stated_empty_agents.py`,
`tests/init/test_init_idempotent.py`,
`tests/specify_cli/tool_surface/test_surface_repair_wiring.py`,
`tests/agent/test_agent_config_unit.py`.

## Risks & Mitigations

- Changing `No agents configured` breaks `test_agent_config.py:107` — update that
  assertion in the same commit, and keep a positive control that the stated-list
  path still lists agents.
- The `--ai` change must not make `init --ai` silently succeed where a listed
  agent is missing its skills (FR-007 ratchet).

## Review Guidance

- Every changed message has a test that was red before the change.
- The predicate is the only new source symbol and has exactly one definition.
- No new config key, no plugin probe, no JSON envelope change.
- `doctor` still exits 0 and `init` still exits 1 for the #4425 shape.

## Activity Log

- 2026-10-31 — system — Prompt created.
