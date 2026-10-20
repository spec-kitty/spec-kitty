---
work_package_id: WP05
title: Antigravity command skills and project workflows archive
dependencies:
- WP03
requirement_refs:
- FR-008
- FR-009
- FR-010
- NFR-001
- NFR-005
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
phase: Phase 2 - Antigravity
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/config.py
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_antigravity_workflows.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_retire_antigravity_workflows.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/_agent_roster.py
- src/specify_cli/core/config.py
- src/specify_cli/agent_utils/directories.py
- src/specify_cli/cli/commands/agent/config.py
- src/specify_cli/cli/commands/agent/surface_presence.py
- src/specify_cli/tool_surface/profiles/capability_matrix.py
- src/specify_cli/cli/commands/regen.py
- src/specify_cli/upgrade/assessment.py
- src/specify_cli/migration/rewrite_shims.py
- src/specify_cli/shims/generator.py
- src/charter/offering/skills/spec-kitty-setup-doctor/references/agent-path-matrix.md
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_antigravity_workflows.py
- tests/specify_cli/core/test_config_registry.py
- tests/specify_cli/skills/test_agent_roster.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_retire_antigravity_workflows.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Antigravity command skills and project workflows archive

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt. If the skill is not
available, read `packs/built-in/agent_profiles/python-pedro.agent.yaml` and adopt it.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission command-skill-names-and-antigravity-01M5DBWT` and the event log `review_ref` before
starting; address every feedback item and record each with
`spec-kitty agent tasks add-history WP05 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- `init --ai antigravity`, `agent config add antigravity` and upgrade install the 14 command skills
  into `.agents/skills/` for Antigravity (FR-008); Antigravity is no longer a slash-command agent.
- Migration `4.0.0rc8_retire_antigravity_workflows` archives Spec Kitty-generated files from a
  project's `.agent/workflows` (operator ruling: archive, never delete).

## Subtasks & Detailed Guidance

### Subtask T018 – Registries and consumers

