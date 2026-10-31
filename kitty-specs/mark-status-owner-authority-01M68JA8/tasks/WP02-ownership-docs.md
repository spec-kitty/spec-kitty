---
work_package_id: WP02
title: Document the ownership and refusal contract (#6463)
dependencies:
- WP01
requirement_refs:
- C-003
- NFR-001
planning_base_branch: issue-6463-mark-status-owner-authority
merge_target_branch: issue-6463-mark-status-owner-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6463-mark-status-owner-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6463-mark-status-owner-authority unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 2 - Documentation
history:
- at: '2026-10-31T08:55:00+00:00'
  actor: system
  action: Prompt generated during tasks phase
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/architecture/status-model.md
role: implementer
tags: []
task_type: document
tracker_refs:
- "6463"
---

# Work Package Prompt: WP02 – Document the ownership and refusal contract (#6463)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via the `/spk-charter-profile-load` skill before reading anything
else. It sets your implementer identity, boundaries and initialization contract for
this work package.

## Objectives & Success Criteria

The mark-status ownership change is user-visible: an operator who used to get a silent
wrong-work-package write now gets a refusal that names every owner. Document the
behaviour where operators and maintainers look for it.

**Done when**:

- `docs/changelog/CHANGELOG.md` carries one `[Unreleased]` entry with an impact-first
  bold lead, the `(#6463)` reference, before/after, under 1,200 characters;
- `docs/architecture/status-model.md` states who owns a subtask id (the authored
  `subtasks:` roster unioned with structured `tasks.md` rows), when `mark-status`
  refuses, and that the completion event's `wp_id` is never re-derived;
- `uv run python -m scripts.docs.check_docs_freshness --ci` exits with errors=0 and no
  generated CLI-help surface changed.

## Context

- The shipped behaviour and messages are in
  `src/specify_cli/cli/commands/agent/tasks_mark_status.py` after WP01; read them, do not
  paraphrase from this prompt.
- Contract of record: `kitty-specs/mark-status-owner-authority-01M68JA8/contracts/mark-status-resolution.md`.
- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md` — edit the latter.
- The command docstring, `--wp` help, `docs/api/agent-subcommands.md` and the
  `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/mark-status.help` golden
  fixture must stay untouched: this mission changes refusals, not the flag surface.

## Detailed Guidance

### T001 — Changelog entry

One bullet under `## [Unreleased]` in the existing style (see the #5067 and #6400
entries): bold impact-first lead with `(#6463)`, then `**Before:**` and `**After:**`.
Lead with what the operator sees: an ambiguous subtask id is refused instead of being
written to the wrong work package. Keep it under 1,200 characters. Mention the two
collision classes concretely: "claimed by two work packages through different sources"
and "a work-package id typed into `mark-status`".

### T002 — Architecture note

Add a short subsection to `docs/architecture/status-model.md` (near the subtask
completion / canonical-event-log material, or under `## CLI Commands` if that reads
better) that answers, in that document's voice:

- who owns a subtask id: the authored `subtasks:` frontmatter roster unioned with
  structured `tasks.md` rows (checkbox, pipe-table, inline `Subtasks:` under a WP
  heading); prose never counts;
- what `mark-status` does when two owners exist, when `--wp` names a non-owner, and when
  a `WP<digits>` id is typed (lane transition, `move-task` is the command);
- that the completion event's `wp_id` is the resolved owner and is never re-derived
  from document order.

Link the section to `spec-kitty agent tasks mark-status`. Keep it tight (10–20 lines);
this is a contract note, not a tutorial.

### T003 — Verify

```bash
uv run python -m scripts.docs.check_docs_freshness --ci   # errors=0
git status --short                                        # no docs/api churn, no help fixture churn
```

If freshness reports errors outside your two files, record them as pre-existing in the
WP history note and in the PR `## Deferred` section — do not regenerate the whole docs
reference on this shared machine.

## Branch Strategy

- Planning base branch: `issue-6463-mark-status-owner-authority`.
- Merge target: `issue-6463-mark-status-owner-authority`.
- Execution happens in the lane worktree the runtime allocates from `lanes.json`.
  Completed changes merge back into the merge target; the operator lands it on `main`.

## Definition of Done

- Changelog entry present, under 1,200 characters, with `(#6463)`.
- Status-model note accurate against the shipped code (read the code, not this prompt).
- No generated docs or CLI-help fixture changed.
- No machine-local path or personal data in the commits.

## Reviewer Guidance

- Check the note against the actual messages in `tasks_mark_status.py`, quoting any drift.
- Check the changelog entry's length and that it does not claim a `--wp` contract change.
- Check `git diff --stat` touches only the two owned files.
