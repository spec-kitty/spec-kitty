---
work_package_id: WP02
title: Changelog and recovery docs
dependencies:
- WP01
requirement_refs:
- SC-002
- SC-003
planning_base_branch: issue-6791-late-teardown-verdict-projection
merge_target_branch: issue-6791-late-teardown-verdict-projection
branch_strategy: Planning artifacts for this mission were generated on issue-6791-late-teardown-verdict-projection. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6791-late-teardown-verdict-projection unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/recovery/recover-from-interrupted-merge.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Changelog and recovery docs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting.

---

## Objectives & Success Criteria

Record the user-facing change and update the recovery documentation it changes.

Done when:

- `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry: bold impact-first lead with
  `(#6791)`, then before/after, under 1,200 characters, matching the surrounding entries' style.
  (The root `CHANGELOG.md` is a symlink to this file — edit the file, never replace the symlink.)
- `docs/guides/how-to/recovery/recover-from-interrupted-merge.md` states what a `--resume` now
  projects from the coordination branch in the late window, and what happens when it cannot prove a
  record landed (non-zero exit, branch/worktree/marker kept, land the file yourself and resume).
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0` and
  `tests/architectural/test_no_legacy_terminology.py` passes.

## Context & Constraints

- Shipped behaviour is defined by WP01 and `spec.md` FR-001…FR-005.
- Do not rebuild the whole CLI reference (other agents share the installed CLI's global asset cache;
  see the mission brief's shared-machine-state rules). Regenerate only the surface this change
  touches, and verify with the freshness check rather than trusting a rebuild.
- Keep terminology canonical: "coordination branch", "coordination record", "gate matrix",
  "late window", "issue verdict" — grep `docs/context/` before inventing a term.

## Branch Strategy

- **Strategy**: workspace-per-work-package; merges back into the mission branch.
- **Planning base branch**: `issue-6791-late-teardown-verdict-projection`
- **Merge target branch**: `issue-6791-late-teardown-verdict-projection`

> Populated by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### T008 – Changelog entry

- **Purpose**: A user-facing reliability fix must be discoverable.
- **Steps**: Add a bullet at the top of `[Unreleased]` in `docs/changelog/CHANGELOG.md`. Lead with
  the impact in bold, e.g. **"`consolidate --resume` no longer drops a coordination commit it did
  not project" (#6791)**; then *Before:* the resume projected only non-gate-matrix paths and deleted
  the coordination branch with the `issue-verdict` commit still on it, leaving the row `in-mission`;
  *After:* it projects those commits too, refuses (keeping branch and worktree) when it cannot prove
  a coordination record landed, and never overturns a verdict the target already holds. Stay under
  1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: Yes, with T009.
- **Notes**: Follow the existing bullet shape — bold lead, `(#issue)`, then the before/after prose.

### T009 – Recovery doc update

- **Purpose**: The exit-75 recovery section is where an operator learns what `--resume` lands.
- **Steps**: Extend the "Coordination branch" bullet under *Exit code 75* (and the resume section
  where the late projection is described) so it says the resume lands **every** coordination record
  committed after the interruption — review-cycle artifacts, tracer files and a gate-matrix commit
  such as `agent issue-verdict` — and that if it cannot prove one landed it exits non-zero naming
  the file, keeps the branch, worktree and marker, and asks the operator to land that file on the
  target (or move it into the Mission directory) and re-run `specify-kitty consolidate --resume`.
  Keep the doc's existing voice and heading structure; do not restructure the page.
- **Files**: `docs/guides/how-to/recovery/recover-from-interrupted-merge.md`
- **Parallel?**: Yes, with T008.
- **Notes**: Update the frontmatter `updated:` date to the day of the change.

### T010 – Verification

- **Steps**:
  ```bash
  uv run python -m scripts.docs.check_docs_freshness --ci
  uv run pytest tests/architectural/test_no_legacy_terminology.py -q
  ```
  Record both results in the WP history note.
- **Files**: n/a
- **Parallel?**: No.
- **Notes**: If the freshness check reports an unrelated pre-existing error, cite it in the PR's
  `## Deferred` rather than papering over it.

## Test Strategy

Documentation-only WP: the checks are the docs freshness gate and the terminology test. No code
tests are added here.

## Risks & Mitigations

- Docs-index drift from touching a page → run the freshness check (errors=0) and state the result.
- Over-long changelog entry → keep the bullet under 1,200 characters and impact-first.

## Review Guidance

- The changelog entry says what changed for the operator before it says how.
- The recovery doc's commands are copy-pasteable and match the CLI's real behaviour (exit code and
  what is kept).
- No claim in the docs exceeds what WP01 ships.

## Progress & Status

- First: `spec-kitty agent action implement WP02 --agent <name> --mission late-teardown-verdict-projection-01M67J85`
- Record progress with `spec-kitty agent tasks add-history WP02 --note "…"`.
