---
work_package_id: WP01
title: The unclog-ci page's branch-intent wording
dependencies: []
requirement_refs:
- FR-001
- NFR-001
- C-001
- SC-002
- SC-001
- NFR-003
planning_base_branch: issue-6997-red-main-guard-subjects
merge_target_branch: issue-6997-red-main-guard-subjects
branch_strategy: Planning artifacts for this mission were generated on issue-6997-red-main-guard-subjects. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6997-red-main-guard-subjects unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Red-clearing subjects
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/development/how-to/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/development/how-to/unclog-ci.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The unclog-ci page's branch-intent wording

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Clear the first of the two reds in issue #6997: the branch-intent terminology guard
fails on `docs/development/how-to/unclog-ci.md:95` because the page still carries the
deprecated main-centric phrasing. Fix the **subject** (the page), never the guard.

Done means:

- `tests/contract/test_terminology_guards.py::test_no_main_branch_workflow_language_in_live_docs_and_skills`
  passes on the reworded page.
- `git diff` shows **zero** changes under `tests/contract/test_terminology_guards.py`
  (no pattern removed, no scope narrowed, no `skip`/`xfail`, no `-k` filtering).
- The page still says what it said: a PR landing on the trunk starts a new CI wave.

## Context & Constraints

- Mission spec: `kitty-specs/red-main-guard-subjects-01M6BTZS/spec.md` (FR-001, NFR-001, C-001, SC-002)
- Plan: `kitty-specs/red-main-guard-subjects-01M6BTZS/plan.md` (IC-01)
- Discovery/reproduction: `kitty-specs/red-main-guard-subjects-01M6BTZS/research.md` (D-2)
- Charter: `.kittify/charter/charter.md`, "Branch-Intent Terminology Governance" — `main`
  is a branch, not a synonym for "the repository root checkout". The retired wording
  taught the opposite; the guard (introduced in `fd9965fca8`) enforces that.
- The guard's forbidden patterns are
  `planning happens in \`main\``, `planning happens in main\b`,
  `task generation happens in main\b`, `merge to \`main\``, `merge to main\b`,
  `run from the main repository root`, `from the main repository root`. Read them in
  `tests/contract/test_terminology_guards.py` rather than trusting this list.
- Do not change any other page in this WP.

## Branch Strategy

- **Strategy**: lane worktree off the mission's planning branch; the WP's
  `owned_files` are the only files it should touch.
- **Planning base branch**: `issue-6997-red-main-guard-subjects`
- **Merge target branch**: `issue-6997-red-main-guard-subjects`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Reword the trunk-merge sentence

- **Purpose**: Remove the deprecated phrasing while preserving the causal claim the
  sentence makes about CI load.
- **Steps**:
  1. Read `docs/development/how-to/unclog-ci.md`, section "Why each step works", the
     "Why the queue clogs" bullet (the sentence currently at line 95).
  2. Rewrite that one sentence so it states that a PR landing starts a new wave,
     without the instruction-shaped main-centric wording the guard forbids. The two
     sentences before it already name `main` as the trunk that moves, so the reworded
     sentence does not have to repeat the branch name.
  3. Keep the file's ~100-column wrapping and the existing bullet structure; touch no
     other line.
- **Files**: `docs/development/how-to/unclog-ci.md`
- **Parallel?**: No (T002 reads the same surface).
- **Notes**: A synonym swap that still reads as "do your merge in `main`" is a grep
  dodge, not a fix. The reviewer will check that the sentence reads as description.

### Subtask T002 – Sweep the live docs for the remaining forbidden patterns

- **Purpose**: Prove the page was the last live hit, so the fix is complete rather
  than the first of several.
- **Steps**:
  1. Grep the live first-party docs (`docs/**/*.md`, `README.md`, `CONTRIBUTING.md`,
     `src/charter/offering/skills/**/*.md`) for each forbidden pattern, honouring the
     guard's exempt roots in `tests/_support/terminology_scope.py` (the `docs/adr/**`,
     `docs/migrations/**`, archive areas).
  2. Record the result — expected: no hits outside the exempt roots after T001.
- **Files**: none (read-only verification; record the outcome in a progress note)
- **Parallel?**: Yes.
- **Notes**: If a hit turns up outside `unclog-ci.md`, report it rather than silently
  widening this WP's diff; the mission scope is the one page.

### Subtask T003 – Prove red-before / green-after with the guard untouched

- **Purpose**: Make the fix's non-vacuity visible: the guard must still fire on the
  old text, and must pass on the new text.
- **Steps**:
  1. Run the guard on the reworded page; expect pass.
  2. Temporarily restore the original sentence (working tree only), run the guard
     again; expect the same failure message naming `docs/development/how-to/unclog-ci.md`.
  3. Restore the reworded sentence and re-run; expect pass.
  4. Confirm `git diff --stat` shows only `docs/development/how-to/unclog-ci.md`.
- **Files**: none changed by this subtask.
- **Parallel?**: No (depends on T001).
- **Notes**: Use targeted `pytest` invocations, not a full suite
  (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Record both runs' outcomes in a progress note.

## Test Strategy

```bash
uv run python -m pytest \
  "tests/contract/test_terminology_guards.py::test_no_main_branch_workflow_language_in_live_docs_and_skills" -q
```

Also run the neighbouring guards in the same file, which share the scan targets:

```bash
uv run python -m pytest tests/contract/test_terminology_guards.py -q
```

A docs-only WP needs no compiler check.

## Risks & Mitigations

- **Grep dodge** — a synonym swap that keeps the instruction reading. Mitigation: read
  the sentence as a maintainer would; the reviewer checks it.
- **Accidental reflow** — a whole-paragraph edit that buries the wording change.
  Mitigation: one sentence, same wrap.
- **Scope creep** — "while I'm here" edits to other docs. Mitigation: `owned_files`
  names exactly one file.

## Review Guidance

- Diff the page: exactly one sentence changes, the fact survives, the wrap width is
  unchanged.
- Confirm `git diff --stat 287a226cfe -- tests/contract/test_terminology_guards.py`
  is empty.
- Confirm the guard passes when run as the issue invoked it.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
