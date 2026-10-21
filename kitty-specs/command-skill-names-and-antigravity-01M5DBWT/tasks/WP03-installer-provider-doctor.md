---
work_package_id: WP03
title: Installer, provider and doctor on the new names
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-004
- FR-007
- FR-019
- FR-020
- NFR-001
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
- T013
- T014
phase: Phase 1 - Foundation
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/command_installer.py
create_intent:
- tests/specify_cli/skills/test_command_installer_legacy.py
- tests/scenarios/init/command-skill-collision.feature
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/command_installer.py
- src/specify_cli/skills/data/skills-manifest.schema.json
- src/specify_cli/skills/ownership.py
- src/specify_cli/tool_surface/providers/command_skills.py
- src/specify_cli/cli/commands/_command_surface_doctor.py
- src/specify_cli/cli/commands/init.py
- tests/specify_cli/skills/test_command_installer.py
- tests/specify_cli/skills/test_command_installer_legacy.py
- tests/scenarios/init/command-skill-collision.feature
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Installer, provider and doctor on the new names

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
`spec-kitty agent tasks add-history WP03 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- The installer writes `.agents/skills/spec-kitty-<cmd>/SKILL.md` and the manifest records only
  hyphen paths for new installs.
- **Every** repair path (provider repair used by init / agent config / tool-surfaces, `prune_stale`
  used by `doctor skills --fix`, `remove`) treats a legacy dotted manifest entry the same way:
  owned + hash-equal → delete file (and folder only if it is then empty); edited → keep the file,
  drop the manifest entry, emit a `legacy_kept` disposition that callers print as a warning naming
  the path and saying it is no longer managed. Legacy entries never take the DERIVED drift-delete
  branch (`remove_entry`, `retired and self._regenerate_derived`). (FR-020, plan A-B1/R-B1.)
- A user-authored file/folder at a canonical path (not in the manifest, bytes ≠ canonical) is
  skipped for that one path with a `collision` disposition + warning; the rest of the batch
  installs and the command succeeds (FR-019, operator ruling). `_direct_assessment` currently
  raises `unexpected_collision` on any `preserve` disposition (`command_installer.py:1162-1166`) —
  change that for this case only; other preserve reasons keep their current behaviour unless the
  operator rules otherwise.
- After this WP the `_PENDING` set of the WP02 architectural gate is empty, and the WP01 #6475
  test's name/path assertions pass (frontmatter key assertion may still fail until WP07 — that is
  expected; do not weaken the test).

## Subtasks & Detailed Guidance

### Subtask T009 – Canonical paths + legacy class

- Replace `:376`, `:383-385` (`_command_from_rel_path`, `is_canonical_rel_path`), `:710`
  (`install_command` rel) and `:327` (CLI-wrapper frontmatter `name:`) and the CLI-wrapper body
  heading `:306` with the authority (heading: `# /spec-kitty-<cmd> - …` via the rewrite or the
  token helper; keep bodies agent-independent).
- Add `LEGACY_COMMAND_SKILL_NAMES = legacy_command_skill_names(CANONICAL_COMMANDS)`.
- In `prepare_commands`, before the retired-prune loop, handle entries whose path parses as legacy:
  call a new `_CommandBatch.migrate_legacy_entry(entry)` that implements the rule above (use
  `observe_destination`, `effect(... FileState("absent"))`, `manifest.remove_path`, dispositions).
  Run it on **every** `prepare_commands` call that has agents or `prune=True` (so init, agent config
  add, doctor fix, provider repair all converge), but never when `adopt_only=True`.
- `remove_entry` must no longer see legacy entries (they are handled first).
- Fix `prune_stale`'s docstring (it claims to preserve edited candidates; with the DERIVED gate it
  does not for retired canonical paths — state exactly what it does now).

### Subtask T010 – Canonical-path collision skip

- In `install_command`/`preserve`, the "Unknown content does not equal canonical rendered bytes"
  disposition at a canonical path becomes `collision` (new state string; check the `Disposition`
  state vocabulary in `tool_surface/operations.py` and extend it if it is a Literal/enum, with
  tests). `_direct_assessment` skips `collision` (no raise) and `install()` reports it in
  `InstallReport` (new `collisions: list[str]`, excluded from `installed_count`).
- Also a directory (not file) at `.agents/skills/spec-kitty-<cmd>/SKILL.md` and a symlinked folder
  without manifest ownership → `collision` too? Decide conservatively: keep current `preserve`
  semantics for symlinks/dirs unless they are clearly user content; record the decision in
  `traces/design-decisions.md`.

### Subtask T011 – Schema + verify

- `skills/data/skills-manifest.schema.json:29-30`: pattern accepts canonical
  `^\.agents/skills/spec-kitty-[a-z0-9]+(-[a-z0-9]+)*/SKILL\.md$` **or** the legacy
  `^\.agents/skills/spec-kitty\.[a-z0-9][a-z0-9-]*/SKILL\.md$` (a pre-migration manifest must
  still load). Keep `SCHEMA_VERSION` unless the loader requires a bump; record the downgrade caveat
  for WP09's release note.
