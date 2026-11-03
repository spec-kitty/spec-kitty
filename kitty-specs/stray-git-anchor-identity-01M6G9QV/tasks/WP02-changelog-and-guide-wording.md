---
work_package_id: WP02
title: Operator-facing changelog and upgrade-guide wording
dependencies: []
requirement_refs:
- FR-001
- FR-004
- SC-002
planning_base_branch: issue-7084-stray-git-anchor-identity
merge_target_branch: issue-7084-stray-git-anchor-identity
branch_strategy: Planning artifacts for this mission were generated on issue-7084-stray-git-anchor-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7084-stray-git-anchor-identity unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Documentation
history:
- at: '2026-11-03T08:57:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7084-stray-git-anchor-identity.fixed.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/unreleased/7084-stray-git-anchor-identity.fixed.md
- docs/guides/how-to/installation/upgrade-project.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Operator-facing changelog and upgrade-guide wording

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- Record what you changed per item with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

The release notes and the upgrade guide describe exactly the behaviour WP01 delivers: a folder git
does not track gets its identity minted; the refusal only covers a repository git cannot read.

Done when:

- `docs/changelog/unreleased/<pr>.fixed.md` exists with content only (no heading) and passes
  `uv run --frozen python -m scripts.docs.check_changelog_style` and
  `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
- `docs/guides/how-to/installation/upgrade-project.md` states the rule once, in the
  "If a Mission's `meta.json` is missing" section.

## Context & Constraints

- `docs/changelog/CHANGELOG.md` is assembled from fragments since #6988; never edit it.
- US spelling (the spelling gate checks `unreleased/` too).
- Do not promise more than the code does: a `.git` directory carrying `HEAD`, a `gitdir:` marker
  file, and any unreadable ancestor still refuse.

## Branch Strategy

- **Strategy**: `issue-7084-stray-git-anchor-identity` — a dedicated non-protected topic branch; the
  operator merges the pull request. Never push `main`.
- **Planning base branch**: `issue-7084-stray-git-anchor-identity`
- **Merge target branch**: `issue-7084-stray-git-anchor-identity`

## Subtasks & Detailed Guidance

### Subtask T007 – Changelog fragment

- **Purpose**: user-visible fix needs a per-PR fragment.
- **Steps**: create `docs/changelog/unreleased/7084-stray-git-anchor-identity.fixed.md` (rename to
  `<pr>.fixed.md` in T009) with one entry in the changelog's own style: bold lead naming the change,
  `(#7084)`, then **Before:** / **After:** sentences.
- **Files**: `docs/changelog/unreleased/7084-stray-git-anchor-identity.fixed.md`

### Subtask T008 – Upgrade guide sentence

- **Purpose**: the guide currently explains the refusal without saying when it does *not* apply.
- **Steps**: in "If a Mission's `meta.json` is missing", after the "Nothing is re-identified"
  paragraph, add one sentence: a folder git does not track — including one that merely sits under a
  directory named `.git` that is not a repository — is given its identity normally, because there is
  nothing to restore. Keep the existing refusal paragraph and its example unchanged.
- **Files**: `docs/guides/how-to/installation/upgrade-project.md`

### Subtask T009 – Rename to the PR number and validate

- **Purpose**: the fragment's name is the pull request number.
- **Steps**: `git mv docs/changelog/unreleased/7084-stray-git-anchor-identity.fixed.md
  docs/changelog/unreleased/<pr>.fixed.md` once the PR exists; re-run both doc checks; confirm
  `uv run python -m scripts.docs.check_docs_freshness --ci` reports no error for the touched pages.
- **Files**: the fragment path.

## Review Guidance

- The wording matches the predicate: no claim that every `.git` name is ignored.
- The guide sentence names the operator-visible outcome, not the helper names.

## Definition of Done

- [ ] T007–T009 complete; both doc checks recorded with their result.
- [ ] Fragment carries the PR number and content only.
- [ ] Guide sentence present, existing refusal text untouched.
