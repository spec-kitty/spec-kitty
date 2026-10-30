---
work_package_id: WP02
title: Skill, doc tables and changelog name the record
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- C-004
- SC-003
planning_base_branch: issue-6631-synthesize-reminder-write-surface
merge_target_branch: issue-6631-synthesize-reminder-write-surface
branch_strategy: Planning artifacts for this mission were generated on issue-6631-synthesize-reminder-write-surface. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6631-synthesize-reminder-write-surface unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-synthesize-commit-reminder-write-surface-01M66FQX
base_commit: a36128ba7d9bbae8f4a3d65f84cd98d9ed8fed29
created_at: '2026-10-30T14:25:26.518985+00:00'
subtasks:
- T007
- T008
phase: Phase 2 - Docs and changelog
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/skills/spk-charter-governance/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/skills/spk-charter-governance/references/charter-governance-workflow.md
- src/charter/offering/skills/spk-charter-governance/references/charter-artifact-structure.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Skill, doc tables and changelog name the record

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` via `spec-kitty agent tasks status`; address all feedback; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

The governance skill's step 7, `charter-artifact-structure.md`'s authority and
Git-tracking tables, and the changelog all name
`.kittify/charter/synthesized-artifacts.yaml` — closing the second copy of the
#6631 omission and recording the user-facing change.

Done when:

1. Step 7 of `charter-governance-workflow.md` commits the record with the rest
   of the synthesis state, and points at the printed command as the authority
   for the exact path list (so the prose cannot drift either).
2. `charter-artifact-structure.md` lists the record in the authority table
   (**Derived** — written by `charter synthesize`, do not edit) and the
   Git-tracking table (**Tracked** — the removal-sticks record shared across
   clones).
3. `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry: bold impact-first
   lead with `(#6631)`, before/after, under 1,200 characters.

## Context & Constraints

- Spec: `kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/spec.md` (FR-004, FR-005, C-004, SC-003).
- C-004: these references are committed in core (`src/charter/offering/skills/spk-charter-governance/references/`) and are the source of the rendered skill copies — edit them there. No pack pin bump: the references are NOT part of the fetched `packs/built-in` / `packs/internal` trees (verified).
- The record's own header: "Written by spec-kitty; do not edit." It is what makes an operator's artifact removal stick (#6404, #6442).
- Note the existing git-tracking row for `provenance/*, synthesis-manifest.yaml` says "Ignored"; do not change that row's semantics — only ADD the record row as Tracked. (The reminder tells operators to commit provenance via safe-commit; the "Ignored" classification of that row is a pre-existing docs question out of scope here.)

## Branch Strategy

- **Strategy**: single lane on the mission topic branch
- **Planning base branch**: `issue-6631-synthesize-reminder-write-surface`
- **Merge target branch**: `issue-6631-synthesize-reminder-write-surface`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T007 – Skill step 7 and artifact-structure tables

- **Purpose**: Close the hand-followed copy of the omission.
- **Steps**:
  1. `charter-governance-workflow.md`, step 7 (~lines 186-191): add `.kittify/charter/synthesized-artifacts.yaml` to the committed paths, and add one sentence: the exact command is printed by `charter synthesize` itself — prefer running that command over copying this list.
  2. `charter-artifact-structure.md`: add a row to the authority table — `synthesized-artifacts.yaml` | **Derived** | Written by `charter synthesize` (the created-artifacts record). Do not edit; restore from version control if damaged. Add a row to the Git-tracking table — `.kittify/charter/synthesized-artifacts.yaml` | Tracked | The per-kind record of artifacts synthesis created; sharing it across clones keeps artifact removals sticking.
- **Files**: both files under `src/charter/offering/skills/spk-charter-governance/references/`.
- **Parallel?**: Yes.
- **Notes**: Keep table column shapes identical to neighbors.

### Subtask T008 – Changelog entry

- **Purpose**: User-facing surface change must be recorded.
- **Steps**: Add under `[Unreleased]` in `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink — do not touch it): bold impact-first lead with `(#6631)`, then Before/After, under 1,200 characters. Mention that the printed command now names every path the run wrote, including the created-artifacts record and, when written, the activation file, and that the governance skill's step 7 matches.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: Yes.
- **Notes**: Follow the entry style of the neighboring #6453/#6454 entries.

## Test Strategy

- No new tests (docs-only surface). Sanity checks:
  - `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` (terminology guard).
  - `git diff` review that only the three files changed.

## Risks & Mitigations

- A docs-index gate firing on a skill-reference edit → the references are not in the docs index; if CI disagrees, run `uv run python -m scripts.docs.docs_index --write` per the delivery procedure and note it.

## Review Guidance

- Step 7 must not restate a full fixed path list as the authority — it points at the printed command.
- Changelog under 1,200 characters, impact-first, `(#6631)` present.

## Progress & Status

- Record notes: `spec-kitty agent tasks add-history WP02 --note "..."`
- Change status: `spec-kitty agent tasks move-task WP02 --to <status>`
