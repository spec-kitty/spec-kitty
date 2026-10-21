---
work_package_id: WP09
title: Docs, ADR, agent tables and changelog
dependencies:
- WP04
- WP05
- WP06
- WP07
- WP08
requirement_refs:
- FR-018
- FR-006
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T034
- T035
- T036
phase: Phase 5 - Docs
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/adr/4.x/2026-10-20-1-command-skills-use-spec-conformant-names.md
execution_mode: code_change
model: sonnet
owned_files:
- docs/adr/4.x/2026-10-20-1-command-skills-use-spec-conformant-names.md
- docs/adr/3.x/2026-04-07-1-global-slash-command-installation.md
- docs/changelog/CHANGELOG.md
- docs/**/*.md
- CLAUDE.md
- AGENTS.md
- README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Docs, ADR, agent tables and changelog

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
`spec-kitty agent tasks add-history WP09 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- Docs mirror shipped behaviour; a new ADR records the decisions and amends ADR 2026-04-07-1; agent
  tables move Antigravity to the skills table; the changelog has an impact-first entry.

## Subtasks & Detailed Guidance

### Subtask T034 – ADR

- Copy the structure of a recent `docs/adr/4.x/` ADR (frontmatter: title, description, status
  Accepted, date 2026-10-20). Content: context (#6475 dotted names silently dropped; #6470
  workflows dead), decisions (name + one authority; clean break with per-clone migration; legacy
  keep-edited rule on every repair path; render-time invocation rewrite with slash files unchanged
  (#6471); `builtin:` alias; Antigravity as command-skill agent; workflows archived; home writer
  scoped to configured agents — **amends 2026-04-07-1**'s "all agents at every startup" and removes
  the antigravity row of its table; frontmatter projection per root; skills-ref in CI),
  consequences (older CLI cannot read new manifests; duplicate commands in harnesses that read both
  a slash file and `.agents/skills`, e.g. codex+copilot, until #6471; doctor reports leftovers).
- Old ADR: add only an "Amended by" pointer line near the top (occurrence map: manual_review).
- Run `.venv/bin/python scripts/docs/docs_index.py --write` and
  `.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (errors=0).

### Subtask T035 – Tables and docs occurrences

- `CLAUDE.md` / `AGENTS.md` "Supported AI Agents": 12 slash-command agents (remove Antigravity row),
  5 Agent Skills agents (add Antigravity: `.agents/skills/`, `/spec-kitty-<command>`, key
  `antigravity`); update the counts line ("17 agents total: 12 slash-command, 5 Agent Skills"), the
  command-surface column (`$spec-kitty-<command>`, `/spec-kitty-<command>`,
  `/skill:spec-kitty-<command>`), and "share `.agents/skills/spec-kitty-<command>/SKILL.md`".
- Docs: grep `docs/` for `.agents/skills/spec-kitty.`, `$spec-kitty.`, `/skill:spec-kitty.`,
  `spec-kitty.<command>` skill references and `.agent/workflows`; classify per
  `occurrence_map.yaml` (historical changelogs/ADRs/kitty-specs untouched; slash-command docs keep
  `/spec-kitty.<cmd>`); update user-facing harness pages (Antigravity, Codex, Pi, Vibe, Letta),
  bump each touched page's `updated:` date. README Supported AI Agents section.
- Run `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q` and any
  docs tests (`tests/docs/`) that cover touched pages.

### Subtask T036 – Changelog

- `docs/changelog/CHANGELOG.md` `[Unreleased]`: bold impact-first lead with `(#6475, #6470)`, then
  before → after: dotted skills silently dropped → spec-valid `spec-kitty-<cmd>` load everywhere;
  how to invoke now per harness; upgrade migrates and keeps edited copies with a warning; Antigravity
  commands delivered as skills, old `.agent/workflows` files archived to
  `.kittify/backups/antigravity-workflows/`; home folder written only for configured agents;
  downgrade caveat (older CLI cannot read the new manifest). Follow the file's existing format.

## Test Strategy

Docs scripts above; terminology guard; `tests/docs` for touched pages.

## Definition of Done

- ADR + tables + docs + changelog consistent with the code; docs checks clean.

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
spec-kitty agent action implement WP09 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
