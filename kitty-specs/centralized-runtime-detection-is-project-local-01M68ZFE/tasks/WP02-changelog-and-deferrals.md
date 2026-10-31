---
work_package_id: WP02
title: Changelog, deferrals and tracers
dependencies:
- WP01
requirement_refs:
- C-003
- SC-004
planning_base_branch: issue-6551-centralized-runtime-detection-is-project-local
merge_target_branch: issue-6551-centralized-runtime-detection-is-project-local
branch_strategy: Planning artifacts for this mission were generated on issue-6551-centralized-runtime-detection-is-project-local. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6551-centralized-runtime-detection-is-project-local unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Close-out surfaces
history:
- at: '2026-10-30T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/traces/**
role: documenter
tags: []
task_type: plan
tracker_refs: []
---

# Work Package WP02 – Changelog, deferrals and tracers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documenter`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Review Feedback

**Read this first if you are working on this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

- `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry for this fix:
  bold impact-first lead ending `(#6551)`, then before/after, under 1,200
  characters. Root `CHANGELOG.md` is a symlink to it — edit the real file.
- The out-of-scope halves of the issue are captured where the PR body can quote
  them verbatim.
- The three mission tracer files exist and carry this mission's entries.

## Context & Constraints

- Spec `kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/spec.md`
  (C-003 lists the deferrals), research decisions D-1..D-4.
- No ADR: this restores a documented invariant rather than changing a structural
  boundary. Do not regenerate `docs/api/cli-commands.md` — no CLI surface moves,
  and the shared global asset cache that a full rebuild reads is written by other
  agents concurrently on this host.
- Verify docs freshness with
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`)
  rather than trusting a full rebuild.

## Branch Strategy

- **Strategy**: single-branch mission on a topic branch
- **Planning base branch**: `issue-6551-centralized-runtime-detection-is-project-local`
- **Merge target branch**: `issue-6551-centralized-runtime-detection-is-project-local`

> Populated by `spec-kitty agent mission finalize-tasks`; do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T007 – Changelog entry

- **Purpose**: The user-facing record of a behaviour change: `upgrade` no longer
  depends on the operator's home.
- **Steps**: Add one bullet under `[Unreleased]` in
  `docs/changelog/CHANGELOG.md`. Shape: bold impact-first lead naming the fixed
  symptom, ending `(#6551)`; then "Before:" and "After:" sentences. Name the
  observable symptom (an upgrade on a machine with no `~/.kittify` copying the
  packaged missions in and auto-committing them as `.kittify/overrides/`), not
  the helper name.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes, with T008/T009.
- **Notes**: Under 1,200 characters. Match the surrounding entries' formatting
  exactly; do not add a heading.

### Subtask T008 – Deferrals

- **Purpose**: Name the parts of #6551 this PR deliberately does not do, with
  reasons, so the operator can decide.
- **Steps**: Write the three items where the PR body will quote them:
  1. Repair of already-affected projects (22 package copies already in
     `.kittify/overrides/missions/`) — out of scope, tracked by #6548; the
     issue's "ledger `success` record later than the stamped version" marker is a
     suggestion for that issue, not this one.
  2. `2.1.3_restore_prompt_commands`, `2.1.4_enforce_command_file_state` and
     `3.1.2_globalize_commands` also read `get_kittify_home()` directly and were
     not measured under this trigger — a follow-up regression test, not a
     speculative change bundled into a one-predicate fix.
  3. The issue's alternative remedy (treat `skipped` as settled for migrations
     whose `target_version` is below the project's stamp) — rejected in research
     D-1 because it changes ledger selection semantics that ADR
     `2026-10-17-1` §3 and C-001 freeze.
- **Files**: `kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/traces/design-decisions.md`
  — **T008 is the single writer of this file**. T009 must not write it again.
- **Parallel?**: Yes.
- **Notes**: This file is also the mission's design-decisions tracer; one file,
  two purposes, no duplication.

### Subtask T009 – Tracer entries

- **Purpose**: Mission hygiene (charter Standing Order #3).
- **Steps**: Create/append the three tracer files under
  `kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/traces/`
  using `spec-kitty agent tracer-append --mission
  centralized-runtime-detection-is-project-local-01M68ZFE --category
  approach|design-decisions|tooling-friction --entry "<text>"`. At minimum:
  - `approach`: the predicate-order decision and the two-tier test plan.
  - `tooling-friction`: whatever actually bit — for example `spec-commit`
    refusing a main-targeted mission until `meta.json` `target_branch` was
    pointed at the topic branch, or `tracer-append` requiring `--actor`.
  - Do **not** append a `design-decisions` entry: T008 already owns that file
    (finding D1 in `analysis-report.md`); duplicate writers would double the
    record.
- **Files**: `kitty-specs/.../traces/*.md`.
- **Parallel?**: No (last).
- **Notes**: Record only what happened; do not invent friction.

## Test Strategy

- No code. Verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci` and
  `tests/architectural/test_no_legacy_terminology.py` if the entry introduces a
  term.

## Risks & Mitigations

- Changelog entry over the character cap → keep it to lead + before + after.
- Docs freshness noise from the shared cache → verify with the `--ci` checker
  (errors=0) rather than a full rebuild, and say so if a regeneration looks
  non-deterministic.

## Review Guidance

- The changelog entry must name the symptom a user sees, not the helper.
- The deferrals must each carry a reason and, where one exists, an issue number.
- No generated docs surface may be rewritten by hand.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
