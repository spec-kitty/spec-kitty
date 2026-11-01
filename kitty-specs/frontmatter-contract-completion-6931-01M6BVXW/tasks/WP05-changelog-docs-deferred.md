---
work_package_id: WP05
title: Changelog, gate docs, and the recorded deferral
dependencies:
- WP02
- WP04
requirement_refs:
- FR-011
- C-004
- C-005
- C-006
- SC-006
tracker_refs: []
planning_base_branch: issue-6931-frontmatter-contract
merge_target_branch: issue-6931-frontmatter-contract
branch_strategy: Planning artifacts were generated on issue-6931-frontmatter-contract. Completed changes merge back into that branch.
subtasks:
- T013
- T014
phase: Phase 5 - Wrap-up
assignee: ''
agent: "claude:opus:python-pedro:implementer"
shell_pid: ""
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Authored via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/development/reference/ci-gate-mechanics.md
- scripts/docs/description_length_check.py
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP05 – Changelog, gate docs, recorded deferral

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

---

## Objective

1. **Changelog** (`docs/changelog/CHANGELOG.md`, `[Unreleased]`): one entry, bold
   impact-first lead with `(#6931)`, before/after, under 1,200 characters; run
   `uv run python -m scripts.docs.check_changelog_style`.
2. **Gate docs** (`docs/development/reference/ci-gate-mechanics.md`, the page that
   already documents `description_length_check` and the docs SEO tests): a short
   section naming the new gate, what it checks, its exit contract, and — explicitly
   — that it is the **pre-doc-kitty** check: when `site/` and
   `dockitty-validate-frontmatter` land (#6930/#6937) the doc-kitty gate becomes the
   authority and this one either agrees with it or is replaced. No claim that this
   gate *is* doc-kitty.
3. **The recorded deferral (FR-011, C-006).** Do **not** delete
   `scripts/docs/description_length_check.py`. ADR D-6 says a ported check is deleted
   "in the step that ports it"; the port target does not exist on `main`, so deleting
   it now would remove enforcement with no replacement. Record the deferral where a
   reader will find it (module docstring + PR `## Deferred`), naming what unblocks it.
4. Note the overlap with #6929 on the ADR `kind`/`doc_status` row in the PR body
   (C-004): 227 files, identical values derived from the same D-7 table, and the
   merge-order advice.

## Definition of done

- `make docs-lint` passes (spelling + changelog style).
- The changelog entry is present, under 1,200 characters, and names `(#6931)`.
- The docs page reads as a gate reference, not as a promise about doc-kitty.
- Nothing in the mission claims a `dockitty-validate-frontmatter` green (SC-006).
