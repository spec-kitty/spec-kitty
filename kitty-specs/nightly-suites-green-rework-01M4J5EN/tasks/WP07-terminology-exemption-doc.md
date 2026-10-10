---
work_package_id: WP07
title: Terminology-exemption doc coverage (#5990)
dependencies: []
requirement_refs:
- FR-009
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
phase: Phase 2 - Doc sync
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/development/reference/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-5-5
owned_files:
- docs/development/reference/terminology-exemptions.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Terminology-exemption doc coverage (#5990)

## ⚡ Do This First: Load Agent Profile
Use `/spk-charter-profile-load` to load `curator-carla` (implementer, claude).

## Objectives & Success Criteria

`test_terminology_exemption_policy_doc_is_present_and_consistent` (nightly `interpreter-3.13-shard-4`, #5990) requires the policy doc `docs/development/reference/terminology-exemptions.md` to contain a token for **every** `docs/` exempt root in `FORBIDDEN_SCAN_ROOTS` (`tests/_support/terminology_scope.py`) plus `Unreleased`. It is RED because `docs/archive/` (added to the exempt roots) is undocumented.

Done when: the policy doc documents every `docs/` exempt root including `docs/archive/`, with rationale, and the test passes (FR-009).

## Context & Constraints
- This is a doc-sync fix (planning_artifact, docs/ only). Terminology canon applies — Mission not Feature; do not introduce retired terms.
- The test (`tests/contract/test_terminology_guards.py:559-593`) reads the doc at `docs/development/reference/terminology-exemptions.md` and derives the required tokens from `FORBIDDEN_SCAN_ROOTS` — cover every `docs/`-prefixed root, not just `docs/archive/`.
- **Adversarial finding F5 (red herring — do NOT act on it)**: the test's line-578 assertion about `docs/development/terminology-exemptions.md` is satisfied by the test file's OWN source literal — it does NOT require a doc at that path. Do **NOT** create a second doc there. The only real assertion is token coverage in the existing `.../reference/...` doc. The full required `docs/` root set is: `docs/migrations/`, `docs/adr/`, `docs/archive/`, `docs/plans/engineering-notes/`, `docs/plans/initiatives/`, `docs/reports/` (plus `Unreleased`) — verify the 5 believed-existing tokens are still present so none silently regress; only `docs/archive/` is believed new.
- Match the authority phrasing already in the doc (FR-013; "every exempt surface must be documented"), and explain why `docs/archive/` is exempt (retired/relocated pages, #5428 context) and what the non-exempt remainder is.

## Subtasks
- **T020** — Read the current policy doc and `FORBIDDEN_SCAN_ROOTS`; add a documented entry for `docs/archive/` (and any other undocumented `docs/` exempt root), consistent with the existing section style and the exempt/non-exempt rationale pattern.
- **T021** — Verify the guard test green (it derives the token set from the shared list, so confirm every `docs/` root is covered).

## Branch Strategy
Planning base / merge target: `fix/nightly-suites-green-rework`. Lane from `lanes.json`.

## Validation
```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  "tests/contract/test_terminology_guards.py::test_terminology_exemption_policy_doc_is_present_and_consistent"
# pre-push terminology guard:
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/architectural/test_no_legacy_terminology.py
```

## Definition of Done
Every `docs/` exempt root documented; guard test green; no legacy/retired terms introduced.

## Reviewer Guidance (opus)
Confirm every `docs/` root in `FORBIDDEN_SCAN_ROOTS` is covered (not just `docs/archive/`), the rationale is real, and terminology canon holds.
