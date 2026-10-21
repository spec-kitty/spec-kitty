---
work_package_id: WP07
title: Spec-conformant frontmatter projection and limits
dependencies:
- WP03
requirement_refs:
- FR-012
- FR-013
- FR-014
- NFR-004
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
- T029
- T030
phase: Phase 3 - Frontmatter
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/skill_frontmatter.py
create_intent:
- src/specify_cli/skills/skill_frontmatter.py
- tests/specify_cli/skills/test_skill_frontmatter.py
- tests/architectural/test_single_frontmatter_authority.py
- tests/charter_offering/pack_skills/test_skill_name_limits.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/skill_frontmatter.py
- src/specify_cli/skills/installer.py
- src/specify_cli/skills/verifier.py
- src/specify_cli/runtime/agent_skills.py
- src/specify_cli/tool_surface/bundles/**
- src/charter/offering/pack_skills/models.py
- src/charter/offering/pack_skills/validation.py
- src/charter/activation/skill_preparation.py
- tests/specify_cli/skills/test_skill_frontmatter.py
- tests/architectural/test_single_frontmatter_authority.py
- tests/charter_offering/pack_skills/test_skill_name_limits.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Spec-conformant frontmatter projection and limits

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
`spec-kitty agent tasks add-history WP07 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- Every SKILL.md written into a shared root (`.agents/skills/`, `~/.agents/skills/`) carries only
  spec fields (`name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`);
  other keys move under `metadata` as strings. Native primary roots (`.claude/skills`,
  `.qwen/skills`, `.kilocode/skills`) keep Claude-style keys. One frontmatter authority.
- Pack skill validation enforces rendered name ≤64 and description (after the Triggers suffix)
  ≤1024 with clear refusal messages.
- The WP01 #6475 repro turns fully green; remove its `p0_repro` marker here (keep the test).

## Subtasks & Detailed Guidance

### Subtask T026 – `skills/skill_frontmatter.py`

- Move/extend `command_renderer.ensure_skill_frontmatter` (`:304`) into this module as the single
  authority (keep a re-export in `command_renderer` for existing callers, or update callers — no
  second implementation). API sketch:
  - `ALLOWED_FIELDS`, `NATIVE_SKILL_ROOTS` (derive from `core/config.AGENT_SKILL_CONFIG` native
    class where possible, not a hand list), `is_shared_root(root_rel: str) -> bool`;
  - `project_for_root(skill_md: str, *, shared: bool, skill_name: str) -> str` — ensures
    frontmatter (old behaviour) then, if shared, moves non-allowed top-level keys under `metadata`
    with string values (`true`/`false` lowercase), preserving key order deterministically; emits
    block style YAML only (skills-ref uses strictyaml, which rejects flow style);
  - `validate_skill_frontmatter(skill_dir) -> list[str]` mirroring skills-ref 0.1.1 rules (name
    grammar, ≤64, equals folder NFKC, description ≤1024, compatibility ≤500, allowed fields) for
    unit tests and WP08.

### Subtask T027 – Apply the projection everywhere a SKILL.md is written or verified

- Command skills (`command_renderer.RenderedSkill.to_skill_md`, `command_installer._render_command_skill`
  CLI wrappers — out-of-map edits, rationale: frontmatter authority) render spec-only frontmatter:
  `name`, `description`, `metadata: {user-invocable: "true"}` (only shared root exists for them).
  Update `test_command_renderer.py` key-order tests and the snapshot.
- Charter/pack skills: `installer._expected_project_entries` (`:687-728`, `:703-705`) applies
  `project_for_root` keyed on the **root**, never the agent (one byte form per path, A-M3);
  `installer._project_skill_file` (`:223-258`, global) likewise; `verifier._expected_content_hash`
  (`:175-180`) uses the same projection with the entry's installed root (A-M2);
  `runtime/agent_skills._prepare_skill_tree:113` (global `~/.agents/skills`) too.
  `render_pack_skill` stays neutral (canonical keys).
- Leave the two shipped sources with `argument-hint` unchanged (A-m2): the projection moves it
  under `metadata` in shared roots; `.claude/skills` keeps it.

### Subtask T028 – Plugin bundles

- `tool_surface/bundles/_builder.py:70` reuses `command.content` for every bundle. The Claude
  bundle (`bundles/claude.py`) must apply the native projection (restore `user-invocable: true`
  top-level); Codex/Copilot keep the spec projection. Add per-bundle frontmatter assertions in the
  existing bundle tests (`tests/specify_cli/tool_surface/test_plugin_build_claude.py`,
  `test_plugin_build_codex.py`).

### Subtask T029 – Pack skill limits

- `charter/activation/skill_preparation.py:182` (rendered name) and/or
  `charter/offering/pack_skills/validation.py`: refuse rendered `<namespace>-<id>` > 64 and the
  rendered description (with `" Triggers: …."`, see `pack_skill_renderer._description`) > 1024,
  naming the limit and the actual length. Add `MAX_SKILL_NAME_LENGTH = 64`,
  `MAX_SKILL_DESCRIPTION_LENGTH = 1024` in `pack_skills/models.py` (or reuse skill_frontmatter
  constants if the layer rules allow — charter may not import specify_cli; keep constants in
  charter and have specify_cli import them, checking `tests/architectural/test_layer_rules.py`).
- Boundary tests 64/65 and 1024/1025.

### Subtask T030 – Tests + gate

- `tests/specify_cli/skills/test_skill_frontmatter.py`: projection, idempotence, CRLF (#4998
  behaviour kept), strict block style, validator rules.
- `tests/architectural/test_single_frontmatter_authority.py`: no module other than
  `skill_frontmatter.py` builds SKILL.md frontmatter lines (`"---\nname:"` shapes, `user-invocable`
  literals) except the neutral pack renderer — empty allowlist, self-mutation test.
- Update tests listed in the plan scout (`test_pack_skill_renderer.py:62-106` key sets,
  `tests/runtime/test_agent_skills.py`, verifier/installer tests, fixtures under
  `tests/fixtures/charter_pack_cutover/static/project_pack_skills/`) — judge each.

## Test Strategy

`.venv/bin/python -m pytest tests/specify_cli/skills tests/specify_cli/tool_surface tests/runtime/test_agent_skills.py tests/charter_offering tests/charter/activation -q`
(scope `tests/charter` to the touched modules' test files if the directory is large), the two new
gates, `tests/architectural/test_layer_rules.py`, the WP01 6475 test, `make test-fast`, mypy.

## Definition of Done

- Spec-only frontmatter in shared roots, native keys preserved natively, limits enforced, one
  authority, 6475 repro green and unmarked.

## Review Guidance

Reviewer runs `uvx --from skills-ref==0.1.1 agentskills validate <dir>` on a few generated dirs
(network permitting) and checks the Claude bundle keeps `user-invocable`.

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
spec-kitty agent action implement WP07 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
