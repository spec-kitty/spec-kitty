---
work_package_id: WP01
title: 'Red-first P0 reproductions for #6475 and #6470'
dependencies: []
requirement_refs:
- FR-001
- FR-008
- SC-004
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 0 - Red-first
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/skills/
create_intent:
- tests/specify_cli/skills/test_p0_6475_command_skill_names.py
- tests/specify_cli/skills/test_p0_6470_antigravity_command_skills.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/skills/test_p0_6475_command_skill_names.py
- tests/specify_cli/skills/test_p0_6470_antigravity_command_skills.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first P0 reproductions for #6475 and #6470

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
`spec-kitty agent tasks add-history WP01 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- Two `p0_repro` tests exist, each RED on the base commit when run with
  `SPEC_KITTY_RUN_P0_REPRO=1`, committed **alone** (no product code) as the first implementation
  commit of the mission. They are the user-observable contract for #6475 and #6470.
- They go GREEN only when the later WPs land; this WP does not change product code.

## Subtasks & Detailed Guidance

### Subtask T001 – #6475 repro through `spec-kitty init`

- **Purpose**: pin that a fresh `init --ai codex` produces spec-valid command skills.
- **Precedent**: `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py:41-53`
  (`contextlib.chdir(tmp)` + `CliRunner().invoke(root_app, ["init", "--ai", "codex",
  "--non-interactive"], catch_exceptions=False)`); read how `root_app` is imported there and how
  the git repo is set up (copy the fixture approach, not the file).
- **Marker**: `@pytest.mark.p0_repro(issue=6475)` (declared in `pytest.ini`; plugin
  `tests/_support/p0_repro.py` only runs it when `SPEC_KITTY_RUN_P0_REPRO=1`). Read the plugin first.
- **HOME**: monkeypatch `HOME` (and `USERPROFILE`) to an **absolute, normalised**
  `tmp_path / "home"` (`.resolve()`), or the global writer raises "Root requires an identity and an
  absolute normalized path".
- **Assertions (use literals, never import the new naming module)**:
  - exit code 0;
  - for each of the 14 commands (hard-code the tuple: accept analyze charter consolidate implement
    plan research review specify status tasks tasks-finalize tasks-outline tasks-packages — verify
    against `CANONICAL_COMMANDS` *count* only: `len(CANONICAL_COMMANDS) == 14`):
    `.agents/skills/spec-kitty-{cmd}/SKILL.md` exists, its frontmatter `name` equals
    `f"spec-kitty-{cmd}"`, the name matches `^[a-z0-9]+(-[a-z0-9]+)*$`, len ≤ 64;
  - frontmatter top-level keys ⊆ {name, description, license, compatibility, metadata,
    allowed-tools}; description ≤ 1024 chars;
  - `list((project/".agents/skills").glob("spec-kitty.*"))` is empty;
  - every `.kittify/command-skills-manifest.json` entry path starts with `.agents/skills/spec-kitty-`.
- Parse frontmatter with `ruamel.yaml` safe loader on the text between the leading `---` lines.

### Subtask T002 – #6470 repro through `spec-kitty init --ai antigravity`

- Same harness, `--ai antigravity`, marker `@pytest.mark.p0_repro(issue=6470)`.
- Assert: exit 0; all 14 `.agents/skills/spec-kitty-{cmd}/SKILL.md` exist; the manifest has entries
  whose `agents` contain `"antigravity"`; `HOME/.agent/workflows` contains no `spec-kitty.*.md`
  (this is the part that is red on base — the global writer fills it today); and, as a secondary
  guard only, `project/.agent/workflows` has no `spec-kitty.*` file.

### Subtask T003 – Capture red evidence and commit

- Run both tests on the current HEAD:
  `SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest tests/specify_cli/skills/test_p0_6475_command_skill_names.py tests/specify_cli/skills/test_p0_6470_antigravity_command_skills.py -q -p no:randomly`
  and confirm both FAIL for the asserted reason (not an import/setup error). Also confirm they are
  deselected/skipped without the env var.
- Paste a short summary (test ids + the failing assertion lines) into
  `kitty-specs/command-skill-names-and-antigravity-01M5DBWT/traces/approach.md` as a dated entry.
- Commit only the two test files (+ the trace) with message
  `test(p0): red-first repros for dotted command skills (#6475) and Antigravity workflows (#6470)`.
- Leave the `p0_repro` markers in place: the WP that turns each green removes its marker
  (WP03 for #6475 once names are fixed — FR-012 frontmatter part lands in WP07, so WP07 removes the
  6475 marker; WP06 removes the 6470 marker once `~/.agent/workflows` is clean).

## Test Strategy

Only these two files. Ruff/format/mypy on them.

## Definition of Done

- Both tests red-for-the-right-reason on base with the env var; skipped without it; committed alone.

## Risks & Mitigations

- Vacuity: a test that imports the naming authority would pass trivially later — use literals.
- Environment: absolute HOME; no network.

## Review Guidance

Reviewer runs the command in T003 and checks the failure messages name the dotted folder / the
home `.agent/workflows` files.

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
spec-kitty agent action implement WP01 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
