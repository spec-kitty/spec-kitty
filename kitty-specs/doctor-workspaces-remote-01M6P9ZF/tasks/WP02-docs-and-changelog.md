---
work_package_id: WP02
title: Docs, CLI reference and changelog fragment
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- FR-006
- C-002
- SC-001
planning_base_branch: issue-7214-doctor-workspaces-remote
merge_target_branch: issue-7214-doctor-workspaces-remote
branch_strategy: Planning artifacts for this mission were generated on issue-7214-doctor-workspaces-remote. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7214-doctor-workspaces-remote unless the human explicitly redirects the landing branch.
created_at: '2026-11-05T17:10:00+00:00'
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Docs
history:
- at: '2026-11-05T17:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/development/how-to/pr-landing.md
- docs/api/cli-commands.md
- docs/changelog/unreleased/
execution_mode: planning_artifact
owned_files:
- docs/development/how-to/pr-landing.md
- docs/api/cli-commands.md
role: implementer
tags: []
task_type: docs
tracker_refs:
- '#7214'
---

# Work Package Prompt: WP02 – Docs, CLI reference and changelog fragment

## Objective

State the option where the operator meets it: the landing runbook's removal step,
the generated CLI reference, and a per-PR changelog fragment.

## Subtasks

- **T007** — `docs/development/how-to/pr-landing.md` step 12: the fetch bullet,
  the verdict bullet and the `--prune` bullet speak of `<remote>/<primary>`;
  a fork-clone block shows `--remote upstream`; the "known gaps" and
  after-session paragraphs stop pointing at `origin` alone.
- **T008** — `docs/api/cli-commands.md`: the `spec-kitty doctor workspaces`
  block is regenerated (or hand-updated) to the live surface including
  `--remote`, then verified with `check_cli_reference_freshness` and
  `check_docs_freshness --ci` (errors=0).
- **T009** — `docs/changelog/unreleased/<pr>.fixed.md` (per
  `docs/changelog/unreleased/README.md`): impact-first lead with `(#7214)`,
  then before/after, under 900 characters.

## Definition of done

- The runbook's fork-clone path names `--remote upstream` and says nothing is fetched.
- The CLI reference matches the live surface (freshness checker errors=0).
- A changelog fragment exists and passes `check_changelog_style`.
