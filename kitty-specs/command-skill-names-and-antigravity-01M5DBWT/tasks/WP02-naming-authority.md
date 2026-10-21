---
work_package_id: WP02
title: Naming authority and invocation rewrite
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-017
- FR-016
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Foundation
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- src/specify_cli/skills/command_skill_names.py
- tests/specify_cli/skills/test_command_skill_names.py
- tests/architectural/test_command_skill_name_authority.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/command_skill_names.py
- src/specify_cli/skills/command_renderer.py
- src/specify_cli/skills/pack_skill_renderer.py
- src/specify_cli/skills/_user_input_block.py
- tests/specify_cli/skills/test_command_skill_names.py
- tests/specify_cli/skills/test_command_renderer.py
- tests/specify_cli/skills/test_pack_skill_renderer.py
- tests/specify_cli/skills/__snapshots__/**
- tests/architectural/test_command_skill_name_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Naming authority and invocation rewrite

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
`spec-kitty agent tasks add-history WP02 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- One dependency-free leaf module `src/specify_cli/skills/command_skill_names.py` is the only place
  the command-skill name and path are composed or parsed (FR-002).
- The command renderer produces `name: spec-kitty-<cmd>` and rewrites command invocations in skill
  bodies through the authority (operator answer A); pack-skill wrappers accept both `builtin:` forms
  and render the hyphenated name (answer B).
- A build-time uniqueness check fails loudly on a collision (FR-003).

## Subtasks & Detailed Guidance

### Subtask T004 – Create `skills/command_skill_names.py`

Model it on `skills/_agent_roster.py` (dependency-free leaf, `__all__`, module docstring explaining
why). It must import nothing from `specify_cli.skills` except `_agent_roster` if needed. Contents:

- `COMMAND_SKILL_PREFIX = "spec-kitty-"`, `LEGACY_COMMAND_SKILL_PREFIX = "spec-kitty."`,
  `COMMAND_SKILLS_ROOT = ".agents/skills"`.
- `command_skill_name(command: str) -> str` → `f"spec-kitty-{command}"`.
- `legacy_command_skill_name(command: str) -> str` → `f"spec-kitty.{command}"`.
- `command_skill_rel_path(command)` → `".agents/skills/spec-kitty-<cmd>/SKILL.md"` (POSIX).
- `legacy_command_skill_rel_path(command)`.
- `parse_command_skill_rel_path(rel, commands)` → command or `None` — exact match against the
  **explicit** `commands` iterable (never a prefix test: nine charter skills start with
  `spec-kitty-`, e.g. `spec-kitty-implement-review` sits beside `implement`/`review`).
- `parse_legacy_command_skill_rel_path(rel, commands)` similarly for the dotted form.
- `LEGACY_COMMAND_SKILL_NAMES: frozenset[str]` — dotted names of the current command set (derive
  from a commands tuple passed in, or define the historical tuple here; the installer owns
  `CANONICAL_COMMANDS`, so to stay a leaf take the tuple as a parameter: expose
  `legacy_command_skill_names(commands)` and let `command_installer` build the constant).
- `rewrite_command_invocations(text: str, commands: Iterable[str]) -> str` — agent-independent:
  for each canonical command, replace `/spec-kitty.<cmd>` and `$spec-kitty.<cmd>` and
  `/skill:spec-kitty.<cmd>` by the same sigil + `spec-kitty-<cmd>`, only on a token boundary
  (the next char is not `[a-z0-9-]`; longest command first so `tasks` never eats `tasks-outline`).
  Never touch `spec-kitty.ai`, `spec-kitty.analysis-report`, `.claude/commands/spec-kitty.plan.md`
  file names (they are not invocation tokens: require the sigil `/`, `$` or `/skill:` directly
  before `spec-kitty.` and not preceded by `[A-Za-z0-9_.-]`, e.g. `commands/spec-kitty.plan.md`
  must not match because `/` is preceded by `commands`… — define the boundary precisely and test it).
- `skill_invocation_token(agent_key, command) -> str` — UI-only per-harness token used by init:
  codex `$spec-kitty-<cmd>`, pi `/skill:spec-kitty-<cmd>`, other skill agents `/spec-kitty-<cmd>`;
  slash agents keep `/spec-kitty.<cmd>` (they invoke command files, C-001). Takes an
  `is_skill_agent: bool` parameter or the roster, keep it a leaf.

### Subtask T005 – Uniqueness check

- `assert_unique_command_skill_names(commands, reserved: Iterable[str])` raises a named error if any
  `command_skill_name(c)` is in `reserved`, or two commands map to one name.
- Wire it at import time in `command_installer` next to the existing
  `assert set(CANONICAL_COMMANDS) == set(CONSUMER_SKILLS)` **only if it is cheap**; otherwise as a
  test-time architectural assertion plus a call from the installer's prepare path. Reserved set =
  names of shipped charter skills (`charter.offering` built-in skill catalog — find
  `resolve_builtin_skill_catalog` / `skills/registry.py`), built-in pack skills, and
  `skills/retired.py` sets. Do **not** add dotted names to `retired.py` sets (plan A-M6).
- Test with a fake colliding command (e.g. `implement-review` → collides with
  `spec-kitty-implement-review`) — the check must fail.

### Subtask T006 – Command renderer

- `command_renderer.py:488` → `name = command_skill_name(command)`; `:368`
  `command = name.removeprefix(...)` → use the authority's prefix constant or pass `command`
  through instead of re-parsing.
- After `_rewrite_user_input`, apply `rewrite_command_invocations(body, CANONICAL_COMMANDS)`
  (import the tuple lazily or pass it in to avoid an import cycle: `command_installer` imports
  `command_renderer`). The body must stay byte-identical across agents (shared batch).
- Docstrings that say `spec-kitty.<command>` → update.
- **Do not** change the frontmatter key set here (WP07 owns frontmatter); keep `user-invocable`.
- `_user_input_block.py:26`: the replacement text should name `/spec-kitty-<command>` /
  `$spec-kitty-<command>`; update its tests.
- Update `tests/specify_cli/skills/test_command_renderer.py` and the codex snapshot
  (`__snapshots__/codex/specify.SKILL.md`) — regenerate deliberately, inspect the diff.

### Subtask T007 – Pack-skill renderer

- `pack_skill_renderer.py:27/46/128/131-136`: accept target `builtin:spec-kitty.<cmd>` **and**
  `builtin:spec-kitty-<cmd>`; error message lists the canonical hyphen form; rendered text
  "Invoke the `spec-kitty-<cmd>` command skill.". Check
  `src/charter/offering/pack_skills/models.py` / `validation.py` for a parallel parser of the
  `builtin:` target and route it through the authority if one exists (single authority).
- Tests in `test_pack_skill_renderer.py` for both inputs.

### Subtask T008 – Architectural gate

- `tests/architectural/test_command_skill_name_authority.py`: AST/regex scan of `src/` for the
  f-string shapes `f"spec-kitty.{` / `f"spec-kitty-{` and literals `.agents/skills/spec-kitty`
  outside `command_skill_names.py` → fail. Allowlist must be EMPTY at the end of WP03; in this WP,
  the remaining producers live in files WP03 owns, so write the gate with a module-level
  `_PENDING = {...}` set naming exactly those files and a test that `_PENDING` only shrinks
  (WP03 empties it). Include a self-mutation test (the gate detects a synthetic offender string).
  Exclude slash-command file producers (`runtime/agent_commands.py`, `shims/`, `migration/`,
  `upgrade/migrations/m_[0-3]*`) by the precise pattern for the *command-skill* name
  (`.agents/skills/` context or `name: spec-kitty`), not by path allowlist where possible.

## Test Strategy

`.venv/bin/python -m pytest tests/specify_cli/skills tests/architectural/test_command_skill_name_authority.py -q`
plus mypy on touched modules. The WP01 6475 test is still expected red (installer path not yet
changed) — do not touch it.

## Definition of Done

- Authority module + tests (boundary cases for the rewrite: `tasks` vs `tasks-outline`,
  `spec-kitty.ai`, `spec-kitty.analysis-report`, file names `spec-kitty.plan.md`).
- Renderer and pack-skill renderer use it; snapshot updated; gate in place with a shrinking pending set.

## Risks & Mitigations

- Import cycles: keep the leaf free of package imports.
- Over-eager rewrite: exhaustive boundary tests.

## Review Guidance

Grep the diff for any remaining `spec-kitty.{` composition in files this WP owns.

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
spec-kitty agent action implement WP02 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
