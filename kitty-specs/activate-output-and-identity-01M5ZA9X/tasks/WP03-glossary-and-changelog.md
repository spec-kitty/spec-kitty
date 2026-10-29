---
work_package_id: WP03
title: Glossary PACK_LEVEL_MISSING correction and changelog
dependencies: []
requirement_refs:
- FR-010
planning_base_branch: issue-6457-activate-output-identity
merge_target_branch: issue-6457-activate-output-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6457-activate-output-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6457-activate-output-identity unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
phase: Phase 1 - Implementation
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/context/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/context/governance.md
- docs/context/charter.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Glossary PACK_LEVEL_MISSING correction and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `scribe-sally` (implementer, `claude`) before reading further.

## Review Feedback

*[Filled from the status event log when returned from review.]*

## Objectives & Success Criteria

- FR-010: `docs/context/governance.md` (**Pack Level**, line ~79) and `docs/context/charter.md` (**Charter Pack**, line ~54) keep `PACK_LEVEL_MISMATCH` as a refusal and describe `PACK_LEVEL_MISSING` (a `pack.yaml` with no `pack_level`, or an org pack with no `pack.yaml`) as a non-blocking diagnostic during the deprecation window of ADR 2026-10-11-2: a warning on load and an advisory in `charter pack validate`, with the configured level used. It becomes a refusal once that window closes.
- Do NOT promise that flipping the validator switch (`_PACK_LEVEL_MISSING_IS_ERROR`) alone changes load-time behaviour (the org-loader warning branches do not consult it; #6403 triage).
- C-003: no other wording change (the "tier" wording is #6439).
- Changelog: `docs/changelog/CHANGELOG.md` `[Unreleased]` gets entries for #6457, #6458, #6459, #6403 in the file's existing style (read the section first; run `make docs-lint`).

## Context & Constraints

- Code truth: `src/charter/offering/drg/org_pack_loader.py:528-555` (warn + load for both cases), `src/charter/offering/packs/pack_validator.py:706` and `:759-767` (advisory severity behind the switch).
- Agreed behaviour for the changelog: see `spec.md` and the WP01/WP02 prompts. Changelog wording: plain, user-facing, Mission terminology.

## Branch Strategy

- **Planning base branch**: issue-6457-activate-output-identity · **Merge target**: issue-6457-activate-output-identity.

## Subtasks & Detailed Guidance

### Subtask T011 – governance.md Pack Level

Replace only the sentence starting "Loading refuses a pack whose declared level disagrees ..." through the end of the deprecation-warning clause. Suggested wording (from #6403):

> Loading refuses a pack whose declared level disagrees with where it is configured (`PACK_LEVEL_MISMATCH`). A `pack.yaml` that omits the field, or an org pack with no `pack.yaml`, is reported as `PACK_LEVEL_MISSING`: during the deprecation window of ADR 2026-10-11-2 that is a non-blocking diagnostic (a warning on load, an advisory in `charter pack validate`) and the configured level is used. Once the window closes it becomes a refusal.

### Subtask T012 – charter.md Charter Pack

Same replacement for the equivalent sentence.

### Subtask T013 – Changelog + lint

Add the `[Unreleased]` entries; run `make docs-lint` and `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`.

## Review Guidance

- Compare each sentence against the cited code lines; check no "tier" edit slipped in.
