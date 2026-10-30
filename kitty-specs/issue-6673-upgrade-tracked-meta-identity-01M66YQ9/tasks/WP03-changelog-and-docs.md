---
work_package_id: WP03
title: Changelog and upgrade documentation
dependencies:
- WP02
requirement_refs:
- FR-005
- NFR-003
planning_base_branch: issue-6673-upgrade-tracked-meta-identity
merge_target_branch: issue-6673-upgrade-tracked-meta-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6673-upgrade-tracked-meta-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6673-upgrade-tracked-meta-identity unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 3 - Communication
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/installation/upgrade-project.md
- docs/api/upgrade-lifecycle.md
role: implementer
tags: []
task_type: documentation
tracker_refs:
- '#6673'
---

# Work Package Prompt: WP03 – Changelog and upgrade documentation

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: pi

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log (`spec-kitty agent tasks status`). Address every item and record it with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

- `docs/changelog/CHANGELOG.md` (`[Unreleased]` → `### Fixed`) carries one impact-first entry for #6673, in the house style: a bold lead naming what changed for the operator, then **Before:** / **After:**, under 1,200 characters.
- The project upgrade how-to explains the new behaviour where it already tells the operator that `kitty-specs/` is the operator's data: a tracked `meta.json` missing from the working tree is rebuilt from git (and how to restore it yourself if the upgrade says it cannot).
- The upgrade reference page states the invariant in one place: an upgrade never re-identifies a Mission whose `meta.json` git already holds.
- The docs freshness / spelling / terminology gates are clean.

## Context & Constraints

- WP02 owns the exact operator-facing message; quote it, do not invent a second wording. Run the WP02 integration test or read `src/specify_cli/upgrade/tracked_meta_notice.py` for the strings.
- **Planning-artifact WP**: every owned file is under `docs/`, so this WP writes no source or test code.
- Do not restate the requirement IDs or the mission's internal structure in the docs; the audience is a project owner.
- `CHANGELOG.md` at the repository root is a symlink to `docs/changelog/CHANGELOG.md` — edit the file under `docs/` only.
- Keep the diff small: one changelog entry, one paragraph under an **existing** section in the how-to, one short paragraph in the reference page. **Do not add a heading**: the committed docs retrieval index records `##`/`###` anchors, and a new heading makes `check_docs_freshness`/`tests/docs/test_committed_docs_index_fresh.py` report drift (and the index file is not in this WP's `owned_files`).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `main`; completed changes must merge back into `main` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `main`
- **Merge target branch**: `main`
- Depends on WP02 for the final message text and the behaviour being documented.

```bash
spec-kitty agent action implement WP03 --agent python-pedro --mission issue-6673-upgrade-tracked-meta-identity-01M66YQ9
```

## Subtasks

### T010 — CHANGELOG `[Unreleased]` entry for #6673

- Under `## [Unreleased]` → `### Fixed`, add one entry in the file's existing style. Content to convey:
  - **Bold lead (impact first):** upgrading a project whose Mission `meta.json` is tracked but missing from the working tree no longer re-identifies the Mission.
  - **Before:** the `2.0.6` sweep wrote a fresh baseline `meta.json` from the directory name and the `3.2.0a4` normalization minted a new `mission_id` into it, so the next `git add -A` committed a second identity for a Mission whose history used the first.
  - **After:** the upgrade rebuilds the file from the copy git holds, so the Mission keeps its `mission_id`; when that copy cannot be read it writes nothing and names `git checkout -- kitty-specs/<slug>/meta.json`.
  - Reference `(#6673)`; stay under 1,200 characters; no em dash rules of the file's neighbours, no version number.
- Match the surrounding entries' heading and emphasis conventions exactly (read the last few `### Fixed` entries before writing).

### T011 — Document the behaviour on the upgrade pages

- `docs/guides/how-to/installation/upgrade-project.md`: near the existing "Leaves your data alone" statement (line ~78) and the `git diff` investigation note (~line 113), add a short **paragraph** (no new heading) that says:
  - `kitty-specs/<slug>/meta.json` is the Mission's identity; if git tracks it and it is missing from the working tree (an accidental delete, a partial/sparse checkout), the upgrade rebuilds it from the copy git holds, so the Mission keeps the same `mission_id`;
  - if the upgrade reports that it cannot read that copy, it has written nothing for that Mission — run the printed `git checkout -- <path>` and re-run the upgrade;
  - the upgrade never gives a Mission a second identity.
  Keep the page's voice (`you`), its sentence length and its link style; add no new page and no new `related:` entry.
- `docs/api/upgrade-lifecycle.md`: add one sentence to the section that describes what migrations may change under `kitty-specs/` (find the statement about project data) recording the invariant. Bump the page's `updated:` frontmatter date to the mission date (2026-10-30).
- Bump `updated:` on the how-to page too if it carries one.

### T012 — Run the docs gates

```bash
uv run python -m scripts.docs.check_docs_freshness --ci     # expect errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
uv run pytest tests/docs -q                                  # spelling / linkage checks for the touched pages
```

- If `check_docs_freshness` reports drift anyway (it should not: no page and no heading was added), run `uv run python -m scripts.docs.docs_index --write` / `uv run python -m scripts.docs.freshen_adr_inventory`, add `docs/development/docs-retrieval-index.yaml` to this WP's `owned_files` (via a history note — WP frontmatter is finalized already), and re-run the check.
- Fix any spelling or terminology finding in your own prose.

## Definition of Done

- The three gate commands above are green.
- The changelog entry is one entry, impact-first, with `(#6673)`, under 1,200 characters.
- Both documentation pages name the restore command, and neither introduces a second wording for the upgrade's message.
- `git diff` touches only the three owned files.

## Risks & Reviewer Guidance

- **Changelog conflict surface**: `docs/changelog/CHANGELOG.md` is edited by every concurrent mission. Keep the insertion surgical and, on rebase, keep both sides' entries.
- **Documentation drift**: the reference page must not promise behaviour for `doctor mission-state --fix` (out of scope, C-004 of the spec).
- Reviewers: check the wording against the real message in `src/specify_cli/upgrade/tracked_meta_notice.py`.
