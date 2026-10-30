---
work_package_id: WP02
title: Accept how-to and changelog for the named override routes
dependencies:
- WP01
requirement_refs:
- FR-004
planning_base_branch: issue-6633-accept-path-conventions-name-overrides
merge_target_branch: issue-6633-accept-path-conventions-name-overrides
branch_strategy: Planning artifacts for this mission were generated on issue-6633-accept-path-conventions-name-overrides. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6633-accept-path-conventions-name-overrides unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/guides/how-to/missions/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/guides/how-to/missions/accept-and-merge.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Accept how-to and changelog for the named override routes

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

---

## Objectives & Success Criteria

- `docs/guides/how-to/missions/accept-and-merge.md` names both project-level levers (`project.path_conventions` remap; `.kittify/overrides/missions/<type>/mission.yaml` drop) where the `contracts: none` waiver bullet currently says other conventions "stay in force".
- `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry: bold impact-first lead with `(#6633)`, before/after, under 1,200 characters.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6633 (labels include `domain:docs`).
- WP01 lands the rendered text first; describe what actually prints, cross-link `docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md`.
- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md` — edit the real file.
- No new doc page and no ADR is added, so the docs index needs no regeneration; do not run full heavy suites.

## Branch Strategy

- **Strategy**: populated by `spec-kitty agent mission finalize-tasks`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> Do NOT change these manually.

## Subtasks & Detailed Guidance

### Subtask T006 – Name both routes in the accept how-to

- **Purpose**: The how-to is the long-form companion of the failure text; today it implies only `--lenient` and `mkdir` exist for non-`contracts` conventions.
- **Steps**: In the path-conventions passage of `docs/guides/how-to/missions/accept-and-merge.md` (the bullet list around "Only `contracts/` is waived. Other path conventions, such as `src/`, `tests/` and `docs/`, stay in force."), add a short passage naming:
  - the remap route: `project.path_conventions` in `.kittify/config.yaml`, with a two-key example and the ADR link;
  - the drop route: a project mission-type override at `.kittify/overrides/missions/<type>/mission.yaml` (#4088);
  - the reminder that `--lenient` also skips the per-WP metadata checks, so the routes above are preferred.
- **Files**: `docs/guides/how-to/missions/accept-and-merge.md`
- **Parallel?**: Yes with T007 (different files).

### Subtask T007 – Changelog entry

- **Purpose**: User-facing text change; the changelog is the release-facing record.
- **Steps**: Under `[Unreleased]` in `docs/changelog/CHANGELOG.md`, add one entry: bold impact-first lead with `(#6633)`, then Before/After describing the failure text. Under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`

### Subtask T008 – Docs gates

- **Steps**: `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`; `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0). If either reports a pre-existing failure unrelated to this change, record it as a pre-existing red rather than fixing here.

## Test Strategy

- Docs gates above; no new tests (no code behavior in this WP).

## Risks & Mitigations

- Changelog length drift → keep under 1,200 characters.
- Terminology drift → use the canonical terms (`project.path_conventions`, mission-type override) verbatim from the code.

## Review Guidance

- The how-to must match what the CLI actually prints after WP01 (same key names, same config path).
- Changelog entry follows the repository's existing `[Unreleased]` entry style.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
