---
work_package_id: WP02
title: The operator-facing record explains the new wording
dependencies:
- WP01
requirement_refs:
- FR-001
- NFR-003
planning_base_branch: issue-6792-planning-lane-gate-honest-reason
merge_target_branch: issue-6792-planning-lane-gate-honest-reason
branch_strategy: Planning artifacts for this mission were generated on issue-6792-planning-lane-gate-honest-reason. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6792-planning-lane-gate-honest-reason unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Operator-facing record
history:
- at: '2026-10-30T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/changelog/CHANGELOG.md
- docs/development/how-to/review-gates.md
role: documentarian
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The operator-facing record explains the new wording

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

1. `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry for #6792: bold
   impact-first lead, then before/after, under 1,200 characters.
2. `docs/development/how-to/review-gates.md` records, next to the existing
   inherited-limitation note (#2741), what the gate now records for a planning-lane WP and
   why — without claiming the gate inspects the committed diff.
3. The touched docs are terminology-clean and the docs freshness check reports
   `errors=0`.

## Context & Constraints

- The shipped reason string comes from WP01; quote it verbatim from
  `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` after WP01 has landed.
- The inherited limitation (the gate scopes off the working-tree diff, not the WP commit
  range) **stays unfixed** — say so. This mission only makes the recorded reason honest.
- Changelog conventions: `docs/changelog/CHANGELOG.md` (`CHANGELOG.md` at the repo root is
  a symlink to it); one entry under `[Unreleased]`; `(#6792)` reference in the lead;
  impact-first, before/after, under 1,200 characters.
- Do not add a new doc page or ADR, so no docs index regeneration is expected; still run
  the freshness check and report its result.
- Terminology: "Mission", "work package", `planning_artifact`, `lane-planning` are
  canonical values; do not use "feature" for a Mission.

## Branch Strategy

- **Strategy**: Feature-branch mission with lanes (`topology: lanes`); all work merges
  into the mission's target branch and a PR carries it to `main`.
- **Planning base branch**: `issue-6792-planning-lane-gate-honest-reason`
- **Merge target branch**: `issue-6792-planning-lane-gate-honest-reason`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change by hand.

## Subtasks & Detailed Guidance

### Subtask T007 – Changelog `[Unreleased]` entry

- **Purpose**: A user reading the release notes learns that the pre-review gate's record
  for a planning-lane WP changed, and what it changed from and to.
- **Steps**:
  1. Read the top of `docs/changelog/CHANGELOG.md` to match the current `[Unreleased]`
     shape and style.
  2. Add one bullet: bold impact-first lead with `(#6792)`, then **Before:** the gate
     recorded "no changed files detected for this WP" for a planning-lane WP whose commit
     had in fact changed files; **After:** it records the planning-lane reason and states
     the committed diff was not inspected, still non-blocking and still without running a
     gate.
  3. Keep it under 1,200 characters; no headings, no sub-bullets needed.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes with T008.
- **Notes**: Do not claim the gate now inspects committed changes — it does not.

### Subtask T008 – `review-gates.md` planning-lane paragraph

- **Purpose**: The how-to is the operator's map of gate behaviour; it must describe this
  outcome where the neighbouring limitation is described.
- **Steps**:
  1. Read the pre-review gate section of
     `docs/development/how-to/review-gates.md`, especially the
     `> **Inherited limitation (#2741 …)**` note.
  2. Add a short paragraph (or a blockquote sibling of that note) stating: a
     `planning_artifact` WP resolves to the planning surface, so its merge-base diff against
     the target branch is empty by construction; the gate records a `no_coverage` verdict
     whose reason names the planning lane and says the committed diff was not inspected,
     and the transition is never blocked by it.
  3. Keep the inherited-limitation note accurate and adjacent: the working-tree-diff
     limitation is still unfixed for WPs whose work lands on the mission branch.
- **Files**: `docs/development/how-to/review-gates.md`.
- **Parallel?**: Yes with T007.
- **Notes**: Quote the reason verbatim so a grep of the code and the doc agree.

### Subtask T009 – Docs checks

- **Purpose**: Prove the docs surface is consistent.
- **Steps**: run from the repo root:
  - `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`)
  - `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
  Record the results in the WP history note.
- **Files**: none.
- **Parallel?**: No.
- **Notes**: If freshness reports an error caused by a concurrently regenerated shared
  cache, re-run once and report it; do not rewrite unrelated generated surfaces.

## Test Strategy

- Documentation-only package: the checks are the two commands in T009 plus a manual read
  that the quoted reason matches the shipped string exactly.

## Risks & Mitigations

- **Overclaiming** ("the gate now covers planning-lane commits") → quote the reason and
  state the limitation explicitly.
- **Changelog drift** (wrong placement, missing issue ref) → follow the existing
  `[Unreleased]` entries' shape.

## Review Guidance

- Confirm the changelog entry is under `[Unreleased]`, carries `(#6792)`, and is under
  1,200 characters.
- Confirm the doc's quoted reason matches the code verbatim.
- Confirm neither doc claims a behavioural change beyond the recorded reason.

## Progress & Status

Progress, history, and status live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
