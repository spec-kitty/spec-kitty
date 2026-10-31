---
work_package_id: WP03
title: Design record and changelog
dependencies:
- WP02
requirement_refs:
- FR-002
- FR-004
planning_base_branch: issue-6464-protected-target-override-refusal
merge_target_branch: issue-6464-protected-target-override-refusal
branch_strategy: Planning artifacts for this mission were generated on issue-6464-protected-target-override-refusal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6464-protected-target-override-refusal unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
phase: Phase 3 - The record
history:
- at: '2026-10-31T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: documentation
tracker_refs:
- '6464'
---

# Work Package Prompt: WP03 – Design record and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing, and record what you changed with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

- ADR `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` records the new decision as a **dated
  follow-up** (never by rewriting the original text): the recorded-target preflight's
  "reads the recorded meta target, not `--target`" sentence is no longer the whole story — an override
  onto a protected branch that is not the recorded target is now refused before any branch moves, with
  the same `PROTECTED_BRANCH_REFUSED` code, and the unprotected-mismatch case stays a named residual.
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry: bold impact-first lead with `(#6464)`,
  then before/after, under 1,200 characters.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and
  `tests/architectural/test_no_legacy_terminology.py` passes.

## Context & Constraints

- Read first: `spec.md` (FR-002, FR-004), `plan.md`, `research.md` (D1–D5 and the residual list), and
  the ADR's existing "Follow-up 2026-09-30 — every post-mutation exit goes through A3 (#5385)" bullet
  **Protected-target preflight**. The ADR's residuals list is where the override gap was documented;
  replace that residual with the new rule and keep an honest residual for the unprotected-mismatch case.
- The changelog's current `[Unreleased]` section is at the top of `docs/changelog/CHANGELOG.md` (the
  root `CHANGELOG.md` is a symlink — edit the real file only). Match the file's existing entry shape:
  `- **<impact-first sentence>** (#6464). **Before:** … **After:** …`.
- Terminology: "mission", "consolidate", "target branch". Never "feature". Never re-describe `merge` as
  the command (it is a removed stub; the live command is `spec-kitty consolidate`).
- Do not regenerate the whole documentation surface (shared machine state: the global asset cache is
  being rewritten by other agents). Only run the freshness check, never a full docs rebuild.
- Keep the ADR edit additive: a new `### Follow-up 2026-10-31 — the branch-integration target is
  guarded too (#6464)` block with its bullets, plus the residual rewrite in the existing list.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6464-protected-target-override-refusal`
- **Merge target branch**: `issue-6464-protected-target-override-refusal`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with
`spec-kitty agent action implement WP03 --agent claude --mission protected-target-override-refusal-01M68JPV`.

## Subtasks & Detailed Guidance

### Subtask T009 – ADR follow-up

- **Purpose**: the design record a maintainer reads before reviewing the behaviour change.
- **Steps**:
  1. Append the dated follow-up block to `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md`
     after the 2026-09-30 follow-up, in the same voice and bullet style.
  2. State: what was unguarded (the branch-integration commit is a raw `git commit` in an ephemeral
     worktree, so the workflow mutation policy never sees it); the scope of the new guard (effective
     target differing from the recorded target **and** protected); the three entries that report it;
     that the recorded-target decision stays #5385's; and the residual (an override onto an unprotected
     branch still lands and then fails its bookkeeping).
  3. Do not change any earlier decision text.
- **Files**: `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md`

### Subtask T010 – Changelog entry

- **Purpose**: users and operators learn the behaviour change from the changelog.
- **Steps**:
  1. Add one bullet to `[Unreleased]` in `docs/changelog/CHANGELOG.md`, under 1,200 characters:
     bold impact-first lead with `(#6464)`, then **Before:** and **After:** in the file's existing style.
  2. Name the refusal code and the fact that it happens before any branch moves; mention the three
     entries (real run, `--dry-run`, `orchestrator-api`).
  3. Run `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0) and
     `uv run python -m pytest tests/architectural/test_no_legacy_terminology.py tests/docs -q` (or the
     narrowest docs-guard selection that covers the changelog lint).
- **Files**: `docs/changelog/CHANGELOG.md`

## Definition of Done

- The ADR follow-up exists, is dated, and leaves the original decision text untouched.
- The changelog entry passes the changelog guard and the docs freshness check (errors=0).
- Nothing outside `owned_files` is modified.

## Reviewer Guidance

- Does the ADR text match what the code actually does (scope, code name, entries)?
- Is the changelog entry impact-first, under 1,200 characters, with `(#6464)`?
- Is there any "feature" terminology or any resurrection of `spec-kitty merge` as a live command?
