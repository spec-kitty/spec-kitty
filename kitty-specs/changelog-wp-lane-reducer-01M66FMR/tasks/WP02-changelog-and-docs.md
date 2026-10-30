---
work_package_id: WP02
title: Changelog entry and G-13 doc update
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: issue-6612-changelog-wp-lane-reducer
merge_target_branch: issue-6612-changelog-wp-lane-reducer
branch_strategy: Planning artifacts for this mission were generated on issue-6612-changelog-wp-lane-reducer. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6612-changelog-wp-lane-reducer unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/architecture/event-ledger-writers-and-readers.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Changelog entry and G-13 doc update

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
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

The user-facing change is recorded and the architecture doc no longer lists the changelog reader as an open gap.

- `docs/changelog/CHANGELOG.md` gains an `[Unreleased]` entry: bold impact-first lead with `(#6612)`, before/after, under 1,200 characters.
- `docs/architecture/event-ledger-writers-and-readers.md`: the readers-table row for "changelog acceptance" moves to the reducer column, and the G-13 gap row drops the changelog item (the preflight item stays).

## Context & Constraints

- Spec: `kitty-specs/changelog-wp-lane-reducer-01M66FMR/spec.md`; plan.md D-1/D-2 describe the landed behavior.
- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md` — edit the real file only.
- The entry must mention the loud-failure behavior change (a corrupt status log now fails `spec-kitty agent release prep` instead of being silently skipped).
- Only these two files; no code.

## Branch Strategy

- **Strategy**: stay on the planning branch.
- **Planning base branch**: `issue-6612-changelog-wp-lane-reducer`
- **Merge target branch**: `issue-6612-changelog-wp-lane-reducer`

## Subtasks & Detailed Guidance

### Subtask T006 – Changelog entry

- **Purpose**: User-facing record per the mission brief's changelog rule.
- **Steps**: Add under `[Unreleased]` (create the section at the top if absent, following the file's existing entry style): bold impact-first lead referencing `(#6612)`, then before/after.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes (with T007).

### Subtask T007 – G-13 doc row update

- **Purpose**: Keep the architecture doc truthful after the fix.
- **Steps**: In `docs/architecture/event-ledger-writers-and-readers.md`: (1) the readers table's "changelog acceptance" row — move it from the raw/append-order group to the reducer-backed group (Through: `store.read_events` via `get_wp_lane` over the placement seam; Order: wall clock `at`, then `event_id`); (2) the G-13 gap row — remove the `release/changelog.py` item, keep the `consolidation/preflight.py` item; adjust the prose sentence naming the raw readers if needed.
- **Files**: `docs/architecture/event-ledger-writers-and-readers.md`.
- **Parallel?**: Yes (with T006).

## Risks & Mitigations

- Docs-freshness gates → no new pages or ADRs, so no index regeneration is required; if a gate still complains, run the documented freshen commands.

## Review Guidance

- Entry under 1,200 characters, impact-first, `(#6612)` present.
- G-13 row keeps the preflight item (it is deliberate and out of scope).

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
