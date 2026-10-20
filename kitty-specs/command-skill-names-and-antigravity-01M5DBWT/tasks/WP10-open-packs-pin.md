---
work_package_id: WP10
title: open-packs text fix and pin bump
dependencies:
- WP09
requirement_refs:
- FR-016
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T037
- T038
phase: Phase 5 - Packs
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in.source.yaml
- packs/internal.source.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – open-packs text fix and pin bump

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
`spec-kitty agent tasks add-history WP10 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- `spec-kitty-open-packs` names the hyphenated command-skill folders where it names the skill
  itself; core consumes the change through the documented pin bump.

## Subtasks & Detailed Guidance

### Subtask T037 – open-packs change (orchestrator-run; external repository)

- Clone at `/home/user/spec-kitty-open-packs`. Branch `issue-6475-6470-command-skill-names` from its
  default branch. Edit `packs/internal/README.md:144` (`.agents/skills/spec-kitty.*` →
  "the generated `.agents/skills/spec-kitty-<command>` command-skill directories (and any leftover
  `spec-kitty.<command>` ones from before 4.0.0)"). Re-grep `packs/` for `$spec-kitty.`,
  `/skill:spec-kitty.`, `skills/spec-kitty.`; pack prompt `/spec-kitty.<cmd>` invocations stay
  (operator answer A). Run that repo's validation (`scripts/ci/validate-packs.sh` if runnable,
  `spec-kitty charter pack regenerate-graph` if the pack manifest gate requires it).
- Commit, push, open a PR referencing #6475/#6470 (spec-kitty/spec-kitty) — orchestrator does this.

### Subtask T038 – Pin bump

- Read `docs/development/how-to/sync-packs.md`. After the open-packs commit exists on its remote
  branch, run `spec-kitty charter pack vendor --pack internal --ref <sha>` (and `--pack built-in`
  only if built-in content changed), then `make sync-packs`, and verify digests. If the pin must
  reference a merged commit only, record the pending pin bump in the PR body instead and leave the
  pin unchanged — follow the how-to.

## Definition of Done

- open-packs PR open; pin bumped (or documented as pending per the how-to).

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
spec-kitty agent action implement WP10 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
