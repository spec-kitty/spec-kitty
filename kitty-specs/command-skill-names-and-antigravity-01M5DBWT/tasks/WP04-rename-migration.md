---
work_package_id: WP04
title: Rename migration and new-invocation notice
dependencies:
- WP03
requirement_refs:
- FR-005
- FR-006
- NFR-001
- NFR-002
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
phase: Phase 2 - Upgrade path
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_command_skill_hyphen_names.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_command_skill_hyphen_names.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_command_skill_hyphen_names.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- src/specify_cli/cli/commands/upgrade.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_command_skill_hyphen_names.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Rename migration and new-invocation notice

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
`spec-kitty agent tasks add-history WP04 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- Migration `4.0.0rc8_command_skill_hyphen_names` moves an upgraded project to the hyphen names
  using the **installer's** legacy rule (one authority; WP03), with `clone_local_effect = True`
  (the effect is under git-ignored `.agents/skills/`; a committed ledger would settle teammates'
  clones — plan A-B2/R-M1), `runs_on_worktrees = True`, idempotent `apply()`, exact `detect()`.
- `spec-kitty upgrade` output names the new invocation (FR-006 upgrade half).

## Subtasks & Detailed Guidance

### Subtask T015 – Migration

- Read `upgrade/migrations/base.py` (ClassVars: `clone_local_effect`, `runs_on_worktrees`,
  `requires_git_repository`, `identity`, `content_hash_sources`), `order_manifest.txt`, and the
  closest precedents `m_3_2_0rc45_retire_standalone_skill_surface.py` and
  `m_3_2_0rc35_codex_to_skills.py`. Read `CLAUDE.md` "Migration Ledger Model".
- `detect()`: True iff the command manifest has any legacy entry, or any
  `.agents/skills/spec-kitty.<cmd>/` folder exists for `cmd` in `CANONICAL_COMMANDS` (folders
  without manifest entries are reported, not deleted — for `detect` they still make it True only if
  there is something the migration will do; otherwise the doctor reports them. Decide precisely and
  keep `init_seed` behaviour in mind: clone-local records are seeded only when `detect()` is False).
- `apply()`: if no configured command-skill agent (`get_configured_agents` ∩ roster) → drop legacy
  manifest entries whose files are gone, warn about the rest, success. Otherwise call the
  installer's install for each configured command-skill agent (or one batch with all agents), which
  installs canonical skills and runs the legacy rule; translate `legacy_kept` / `collision`
  dispositions into `MigrationResult.warnings` and `preserved_paths`. Missing/corrupt manifest →
  success + warning naming `spec-kitty doctor skills` (a failed record would retry and block every
  upgrade, R-m3). Never mkdir an agent directory; respect `get_agent_dirs_for_project`-style config
  awareness (the shared root is created only when a configured agent needs it, exactly as the
  installer already does).
- Ownership proof extension (plan A-M1): a legacy file whose bytes equal today's render under the
  legacy name counts as owned+unmodified even if the manifest hash differs. Implement it in the
  installer helper from WP03 (out-of-map edit allowed with rationale) or here if the installer
  exposes a hook; one authority either way. Do not edit historical migrations.
- `order_manifest.txt`: append `4.0.0rc8_command_skill_hyphen_names  # tie: shares target_version
  4.0.0rc8 with 4.0.0rc8_project_intent_directive_rename; runs after it` (follow the exact
  annotation grammar used there). Run `tests/architectural/test_migration_order_manifest.py` and
  `tests/specify_cli/upgrade/test_requires_git_repository_audit.py`.

### Subtask T016 – Tests (non-vacuous, R-M7)

- Fixture: a project with codex configured, the **prior-release dotted bytes** (commit a small
  fixture set under `tests/specify_cli/upgrade/migrations/fixtures/` rendered from the base commit
  — e.g. run the base renderer once and store 2-3 SKILL.md files + a manifest carrying their
  hashes; document how they were produced), the migration's ledger row stripped from both
  partitions.
- Cases: owned unmodified → removed and hyphen installed; edited → kept + warning text asserted +
  entry dropped; legacy folder without manifest entry → untouched; user `spec-kitty-plan/` →
  collision warning, others installed; missing manifest → success + warning; no configured
  command-skill agent → no mkdir; second run → zero changes (NFR-002); the migration's own
  clone-local ledger record exists (`.kittify/migrations/clone-local.jsonl`); a lane worktree copy.
- Assert through `spec-kitty upgrade` (CliRunner) for at least one end-to-end case, plus direct
  `apply()` unit tests.

### Subtask T017 – New-invocation notice in upgrade

- `cli/commands/upgrade.py:~1183-1201` (regenerated paths report): when the rename migration ran
  (or any `spec-kitty-<cmd>` skill was added while legacy entries existed), print one line:
  "Command skills are now named spec-kitty-<command> (for example `$spec-kitty-specify` in Codex,
  `/spec-kitty-specify` in Vibe, Letta and Antigravity, `/skill:spec-kitty-specify` in Pi)." Use the
  authority's token helper; hoist the string to a constant; test it.

## Test Strategy

`.venv/bin/python -m pytest tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_command_skill_hyphen_names.py tests/architectural/test_migration_order_manifest.py tests/specify_cli/upgrade/test_requires_git_repository_audit.py -q`,
the upgrade CLI tests you touch (`tests/specify_cli/cli/commands/test_upgrade*.py` are
out-of-matrix in CI — run the ones you change locally), `make test-fast`.

## Definition of Done

- Migration registered, ordered, clone-local, idempotent; fixtures prove each case; upgrade prints
  the notice.

## Risks & Mitigations

- `m_3_2_0rc35_kittify_profile_handoff` may have patched dotted implement/review in place; those
  files match neither hash nor render → kept with the warning (accepted, recorded).

## Review Guidance

Reviewer checks the fixture bytes are genuinely prior-release, the ledger partition, and that a
do-nothing migration would fail at least the edited-file and ledger-record assertions.

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
spec-kitty agent action implement WP04 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
