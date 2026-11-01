---
work_package_id: WP03
title: Changelog and charter command reference
dependencies:
- WP02
requirement_refs:
- SC-004
planning_base_branch: issue-6768-charter-resynth-project-directive
merge_target_branch: issue-6768-charter-resynth-project-directive
branch_strategy: Planning artifacts for this mission were generated on issue-6768-charter-resynth-project-directive. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6768-charter-resynth-project-directive unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 3 - Docs
history:
- at: '2026-10-31T13:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/charter-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6768'
---

# Work Package Prompt: WP03 – Changelog and charter command reference

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`). Address every item, then record what changed with
  `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

Tell the operator, in the two places they look, that a project can amend its own project
directives again.

## Subtasks

### T001 — `[Unreleased]` changelog entry

`docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink — edit the real file) under
`[Unreleased]` in the most fitting existing subsection (`### Fixed`, else `### Changed`):

- impact-first bold lead ending with `(#6768)`;
- what changed for the user: resynthesizing a project's own directive no longer refuses;
- **Before** / **After** in one sentence each: before, `charter resynthesize --topic
  directive:<PROJECT_xxx>` failed with `Additive-only violation (FR-020 / EC-6)` because the
  CLI's request snapshot listed the project's activated directives as built-in nodes; after, the
  additive-only check reads the shipped built-in layer and the project's nodes stay in the
  reference universe, so the command regenerates normally and the check still refuses a genuine
  built-in URN;
- under 1,200 characters, no nested headings.

Match the voice and shape of the neighbouring entries (they read `**…** (#NNNN). **Before:** … **After:** …`).

### T002 — Command reference note

In `docs/api/charter-commands.md`, `## spec-kitty charter resynthesize` (~line 254): add one or
two sentences to the narrative stating that a project directive the project authored and
activated can be resynthesized in place, and that the additive-only guard applies to built-in
doctrine only. Keep the existing examples; add none.

### T003 — Verify

```bash
uv run python -m scripts.docs.check_docs_freshness --ci     # expect errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

If the freshness checker reports an untouched surface as stale, record the check and its output
in the WP history instead of regenerating the whole reference (the shared machine rewrites the
global asset cache concurrently — see the mission brief).

## Definition of Done

- The changelog entry renders as one bullet with the `(#6768)` reference and stays under 1,200
  characters.
- The command reference states the new behaviour without contradicting the existing text.
- T003 commands were run and their results recorded.

## Risks

- The changelog file is shared by every parallel mission: keep your edit to a single insertion
  and rebase by keeping both sides' entries, never by dropping another mission's bullet.

## Reviewer Guidance

- Does the entry tell a `spec-kitty-charter` maintainer what they can do now that they could not
  before?
- Is the "before" claim accurate (the refusal, not a generic "bug")?
