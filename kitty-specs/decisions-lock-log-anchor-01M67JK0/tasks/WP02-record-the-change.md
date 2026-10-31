---
work_package_id: WP02
title: Record the change for users and reviewers
dependencies:
- WP01
requirement_refs:
- NFR-003
- C-001
- C-002
- SC-004
planning_base_branch: issue-6765-decisions-lock-log-anchor
merge_target_branch: issue-6765-decisions-lock-log-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-6765-decisions-lock-log-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6765-decisions-lock-log-anchor unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
phase: Phase 2 - Record
history:
- at: '2026-10-30T23:38:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Record the change for users and reviewers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If the profile id does not exist in this project, run `spec-kitty agent profile list` and
use the docs/writing profile it offers.

---

## Objectives & Success Criteria

A user-facing `[Unreleased]` changelog entry for #6765 that says, impact first, that the
Decision Moment write lock is now keyed on the event log a decision row is appended to, so
two checkouts that write one log serialize; and that the ledger-directory lock and its
machinery are unchanged.

Done when:

- the entry is under `[Unreleased]` in `docs/changelog/CHANGELOG.md`, matches the shape of
  its neighbours, leads with the impact in bold, cites `(#6765)`, carries before/after, and
  stays under 1,200 characters;
- the entry describes **keying**, never a timeout/refusal change (`C-001`);
- no docs index or CLI reference needs regenerating for this change (`SC-004`).

## Context & Constraints

- `docs/changelog/CHANGELOG.md` is the only file this WP owns; the repository-root
  `CHANGELOG.md` is a symlink to it.
- Read the neighbouring `[Unreleased]` entries for shape; do not invent a new heading or
  ordering.
- Do not edit the mission's `kitty-specs/` artifacts (a code/planning ownership rule), and
  do not touch `src/`.

## Branch Strategy

- **Strategy**: feature branch per mission, merged to `main` by the operator.
- **Planning base branch**: `issue-6765-decisions-lock-log-anchor`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T008 – Write the `[Unreleased]` entry

- **Purpose**: tell users what changed and what did not.
- **Steps**: add one entry at the appropriate place in `[Unreleased]`, in the file's existing
  style. Content must state: the lock that guards a decision open/resolve is now keyed on the
  event log the row goes to (the anchor every writer of that log shares) *in addition to* the
  per-ledger `decisions/index.json.lock`, so two checkouts writing one
  `status.events.jsonl` serialize; before this, they took different locks and could both open
  the same explicit `decision_id`. Mention that the ledger-directory lock and its repair
  machinery are unchanged. Cite `(#6765)`.
- **Files**: `docs/changelog/CHANGELOG.md`.

### Subtask T009 – Verify shape and docs freshness

- **Purpose**: keep the docs gates honest.
- **Steps**: check the entry's character count (`python3 - <<'EOF'` or `wc -c`), confirm no
  broken links, and run the repository's docs freshness check if the change could affect it:
  `uv run python -m scripts.docs.check_docs_freshness --ci`. Record the result.
- **Files**: `docs/changelog/CHANGELOG.md`.

## Definition of Done

- Entry landed under `[Unreleased]`, under 1,200 characters, impact-first, `(#6765)` cited.
- Docs freshness check result recorded.
- No other file touched.

## Risks & Mitigations

- Sibling PR #6841 edits the decisions lock *timeout* neighbourhood → keep this entry about
  keying only, and place it in the section its neighbours use rather than at a boundary.

## Reviewer Guidance

- Is the claim in the entry exactly what the code does (both locks held; anchor keyed on the
  log)?
- Does it avoid claiming anything about refusals, retries or timeouts?