- `skills/_agent_roster.py`: `SUPPORTED_AGENTS = ("codex", "vibe", "pi", "letta", "antigravity")`
  (docstring: #6470).
- `core/config.py:68` remove the `AGENT_COMMAND_CONFIG["antigravity"]` row; keep `AI_CHOICES`,
  `IDE_AGENTS`, and `AGENT_SKILL_CONFIG["antigravity"]` (`.agents/skills/`, `.agent/skills/`).
- `agent_utils/directories.py:28,47` remove `(".agent", "workflows")` and `".agent": "antigravity"`;
  fix the docstring count. (`runtime/doctor.py` would KeyError otherwise.)
- Introduce one `configured_slash_agents(agent_keys)` helper (filter by `AGENT_COMMAND_CONFIG`) in
  the module that owns the registry and use it in: `_command_surface_doctor.py:~191` (WP03 file —
  out-of-map edit with rationale), `cli/commands/regen.py:100`, `upgrade/assessment.py:125`,
  `migration/rewrite_shims.py:102/143`, `shims/generator.py:183/221`,
  `cli/commands/agent/surface_presence.py:93,147-153`, `cli/commands/agent/config.py:61,91-97,216,346-358,496,568`
  (ordering: an agent in the roster and absent from `AGENT_COMMAND_CONFIG` must resolve as a skill
  agent in list/status/sync/add/remove). Grep `AGENT_COMMAND_CONFIG` and `get_global_command_dir`
  across `src/` and check each remaining caller still copes with antigravity absent.
- `upgrade/assessment.py`: antigravity moves from slash to command-skill agents automatically —
  verify.

### Subtask T019 – Wording surfaces

- `tool_surface/profiles/capability_matrix.py:92` → "No native agent primitive; use skill surfaces".
- `agent-path-matrix.md:31,49` → command surface `_(none; command skills)_`, matching rows 22-25.
- `init.py` panels/token (WP03 owns init.py): antigravity should get the skill-agent panel/token
  automatically through the roster; verify and only add an out-of-map edit if it does not.
- `gitignore_manager.py:341` stays (`.agent/` still holds `.agent/skills/`).

### Subtask T020 – Workflows archive migration

- Read `asset_preservation/guard.py` `guard_destructive_removal(..., backup_parent=...)` and
  `provers.py` `CanonicalContentProver`. Proof (all must hold, R-M2): regular file (not symlink);
  name `spec-kitty.<cmd>.md` with `<cmd>` in a frozen **historical** command set defined in the
  migration (include retired ones: e.g. checklist, clarify, dashboard, merge, constitution — grep
  old migrations like `m_2_0_11_remove_clarify_command.py`, `m_3_1_2_globalize_commands.py` and
  `shims/registry.py` history to build the list; document the source); the **exact** marker line
  `<!-- spec-kitty-command-version: X -->` (see `runtime/agent_commands.py:~295`
  `_VERSION_MARKER_LINE`) within the first 20 lines.
- Proven → move to `.kittify/backups/antigravity-workflows/<name>` (through the guard with
  `backup_parent`; never overwrite an existing backup — suffix it). Unproven/foreign → keep + warn.
  Never remove `.agent/workflows/` or `.agent/`.
- Refuse (warn, no change) when `.agent` or `.agent/workflows` is a symlink or resolves outside
  `project_path.resolve()` (R-M4).
- Gate on `"antigravity" in get_configured_agents(project_path)` with a legacy fallback when there
  is no config file (process only if `.agent/workflows` exists); this deviates from C-003's
  `get_agent_dirs_for_project()` because `.agent` is no longer in `AGENT_DIRS` — record the
  rationale in the module docstring and `traces/design-decisions.md`.
- When antigravity is configured, also ensure the command skills are installed (call the installer
  like WP04's migration, or rely on the finalizer repair — verify which runs and document).
- `clone_local_effect`: `.agent/workflows` files may be tracked by git in some projects — the
  archive is a working-tree change that travels with a commit if tracked; choose
  `clone_local_effect=False` only if you can justify it; otherwise True. Record the decision.
- `order_manifest.txt` line (WP04-owned file; one-line out-of-map append with `# tie:` annotation).

### Subtask T021 – Tests

- `tests/specify_cli/core/test_config_registry.py:106-138` invariants updated (antigravity not a
  command agent; the three registries still agree).
- `tests/specify_cli/skills/test_agent_roster.py:34`, `test_command_installer.py:1048` roster tuple.
- Migration fixtures: marked owned file archived; foreign file kept; marker-less file kept; edited
  marked file archived (not lost — backup exists with the edit); symlinked dir refused; no
  `.agent/workflows` → no-op, no mkdir; idempotent second run.
- `init --ai antigravity` end-to-end check (the WP01 6470 repro's project-side assertions should now
  pass except the home folder one, which WP06 fixes).
- Regression tests that iterate `AGENT_COMMAND_CONFIG` (e.g.
  `tests/specify_cli/regression/test_twelve_agent_parity.py`) — update counts/docstrings.

## Test Strategy

`.venv/bin/python -m pytest tests/specify_cli/core tests/specify_cli/skills tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_retire_antigravity_workflows.py tests/specify_cli/tool_surface tests/architectural/test_migration_order_manifest.py -q`,
the agent-config tests (`tests/agent/cli/commands/test_agent_config.py`,
`tests/specify_cli/cli/commands/test_agent_config.py`), `tests/runtime/test_doctor_command_file_health.py`,
`make test-fast`.

## Definition of Done

- Antigravity is a command-skill agent everywhere; no consumer KeyErrors; migration archives
  safely with all fixtures green.

## Review Guidance

Reviewer greps for `"antigravity"` in slash-command code paths and checks the backup never
overwrites and symlinks are refused.

## Context & Constraints

- Read first: `kitty-specs/command-skill-names-and-antigravity-01M5DBWT/spec.md`, `plan.md` (the **Post-plan squad dispositions**
  table overrides the concern text where they disagree), `research.md`, `data-model.md`,
  `occurrence_map.yaml`, and `.kittify/charter/charter.md`.
- Operator rulings (decision `01M5DBXJ05DSF4322SXVPNPZZ1` + 2026-10-20 answers): name
  `spec-kitty-<cmd>`; clean break; keep hand-edited dotted skills with a warning; slash-command files
  of the 13 command agents keep `spec-kitty.<cmd>` (C-001, #6471); pack sources keep
  `/spec-kitty.<cmd>` and skill bodies are rewritten at render time; `builtin:spec-kitty.<cmd>` is an
  accepted input alias; Antigravity workflow files are archived, not deleted; a user folder at a
  canonical path is skipped with a warning.
- **Stop and ask the operator** (C-006) on anything these rulings do not cover. Do not guess.
- Code rules: ruff + `ruff format --force-exclude <files>` + mypy clean, complexity ≤15, no new
  `# noqa`/`# type: ignore` without an inline rationale, repeated literals hoisted to constants,
  new branches covered by focused tests in the same commit.
- Tests: run the targeted files you touch plus the owning directory
  (`tests/specify_cli/skills`, `tests/specify_cli/upgrade/migrations`, init tests) and the specific
  architectural gate files implicated. **Never** `make test-full` or a bare `tests/architectural/`
  sweep (NO_FULL_HEAVY_SUITES_IN_MISSION). Use `.venv/bin/python -m pytest ... -q`.
- Harness env leaks: containers export `SPEC_KITTY_NO_NAG`, `SPEC_KITTY_NO_UPGRADE_CHECK`,
  `SPEC_KITTY_NON_INTERACTIVE`; delete them test-locally when a test needs them unset.
- Append dated entries to `kitty-specs/command-skill-names-and-antigravity-01M5DBWT/traces/*.md` at each significant decision or
  friction point (that file is planning surface; editing it is allowed).
- Commit with a conventional message ending with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_0113JBRFGzV5iEZ6QwgwijcB`. Never push.

## Branch Strategy

- **Strategy**: single_branch (no lanes; work in the repository root checkout)
- **Planning base branch**: issue-6475-6470-command-skill-names
- **Merge target branch**: issue-6475-6470-command-skill-names

## Progress & Status

Progress lives in the status event log. Record notes with
`spec-kitty agent tasks add-history <WPID> --note "..."`, move with
`spec-kitty agent tasks move-task <WPID> --to <lane>`, mark subtasks with
`spec-kitty agent tasks mark-status <Txxx...> --status done`.

Implementation command:

```bash
spec-kitty agent action implement WP05 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
