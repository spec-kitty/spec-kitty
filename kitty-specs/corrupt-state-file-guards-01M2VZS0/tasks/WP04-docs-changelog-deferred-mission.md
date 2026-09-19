---
work_package_id: WP04
title: Docs/CHANGELOG + deferred-mission filing
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-004
planning_base_branch: fix/4642-corrupt-state-file-guards
merge_target_branch: fix/4642-corrupt-state-file-guards
branch_strategy: Planning artifacts for this mission were generated on fix/4642-corrupt-state-file-guards. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/4642-corrupt-state-file-guards unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
history:
- by: orchestrator
  at: '2026-09-19T05:00:00Z'
  note: 'Authored from IC-5 (mission corrupt-state-file-guards, #4642).'
agent_profile: scribe-sally
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load` (profile: `scribe-sally`, role: `implementer`).

## Objective

Close out the mission's user-facing paper trail: a `[Unreleased]` CHANGELOG entry for #4642, and file + link the deferred hardening mission that closes the whole corrupt-state class (subsuming #4600 + #4642).

## Subtasks

### T014 — CHANGELOG entry
Add a `[Unreleased]` entry to the canonical `docs/changelog/CHANGELOG.md` (repo root `CHANGELOG.md` is a symlink). Impact-first bold lead with the `(#4642)` ref, then before→after:
- Before: a corrupt per-mission `meta.json` crashed `spec-kitty next`, and a corrupt `decisions/index.json` crashed `agent decision verify`/`resolve`, with raw Python tracebacks.
- After: both fail closed with a single operator-readable error (fail-closed message + `run: spec-kitty doctor`) and a non-zero exit.
Match the file's existing `**asterisk**` emphasis convention (its markdownlint MD049 findings are non-blocking).

### T015 — File + link the deferred hardening mission
File a GitHub issue for the deferred class-closer (canonical guarded-read primitive `read_json_state()` + single CLI corrupt-state presentation seam + audit of the partial-guard non-UTF-8 tail: `decisions/service.py`, `merge/state.py`, `review/baseline.py`, and the fully-unguarded `review/lock.py`, `review/artifacts.py`, `status/validate.py`, plus `wps_manifest.py`). State that it subsumes #4600 and #4642 as one class. Record the issue number in the PR body (this is an action, not a file edit).

## Branch Strategy

Planning/base branch and final merge target: `fix/4642-corrupt-state-file-guards`.

## Definition of Done

- [ ] `[Unreleased]` CHANGELOG entry present, impact-first, `(#4642)` ref, before→after.
- [ ] Deferred hardening mission filed; issue number recorded for the PR body.

## Risks / Reviewer guidance

- Depends on WP01–WP03 landing (describe shipped behavior accurately).
- This is a `planning_artifact` WP — its only owned file is under `docs/`; the issue-filing is an action performed during the WP, not a tracked file.
