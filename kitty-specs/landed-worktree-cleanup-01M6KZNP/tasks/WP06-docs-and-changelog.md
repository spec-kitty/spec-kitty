---
work_package_id: WP06
title: Documentation and changelog
dependencies:
- WP04
- WP05
requirement_refs:
- C-005
- FR-011
planning_base_branch: issue-7173-landed-worktree-cleanup
merge_target_branch: issue-7173-landed-worktree-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-7173-landed-worktree-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7173-landed-worktree-cleanup unless the human explicitly redirects the landing branch.
subtasks:
- T024
- T025
- T026
phase: Phase 3 - Polish
history:
- at: '2026-11-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7173.fixed.md
execution_mode: planning_artifact
owned_files:
- docs/api/cli-commands.md
- docs/development/how-to/pr-landing.md
- docs/changelog/unreleased/7173.*.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Documentation and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback; record changes with `spec-kitty agent tasks add-history WP06 --note "..."`.

---

## Objectives & Success Criteria

- `docs/api/cli-commands.md` shows the current help of `spec-kitty doctor workspaces` (with `--prune`) and `spec-kitty upgrade` (with `--include-worktree`, `--all-worktrees`).
- `docs/development/how-to/pr-landing.md` owns a removal step (FR-011): after the operator merges, run `git fetch origin`, `spec-kitty doctor workspaces`, then `spec-kitty doctor workspaces --prune`; the recreate command is printed for every removal. Landing worktrees live under `.worktrees/` (already the runbook's step 2 path). Note that `upgrade` no longer commits into landing worktrees unless named.
- A changelog **fragment** (never an edit of `CHANGELOG.md`; CLAUDE.md "Code Style") describes both changes for operators.

## Context & Constraints

- The CLI reference is hand-maintained help output; `tests/architectural/test_docs_cli_reference_parity.py` checks command paths only. Copy the real `--help` text from the CLI built from this branch (`COLUMNS=80 spec-kitty doctor workspaces --help`, `COLUMNS=80 spec-kitty upgrade --help`) into the existing sections at their current positions, matching the surrounding box format.
- Fragment format: read `docs/changelog/unreleased/README.md` for `<id>.<section>.md` naming and sections; use id `7173`. Run `tests/docs/test_changelog_style.py` if it covers fragments.
- Style: short sentences, plain words, "Mission" not "feature" (Terminology Canon).
- The landing **skill** and `landing-contributor-prs` procedure are authored in `spec-kitty-open-packs`; do **not** edit `packs/` here (C-005).

## Branch Strategy

- **Planning base branch**: `issue-7173-landed-worktree-cleanup`
- **Merge target branch**: `issue-7173-landed-worktree-cleanup`

Run `spec-kitty agent action implement WP06 --agent claude --mission landed-worktree-cleanup-01M6KZNP` and work in the printed workspace.

## Subtasks & Detailed Guidance

### Subtask T024 – CLI reference

- Replace the `spec-kitty doctor workspaces` help block (around line 2863) and the `upgrade` options box (around line 6447) with the real output.

### Subtask T025 – Runbook step

- Add a numbered section after the hand-off section ("After the merge: remove the landing worktree") with the three commands, what "landed" means (content on the local `origin/<primary>`; rebase and squash merges count), what is never removed (uncommitted or untracked files, a running process, unmerged content, Mission worktrees), and how to restore a branch (`git branch <b> <sha>` or the `refs/spec-kitty/discarded/<b>` ref). Add it to the runbook's table of contents.

### Subtask T026 – Changelog fragment

- One fragment covering: new `doctor workspaces --prune` and landed-worktree report; `upgrade` no longer writes into non-Mission worktrees unless `--include-worktree`/`--all-worktrees`, and names every worktree. Reference #7173.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_docs_cli_reference_parity.py tests/docs/test_changelog_style.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen pytest tests/docs -q -k "spelling or link" 
```

## Risks & Mitigations

- Help text drift: regenerate from the built CLI, do not hand-type.

## Review Guidance

- Commands in the runbook run as printed.
- No `packs/` edits.

## Progress & Status

Record notes with `spec-kitty agent tasks add-history WP06 --note "..."`.
