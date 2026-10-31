---
work_package_id: WP04
title: Changelog and the docs the behaviour touches
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6450-consolidate-run-gap-truthfulness
merge_target_branch: issue-6450-consolidate-run-gap-truthfulness
branch_strategy: Planning artifacts for this mission were generated on issue-6450-consolidate-run-gap-truthfulness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6450-consolidate-run-gap-truthfulness unless the human explicitly redirects the landing branch.
base_branch: issue-6450-consolidate-run-gap-truthfulness
base_commit: f810db3fbd429e8888c32f72150c90985fbbce11
created_at: '2026-10-31T12:46:28Z'
subtasks:
- T011
- T012
- T013
phase: Phase 3 - Documentation
history:
- at: '2026-10-31T12:46:28Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/development/recovery/**
- docs/development/how-to/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Changelog and the docs the behaviour touches

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `comms-cleo`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Load the profile first: `spec-kitty agent profile show comms-cleo`, then
`spec-kitty charter context --action implement`.

---

## Objectives & Success Criteria

Record the three user-facing changes from #6450 items (4), (6) and (7) under `[Unreleased]`, and
update the existing prose that describes consolidation teardown and acceptance next steps.

Done when:

- `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink to it) has one `[Unreleased]`
  entry with a bold impact-first lead, the `(#6450)` reference, before/after, and under 1,200
  characters.
- The touched doc pages state: consolidation commits the lane workspace-context tombstones it makes;
  `accept` on coordination topology points at `specify-kitty consolidate` rather than a pull request;
  the `done` issue-matrix refusal only prints the verdict remedy when a verdict is missing.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and
  `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` passes.

## Context & Constraints

Read first:

- `kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/spec.md` — C-003 and the three user stories.
- `docs/changelog/CHANGELOG.md` — the `[Unreleased]` section's existing shape and voice.
- `docs/development/recovery/recover-from-interrupted-merge.md` and the consolidation how-to pages —
  wherever teardown, workspace contexts or `accept` next steps are described.

Constraints that matter:

- Edit existing pages; do not add a page (so the docs index needs no rebuild — this host's installed
  CLI asset cache is shared with other agents).
- Never write machine-local paths, hostnames or personal data.
- Keep the entry under 1,200 characters; US spelling, as the docs gates require.

## Branch Strategy

- **Strategy**: workspace-per-work-package on a lanes-topology Mission; the WP executes in its
  computed lane worktree and merges back into the mission target branch.
- **Planning base branch**: `issue-6450-consolidate-run-gap-truthfulness`
- **Merge target branch**: `issue-6450-consolidate-run-gap-truthfulness`

> Populated by `specify_cli`. Do not edit by hand.

## Subtasks & Detailed Guidance

### T011 — Changelog entry

One bullet, impact-first: what an operator no longer has to do. Mention all three fixes, cite
`(#6450)`. Example shape (write your own wording):

> **Consolidation now leaves a clean tree and truthful next steps (#6450).** `consolidate` commits
> the `.kittify/workspaces/*.json` contexts it tombstones ... Before: ... After: ...

### T012 — Doc prose

- The consolidation/teardown doc: state that the lane workspace-context tombstones are committed by
  the run's cleanup phase (so a landed merge ends clean).
- The acceptance doc/how-to: state the coordination-topology next step is `spec-kitty consolidate`,
  and that a pull request is only suggested for topologies that use one.
- The issue-matrix/done documentation, if it quotes the refusal: reflect the cause-dependent header.

### T013 — Verification

- `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0).
- `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`.
- `uv run pytest tests/cross_cutting -k "changelog or docs" -q` if such a selection exists.

## Test Strategy

Docs-only; the gates are the freshness check and the terminology test.

## Definition of Done

- Entry present, character budget respected, `(#6450)` cited.
- Freshness and terminology gates green.
- No new page, no docs index churn.

## Risks

- Changelog conflicts on rebase → keep both sides' `[Unreleased]` entries.
- A stale docs index after editing a page's title/heading → the freshness check will name it.

## Reviewer Guidance

Check the entry's before/after is accurate against the diff (three defects, not one), and that no
doc claims a gate or topology behaviour the code does not have.
