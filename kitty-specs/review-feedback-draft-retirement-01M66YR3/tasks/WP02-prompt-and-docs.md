---
work_package_id: WP02
title: Prompt wording, guide and changelog
dependencies: []
requirement_refs:
- FR-007
- SC-004
- C-001
planning_base_branch: issue-6632-review-feedback-draft-retirement
merge_target_branch: issue-6632-review-feedback-draft-retirement
branch_strategy: Planning artifacts for this mission were generated on issue-6632-review-feedback-draft-retirement. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6632-review-feedback-draft-retirement unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-review-feedback-draft-retirement-01M66YR3
base_commit: c8fb16dc250a1029f1b25c4e51d65b804f311104
created_at: '2026-10-30T18:35:45.568666+00:00'
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 2 - Wording and docs
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/agent/test_review_prompt_feedback_draft.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow_executor.py
- tests/agent/test_review_prompt_feedback_draft.py
- docs/guides/how-to/missions/review-work-package.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6632'
---

# Work Package Prompt: WP02 – Prompt wording, guide and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting, and
address every item before declaring the work done.

## Objectives & Success Criteria

Stop the review prompt telling a reviewer that the feedback draft is "committed with the project" and
that "The Python script handles all file updates automatically" — both false today, and both part of
why the leftover looked acceptable. #3430 showed what a prompt that promises something the command
does not do costs: a whole review cycle.

Then document the real contract in the how-to guide and the changelog.

## Context & Constraints

- Spec US3 / FR-007; plan IC-02 (including its deliberate exclusions).
- Current text: `src/specify_cli/cli/commands/agent/workflow_executor.py`, in
  `_build_review_prompt_lines` — the "⚠️ Changes requested" block (~2318), the "❌ REQUEST CHANGES"
  block (~2366) and the closing note (~2376).
- The rejection command itself is rendered by `render_review_completion_commands`
  (`src/mission_runtime/resolution.py`) and must not change.
- Out of scope, deliberately: the `--review-feedback-file` CLI help text, its fixture
  (`tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help`) and the generated
  `docs/api/agent-subcommands.md`. The help remains accurate for a draft outside the mission
  directory, and touching it forces a generated-docs regeneration whose drift gate is not worth the
  blast radius here. Name this in the PR's `## Deferred` section if a reviewer asks.

## Branch Strategy

- **Strategy**: branch strategy is set by `finalize-tasks` from `lanes.json`; this WP runs in its
  allocated lane worktree.
- **Planning base branch**: `issue-6632-review-feedback-draft-retirement`
- **Merge target branch**: `issue-6632-review-feedback-draft-retirement`

## Subtasks & Detailed Guidance

### Subtask T009 – Reword the rejection blocks

- **Purpose**: FR-007. The reviewer must learn (a) the file is a draft, (b) the record keeps its text,
  (c) the rejection command removes the draft once the record is committed.
- **Steps**: change the three strings, keeping the prompt's line budget. Suggested wording:
  - `"  1. Write feedback to (in-repo draft; the rejection records it, then removes it):"`
  - `"   1. Write feedback to the in-repo draft path:"`
  - `"     The Python script records the feedback in review-cycle-N.md and removes this draft."`
- **Notes**: keep the two blocks parallel; no extra paragraph. Preserve the emoji/section structure —
  other prompts and tests read the section headers.

### Subtask T010 – Prompt-wording test

- **Purpose**: pin the wording so it cannot drift back to a claim the code does not honour.
- **Steps**: create `tests/agent/test_review_prompt_feedback_draft.py`; assert on the rendered
  `REVIEW: <WP>` prompt body:
  1. it does not contain `committed with the project`;
  2. it does not contain `handles all file updates automatically`;
  3. its rejection guidance names `review-cycle-`;
  4. the advertised path still comes from `review_feedback_source_path` (unchanged contract).
  Prefer a real render; otherwise call `_build_review_prompt_lines` with a minimal hand-built argument
  set. Never copy the strings into the test as the source of truth.
- **Parallel?**: yes with T011/T012.

### Subtask T011 – How-to guide

- **Purpose**: the operator-facing page must describe the lifecycle.
- **Steps**: in `docs/guides/how-to/missions/review-work-package.md`, "If changes are required",
  state: the path the prompt prints is an in-repo draft; `move-task` writes `review-cycle-N.md` with
  the text and removes the draft once that record is committed; with `--no-auto-commit`, when the
  draft is already committed, or when it lies outside the mission directory, the draft is kept, and a
  warning on stderr names it when it could not be removed. Keep the existing `/tmp/...` example — it
  remains correct.
- **Parallel?**: yes.

### Subtask T012 – Changelog entry

- **Purpose**: SC-004 and the repo's changelog contract.
- **Steps**: add one bullet to `docs/changelog/CHANGELOG.md` under `## [Unreleased] - 4.0.0rc8` →
  `### Fixed`, in house shape: bold impact-first lead ending with `(#6632)`, then **Before:** /
  **After:**, under 1,200 characters, no nested headings. Suggested lead: "**A review rejection no
  longer leaves its feedback draft behind to block the next `move-task --to for_review`** (#6632)."
- **Notes**: mention the kept-draft cases and the stderr warning, so the entry is honest about the
  destructive half.
- **Parallel?**: yes.

## Test Strategy

```bash
uv run pytest tests/agent/test_review_prompt_feedback_draft.py -q
uv run pytest tests/agent/ -q -k "prompt or review"
uv run python -m scripts.docs.check_docs_freshness --ci
```

No new doc page and no ADR, so `docs_index`/ADR inventory must be unchanged — the freshness check
proves it.

## Risks & Mitigations

- **Prompt snapshots elsewhere go red** → grep `tests/` for the old strings first; none exist today, so
  a red here means a new snapshot appeared. Fix the snapshot, never the assertion.
- **Changelog over budget** → keep it under 1,200 characters.
- **Terminology** → "Mission", "work package", "repository root checkout"; no "feature".

## Review Guidance

- Confirm the prompt no longer promises something the code does not do, in **both** blocks.
- Confirm the guide and the changelog agree with `data-model.md`'s transition table.
- Confirm nothing under `docs/api/` or the CLI help fixture changed (out of scope by design).

## Progress & Status

- Record progress with `spec-kitty agent tasks add-history WP02 --note "<what you did>"`.
- Change status with `spec-kitty agent tasks move-task WP02 --to <lane>`.
