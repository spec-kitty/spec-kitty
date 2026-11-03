---
work_package_id: WP02
title: Contract prose and changelog record
dependencies:
- WP01
requirement_refs:
- FR-006
- SC-003
- C-002
- C-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Contract record
history:
- at: '2026-11-03T13:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- docs/changelog/unreleased/6956-create-root-refusal.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/_owned_checkout.py
- docs/changelog/unreleased/6956-create-root-refusal.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6956'
---

# Work Package Prompt: WP02 – Contract prose and changelog record

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according
to its guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting; if
this WP was returned from review, resolve every feedback item first and record each with
`spec-kitty agent tasks add-history WP02 --note "..."`.

## Objectives & Success Criteria

- The two docstrings that document the create-level residual as a live hole describe the delivered
  behaviour instead, and say precisely what is and is not now shared.
- The user-visible refusal is recorded as one changelog fragment under
  `docs/changelog/unreleased/`, in assemble-ready form.
- The docs surfaces this change touches verify clean, and the plan states explicitly that no
  generated docs index needs regeneration (no public CLI surface changed).

## Context & Constraints

- Read first: `kitty-specs/owned-create-root-refuses-mission-worktree-01M6GRFM/spec.md` (FR-006),
  `research.md`, `plan.md` (IC-02), and the WP01 diff.
- Targets:
  - `src/specify_cli/core/owned_mission.py` — `resolve_owned_create_root`'s docstring currently says
    *"No branch or topology check: the mission does not exist yet"*; it must say that the claim now
    refuses a coordination or lane worktree and that no topology/branch decision is made;
  - `src/specify_cli/cli/commands/_owned_checkout.py` — `resolve_owned_op_record_root`'s docstring
    currently documents *"Known residual: because no Mission is bound, a registered coordination
    worktree or lane worktree is NOT refused here"*; that sentence is now false and must be
    replaced with what is true: the Mission-worktree legs are shared through the create minter, and
    what remains unvalidated for an Op command is the Mission, its topology and its write branch.
- Charter rules that bind this WP: proof trail (the docstring is the record), DIRECTIVE_024
  (locality — docstrings only, no behaviour change in this WP).
- `docs/changelog/unreleased/README.md` owns the fragment shape and naming. The fragment id is the
  PR number once it exists; before that, use `<issue>-<branch-slug>` (`6956-create-root-refusal`).
  Rename it to the PR number at wrap-up if the PR number is known before the branch is pushed.

## Branch Strategy

- **Strategy**: single_branch mission
- **Planning base branch**: `kitty/mission-owned-create-root-refuses-mission-worktree-01M6GRFM`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T007 – Retire the residual prose

- **Purpose**: stop the code from promising a hole that no longer exists, without over-claiming.
- **Steps**:
  1. Rewrite `resolve_owned_create_root`'s docstring: the claim check plus the Mission-worktree
     legs (coordination, lane), the code they raise, and the explicit statement that the create
     seam still makes no branch or topology decision because the Mission does not exist yet.
  2. Rewrite `resolve_owned_op_record_root`'s "Known residual" paragraph: the Mission-worktree legs
     now come from the shared create minter, so a coordination or lane worktree is refused; what an
     Op command still does not validate is the Mission, its topology and its write branch.
  3. Grep the tree for other copies of the retired claim
     (`grep -rn "Known residual" src/ docs/`) and fix any that this change falsifies — do not edit
     historical notes under `docs/plans/` or `docs/archive/`.
- **Files**: `src/specify_cli/core/owned_mission.py`,
  `src/specify_cli/cli/commands/_owned_checkout.py`.
- **Notes**: docstrings only. If a prose fix would need a behaviour change, stop and report instead.

### T008 – Changelog fragment

- **Purpose**: the refusal is user-visible (`mission create --owned-checkout` now fails where it
  used to succeed), so it belongs in the assembled changelog.
- **Steps**: add `docs/changelog/unreleased/6956-create-root-refusal.fixed.md` holding exactly one
  entry in the house shape: a bold, impact-first lead with `(#6956)`, then **Before:** and
  **After:**, under 1,200 characters. Facts to state: before, `--owned-checkout` naming a
  registered coordination or lane worktree was admitted, so a create scaffolded a Mission inside
  another Mission's worktree and the refusal arrived only afterwards; after, the create claim
  refuses it with `OWNED_CHECKOUT_IS_MISSION_WORKTREE` before anything is scaffolded, while an
  ordinary linked owned checkout is unaffected. Do **not** edit `docs/changelog/CHANGELOG.md`.
- **Files**: the new fragment.
- **Notes**: US spelling; no heading inside the file.

### T009 – Verify the touched docs surfaces

- **Purpose**: prove the doc change costs no shared regeneration.
- **Steps**: run
  - `uv run --frozen python -m scripts.docs.check_changelog_style`
  - `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`
  - `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` (expect errors=0; this
    Mission adds no docs page and no CLI surface, so nothing should need regenerating — record the
    actual result)
- **Files**: none.
- **Notes**: the installed CLI's global asset cache is shared with other agents; do **not** run a
  full `docs/api/cli-commands.md` rebuild. If freshness reports drift caused by another agent's
  concurrent run, say so instead of rebuilding the shared surface.

## Definition of Done

- T007–T009 complete and recorded.
- No docstring in `src/` still claims a coordination or lane worktree is admitted by the create
  claim.
- The changelog fragment passes style and spelling checks, and the freshness check result is
  recorded verbatim.
