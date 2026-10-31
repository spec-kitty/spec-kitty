---
work_package_id: WP02
title: Containment-authority claims and changelog
dependencies:
- WP01
requirement_refs:
- FR-004
- C-003
planning_base_branch: issue-6734-pack-skill-body-path-containment
merge_target_branch: issue-6734-pack-skill-body-path-containment
branch_strategy: Planning artifacts for this mission were generated on issue-6734-pack-skill-body-path-containment. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6734-pack-skill-body-path-containment unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-skill-body-path-containment-01M66FEC
base_commit: cab1be39f6ba43ea99cb65f4d0df7db25414a52d
created_at: '2026-10-30T14:39:02.069341+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 2 - Claims and changelog
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/drg/org_pack_config.py
- src/charter/offering/packs/pack_validator.py
- docs/development/how-to/create-a-pack-skill.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Containment-authority claims and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record what you changed with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Every containment-authority claim the mission makes true or stale is corrected,
and the user-facing change is recorded:

- the primitive's docstring names the pack-skill read paths among its
  consumers (its "single canonical escape-detection implementation" claim is
  now true with no hand-rolled counterexample in `pack_skills/`);
- the pack validator's hand-rolled-count ordinal matches reality;
- the pack-skill authoring how-to says enforcement holds at read time too;
- `docs/changelog/CHANGELOG.md` `[Unreleased]` carries the entry.

## Context & Constraints

- Depends on WP01: the claims are only true once both pack-skill read paths
  route through the primitive.
- Do NOT edit `kitty-specs/doctor-body-path-containment-01M5ZD3C/` — a
  historical immutable mission snapshot.
- Changelog format: bold impact-first lead with `(#6734)`, then before/after,
  under 1,200 characters, under `[Unreleased]` (root `CHANGELOG.md` is a
  symlink to `docs/changelog/CHANGELOG.md`).
- Follow the repo's code rules for docstring edits (`ruff` clean; no
  formatting churn).

## Branch Strategy

- **Strategy**: coord topology, planning on `issue-6734-pack-skill-body-path-containment`
- **Planning base branch**: `issue-6734-pack-skill-body-path-containment`
- **Merge target branch**: `issue-6734-pack-skill-body-path-containment`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually.

## Subtasks & Detailed Guidance

### Subtask T007 – Primitive docstring claim

- **Purpose**: The docstring of `resolve_relative_path_within_root`
  (`src/charter/offering/drg/org_pack_config.py`, ~line 136) lists its
  consumers; the pack-skill read paths now belong on that list.
- **Steps**: Update the docstring's consumer list to include the pack-skill
  body read paths (`charter.offering.pack_skills.validation` and
  `repository.body_text`). Keep the "single canonical escape-detection
  implementation" sentence — it is now accurate.
- **Files**: `src/charter/offering/drg/org_pack_config.py`
- **Parallel?**: No.

### Subtask T008 – Pack validator ordinal

- **Purpose**: `pack_validator.py` (~line 1441) says the asset check reuses
  the primitive "rather than a **sixth** hand-rolled resolve-then-
  `relative_to` implementation"; with the pack-skill hand-roll deleted the
  count must be verified and corrected so the ordinal is truthful.
- **Steps**: Re-count the hand-rolled containment sites repo-wide
  (`rg -n "is_relative_to" src/`); update the ordinal to the true count.
- **Files**: `src/charter/offering/packs/pack_validator.py`
- **Parallel?**: No.

### Subtask T009 – Pack-skill how-to clarification

- **Purpose**: `docs/development/how-to/create-a-pack-skill.md` documents the
  "must stay inside that directory" rule at load time only.
- **Steps**: One-line clarification that the body path is also re-checked at
  read time (fail-closed), so a symlink swap cannot serve a body from outside
  the skill directory.
- **Files**: `docs/development/how-to/create-a-pack-skill.md`
- **Parallel?**: No.

### Subtask T010 – Changelog entry

- **Purpose**: User-facing record (bold impact-first lead with `(#6734)`,
  before/after, under 1,200 characters).
- **Steps**: Add under `[Unreleased]` in `docs/changelog/CHANGELOG.md`:
  the read-time containment refusal on both pack-skill body read paths, the
  one shared containment authority (campsite follow-up from #6418), and the
  tightened `..` edge (a string-level `..` that resolves back inside is now
  refused, matching the primitive).
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: No.

## Test Strategy

- No new product tests (docstrings/docs/changelog only). Run:
  - `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`
    (required when touching `src/charter/offering/` or user-facing prose)
  - `uv run --frozen ruff check` + `ruff format --check --force-exclude` on the
    touched source files.

## Risks & Mitigations

- Ordinal drift → re-count at implementation time, cite the count in the WP
  history note.
- Changelog length/format → validate under 1,200 characters, match the
  existing entry style.

## Review Guidance

- Claims must match post-WP01 reality exactly (no aspirational wording).
- The changelog entry names both the refusal and the tightened `..` edge.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
