---
work_package_id: WP03
title: Record the operator-visible change in the changelog
dependencies:
- WP02
requirement_refs:
- SC-004
planning_base_branch: issue-6438-build-lifecycle-payloads-from-models
merge_target_branch: issue-6438-build-lifecycle-payloads-from-models
branch_strategy: Planning artifacts for this mission were generated on issue-6438-build-lifecycle-payloads-from-models. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6438-build-lifecycle-payloads-from-models unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
phase: Phase 3 - Record
history:
- at: '2026-10-31T12:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: communicator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Record the operator-visible change in the changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `comms-cleo`
- **Role**: `communicator`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status` before starting. Address every feedback item with
`spec-kitty agent tasks add-history WP03 --note "..."`.

## Objectives & Success Criteria

One `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` states, impact-first, what changes for someone
who runs or reads the lifecycle ledger, and cites `(#6438)`.

## Context & Constraints

- The root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`. Edit the file in `docs/changelog/` only.
- Entry shape, per the repository convention: a bold impact-first lead sentence ending with `(#6438)`,
  then the before/after in plain prose. Under 1,200 characters.
- Place it under the existing `## [Unreleased]` heading, newest-first within the section, matching the
  surrounding entries' formatting (do not invent a new heading level).
- Match the US spelling the docs gate enforces.

## Branch Strategy

- **Strategy**: feature-branch on `issue-6438-build-lifecycle-payloads-from-models`
- **Planning base branch**: `issue-6438-build-lifecycle-payloads-from-models`
- **Merge target branch**: `issue-6438-build-lifecycle-payloads-from-models`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T010 – Author the entry

- **Purpose**: A reader of the changelog learns that a contract-invalid lifecycle payload no longer
  reaches the ledger.
- **Steps**:
  - Read the top of `docs/changelog/CHANGELOG.md` for the `[Unreleased]` formatting.
  - State: `MissionReopened`, `FollowUpRecorded` and `ReviewerSelfApproval` payloads are now built through
    their published `spec-kitty-events` models, so a payload the contract rejects (an empty `reason`, for
    example) fails at emit time instead of being written and detected later by a consumer.
  - State the "after" for a valid emit too: the persisted row is the model's own JSON dump, so the ledger
    and the published contract cannot drift; existing lines are never rewritten.
  - Mention that the issue's follow-on item about the unused hosted lifecycle builder was already done
    in #6607, so a reader does not think part of #6438 is outstanding.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: no.
- **Notes**: keep it under 1,200 characters; no implementation internals beyond the event and model names.

### Subtask T011 – Verify docs freshness

- **Steps**:
  - `uv run python -m scripts.docs.check_docs_freshness --ci` → expect `errors=0`.
  - If it reports an unrelated, pre-existing error, record it verbatim in the WP history and in the PR's
    `## Deferred` rather than regenerating unrelated docs.
- **Files**: none.
- **Parallel?**: no.

## Risks & Mitigations

- Churn from regenerating a whole docs index → run the check only; do not run a full regenerator.
- Terminology drift (`feature` for `mission`) → use "mission" throughout.

## Review Guidance

- Does the lead sentence say what changed for the user, not what file changed?
- Is the reference `(#6438)`? Is the entry under `[Unreleased]` and under 1,200 characters?
- Is any pre-existing changelog text rewritten? It must not be.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
