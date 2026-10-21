---
work_package_id: WP08
title: Agent Skills validator in CI
dependencies:
- WP07
requirement_refs:
- FR-015
- SC-001
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T031
- T032
- T033
phase: Phase 4 - CI
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/validate_agent_skills.py
- tests/ci/test_validate_agent_skills.py
execution_mode: code_change
model: sonnet
owned_files:
- scripts/ci/validate_agent_skills.py
- .github/workflows/ci-router.yml
- tests/ci/test_validate_agent_skills.py
- tests/ci/test_ci_module_wiring.py
- tests/ci/test_skip_if_green_wiring.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Agent Skills validator in CI

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
`spec-kitty agent tasks add-history WP08 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- A cheap always-on CI job validates every shipped skill (projected for the shared root) and every
  skill a fresh `init` generates, with the reference validator `skills-ref==0.1.1` (PyPI,
  anthropics/agentskills, console script `agentskills`), and fails the PR on a violation.

## Subtasks & Detailed Guidance

### Subtask T031 – Script

- `scripts/ci/validate_agent_skills.py`: (1) build a temp project, run `spec-kitty init --ai codex
  --non-interactive` and `--ai claude` (HOME in a temp dir), collect every `SKILL.md` directory under
  its `.agents/skills/` and native roots; (2) project the shipped skills under
  `src/charter/offering/skills/*` for the shared root through `skill_frontmatter.project_for_root`
  into a temp dir; (3) run the validator on each directory (`agentskills validate <dir>` via
  subprocess, or the `skills_ref.validate(Path)` API if importable) and aggregate; exit 1 with a
  clear per-skill report. Also run the in-repo `validate_skill_frontmatter` as a cross-check and
  fail if the two disagree. Native roots are validated with the native allowance (Claude keys
  permitted) — validate them with the in-repo checker in native mode only.
- Make the script importable for unit tests (pure functions + `main()`).

### Subtask T032 – CI wiring

- Add an always-on job to `.github/workflows/ci-router.yml` next to the cheap lint jobs (~l.760-910):
  fork guard `if:` only, no `needs:`, `ubuntu-24.04`, `timeout-minutes: 5`, the same pinned
  checkout/setup-uv actions as its neighbours, `uv sync --frozen`, `make sync-packs` equivalent if
  the generated project needs packs (regen-check job shows how: `PYTHONPATH=src uv run --frozen
  --no-sync python scripts/sync_packs.py --pack all`), then
  `uvx --from skills-ref==0.1.1 agentskills --help` and `uv run --frozen python scripts/ci/validate_agent_skills.py`.
- Update `router-gate.needs` (`ci-router.yml:~1396-1415`), `tests/ci/test_ci_module_wiring.py:~238`
  `_ALWAYS_ON_JOB_NAMES`, `tests/ci/test_skip_if_green_wiring.py:~372`, and check
  `tests/architectural/test_dual_mode_contract.py:277-322` and
  `tests/architectural/_ci_integrity_oracle.py:78-89` (add to `MUST_RUN_ALWAYS_ON_GATES` if that is
  the convention for lint gates — follow precedent `tests/ci/test_docs_lint_job.py`).

### Subtask T033 – Prove it fails

- `tests/ci/test_validate_agent_skills.py`: a seeded bad skill (dotted name; non-spec top-level key
  in shared root; 65-char name) makes the script's aggregate fail; a good one passes (run the
  in-repo checker; mark any test that needs the network/uvx so it is skipped when unavailable).
- Run the script locally once (network permitting) and paste the summary in the trace.

## Test Strategy

`.venv/bin/python -m pytest tests/ci/test_validate_agent_skills.py tests/ci/test_ci_module_wiring.py tests/ci/test_skip_if_green_wiring.py tests/architectural/test_dual_mode_contract.py -q`;
`actionlint` if available.

## Definition of Done

- Job wired and gated; script green on the branch; seeded failure proven.

## Review Guidance

Check action SHA pins match neighbours and the job is in router-gate needs.

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
spec-kitty agent action implement WP08 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