- `verify()`: `stale` excludes legacy entries; add `legacy: list[str]` (manifest legacy entries +
  on-disk `.agents/skills/spec-kitty.<cmd>/` folders for commands in the explicit set) and
  `collisions: list[str]`; the orphan scan iterates only `spec-kitty-<cmd>` folders for `cmd` in
  `CANONICAL_COMMANDS` (never `startswith("spec-kitty-")`, FR-004: a user `spec-kitty-mine/` is
  never reported or touched).

### Subtask T012 – Provider, ownership, init

- `tool_surface/providers/command_skills.py:62/66/198/410-414/430`: use the authority; surface the
  new dispositions (legacy kept, collision) as warnings in the provider's diagnostics/statuses.
- `skills/ownership.py:42-51` `is_projected_skills_path`: canonical via authority; accept legacy
  paths **only for deletions** (check callers `upgrade/autocommit.py:47,489`,
  `m_3_2_5_agents_skills_gitignore_backfill.py:109` — do not edit the migration; adapt the helper's
  signature with a keyword, default safe).
- `cli/commands/init.py`: `:98` `_COMMAND_SKILL_AGENTS` → derive from `_agent_roster.SUPPORTED_AGENTS`
  (single authority; WP05 adds antigravity to the roster and it must flow here automatically);
  `:183`, `:250` paths via the authority; `:729-737` `_agent_command_token` → authority's
  `skill_invocation_token`; panels `:1384/:1402/:1420` print hyphen tokens — generalise into one
  helper for skill agents if it reduces duplication (keep complexity ≤15). Print the new-invocation
  line (FR-006, init half): one line naming the change ("Spec Kitty command skills are now named
  `spec-kitty-<command>`") when skill agents are configured.

### Subtask T013 – doctor skills

- `_command_surface_doctor.py`: payload gains `legacy` and `collisions` keys; human output prints
  "Legacy dotted command skills (no longer managed): <path> — remove it when you no longer need
  your edits" and "Your own folder blocks command skill <path> — rename or remove it, then run
  `spec-kitty doctor skills --fix`". `_repair_refusal` must not refuse `--fix` because of legacy
  leftovers or collisions; `--fix` never deletes them (read-only report, R-m5).

### Subtask T014 – Acceptance scenario + test updates

- Read `docs/development/testing/acceptance-scenarios.md` and `tests/scenarios/README.md` (steps,
  tags, `absorption-ledger.json`, `@wip`/promise rules). Write
  `tests/scenarios/init/command-skill-collision.feature` (one scenario) using **existing** steps:

  ```gherkin
  Feature: Set up command skills without overwriting my own skills
    Scenario: Setting up command skills skips a folder I already own at a command skill's name
      Given a project already set up with Spec Kitty for the agents "claude"
      And the file ".agents/skills/spec-kitty-plan/SKILL.md" has the uncommitted text "my own plan skill"
      When I run "spec-kitty init --ai codex --non-interactive"
      Then the command succeeds
      And the file ".agents/skills/spec-kitty-plan/SKILL.md" mentions "my own plan skill"
      And the file ".agents/skills/spec-kitty-specify/SKILL.md" exists
      And the output mentions "spec-kitty-plan"
  ```

  Verify each step string exists in `acceptance-jvm/src/**` step definitions (grep the Java
  `@Given/@When/@Then` annotations) and that `init --ai` on an already-set-up project is a supported
  invocation (check `init.feature`). Tag per the README rules (likely `@wip` + owner/since if it
  cannot be bound/promised yet — follow the documented rule, do not invent a promise tag). If JDK 25
  is unavailable locally (JDK 21 present), say so in the trace and rely on the pytest twin below.
- Pytest twin in `tests/specify_cli/skills/test_command_installer_legacy.py`: collision skip; edited
  legacy kept through `install`, `prune_stale`, provider `prepare_commands(prune=True)` and
  `remove`; owned legacy deleted; user `spec-kitty-mine/` untouched; legacy + canonical both present
  (partial earlier run) converges.
- Update existing tests that construct the dotted path (≈50 files; grep
  `agents/skills/spec-kitty\.`, `"spec-kitty.{`, `skills" / "spec-kitty.`). Classify each per the
  occurrence map: tests that pin the **legacy** form on purpose stay; ordinary install assertions
  move to the hyphen form via the authority helper. You may edit tests outside `owned_files` for
  this mechanical follow-through; list them in the commit body.

## Test Strategy

`.venv/bin/python -m pytest tests/specify_cli/skills tests/specify_cli/tool_surface tests/architectural/test_command_skill_name_authority.py -q`,
the init test files you touch, `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py`,
the doctor tests (`grep -rl _command_surface_doctor tests`), `make test-fast`, mypy on touched
modules. Run the WP01 6475 repro with the env var and record which assertions now pass.

## Definition of Done

- All repair paths share the legacy rule (tests prove edited legacy survives each path).
- Collision skip with warning; init succeeds; scenario file present and step-checked.
- Gate `_PENDING` empty; no prefix-based ownership left.

## Risks & Mitigations

- `recheck_commands` compares observations; new effects must be observed through the batch.
- Windows mode relaxation (`windows_dir_mode_only_divergence`) unchanged.

## Review Guidance

Reviewer runs the edited-legacy fixture through `doctor skills --fix` and `init` on an existing
project, and greps for any remaining `startswith("spec-kitty` ownership tests.

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
spec-kitty agent action implement WP03 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
