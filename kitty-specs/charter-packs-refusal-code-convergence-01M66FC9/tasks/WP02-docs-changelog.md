---
work_package_id: WP02
title: Docs and changelog for the converged refusal
dependencies:
- WP01
requirement_refs:
- FR-005
- SC-004
planning_base_branch: issue-6772-charter-packs-refusal-code
merge_target_branch: issue-6772-charter-packs-refusal-code
branch_strategy: Planning artifacts for this mission were generated on issue-6772-charter-packs-refusal-code. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6772-charter-packs-refusal-code unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
phase: Phase 2 - User-facing docs
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/api/charter-commands.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Docs and changelog for the converged refusal

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

The CLI reference (`docs/api/charter-commands.md`) stops documenting the activate/deactivate
asymmetry and instead documents the converged behaviour; the changelog records the
user-facing change. Success criteria: SC-004, FR-005.

## Context & Constraints

- Spec: `kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/spec.md` (FR-005, SC-004).
- Issue: #6772. The docs section is "Error envelope and codes" (the codes table plus the
  "Edge cases" list). The asymmetry note is the bullet starting "A malformed `charter_packs`
  entry in `.kittify/config.yaml` is refused as `ACTIVATION_FAILED` by `activate` but as
  `ACTIVE_CHARTER_CONFIG_INVALID` by `deactivate`" — it names #6772 as the follow-up; remove
  it and replace with the converged statement.
- Changelog rules (charter): `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (root
  `CHANGELOG.md` is a symlink to it — never edit the symlink target path), bold impact-first
  lead with `(#6772)`, before/after, under 1,200 characters. Follow the style of neighboring
  entries.
- If any docs-retrieval index or freshness gate covers these files, run the commands the repo
  documents (`uv run python -m scripts.docs.check_docs_freshness --ci`) only if the change
  touches indexed pages; `charter-commands.md` edits historically require no index regen, but
  check `docs/development/docs-retrieval-index.yaml` for a `charter-commands.md` entry first.

## Branch Strategy

- **Strategy**: populated automatically by `spec-kitty agent mission finalize-tasks`
- **Planning base branch**: `issue-6772-charter-packs-refusal-code`
- **Merge target branch**: `issue-6772-charter-packs-refusal-code`

## Subtasks & Detailed Guidance

### Subtask T005 – Converge the CLI reference

- **Purpose**: FR-005 — the reference must not pin a fixed asymmetry.
- **Steps**:
  1. In `docs/api/charter-commands.md` ("Error envelope and codes"), remove the asymmetry
     edge-case bullet.
  2. Converge the wording: a malformed `charter_packs` registry is refused by BOTH verbs as
     `ACTIVE_CHARTER_CONFIG_INVALID`; the `ACTIVATION_FAILED` row's cause list keeps "a
     declared org pack that was never fetched" distinct (name the fetch remedy). Update the
     `ACTIVE_CHARTER_CONFIG_INVALID` row's cause wording if it needs to name the pack
     configuration case for activate/deactivate too (it already says "the pack configuration
     is unsound").
  3. Keep the table compact; describe behaviour (codes and causes), not the exception class.
- **Files**: `docs/api/charter-commands.md`
- **Parallel?**: Yes (with T006).
- **Notes**: Preserve the surrounding edge cases (config not a mapping, etc.).

### Subtask T006 – Changelog entry

- **Purpose**: The change is user-facing (tooling branching on `error.code`).
- **Steps**: Add under `[Unreleased]` in `docs/changelog/CHANGELOG.md` a single entry: bold
  impact-first lead naming the converged code with `(#6772)`, then before/after (activate
  used to report `ACTIVATION_FAILED` for a malformed `charter_packs` registry while
  deactivate reported `ACTIVE_CHARTER_CONFIG_INVALID`; both verbs now report
  `ACTIVE_CHARTER_CONFIG_INVALID`, text and `--json`; a declared-but-unfetched pack still
  reports `ACTIVATION_FAILED` with the fetch remedy). Under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: Yes (with T005).
- **Notes**: Match the section (Added/Fixed) and formatting of neighboring entries; this is a
  Fixed entry.

## Test Strategy

- Docs-only WP: no test suite beyond the repo's docs gates. If CI's docs freshness/codespell
  gates cover these files, they run on the PR; validate locally only what the repo documents
  for edited docs pages.

## Risks & Mitigations

- None material.

## Review Guidance

- The docs must not mention the internal exception class or the seam; behaviour only.
- The changelog entry must be under 1,200 characters, impact-first, with the `(#6772)` ref.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
