---
work_package_id: WP05
title: Drift/staleness findings, packaging safety, ADR acceptance, docs
dependencies:
- WP04
requirement_refs:
- FR-012
- FR-014
- SC-002
- SC-004
- NFR-001
- NFR-003
planning_base_branch: claude/festive-babbage-lhkqac
merge_target_branch: claude/festive-babbage-lhkqac
branch_strategy: Planning artifacts for this mission were generated on claude/festive-babbage-lhkqac.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into claude/festive-babbage-lhkqac unless
  the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
history:
- at: '2026-10-04T10:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/pack_skill_drift.py
create_intent:
- src/specify_cli/skills/pack_skill_drift.py
- tests/specify_cli/skills/test_pack_skill_drift.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/pack_skill_drift.py
- src/specify_cli/cli/commands/doctor.py
- tests/specify_cli/skills/test_pack_skill_drift.py
- tests/cross_cutting/packaging/test_packaging_safety.py
- docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md
- docs/changelog/CHANGELOG.md
- docs/context/**
- src/charter/offering/skills/README.md
- src/specify_cli/upgrade/assessment.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Drift/staleness findings, packaging safety, ADR acceptance, docs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role implementer) and behave according to its guidance before parsing the rest of this prompt.

## Objective

Deliver FR-012, FR-014, SC-002, SC-004, NFR-001, NFR-003 of mission `pack-skills-kind-01M43419` (see `../spec.md`, `../plan.md`, ADR `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`).

## Branch Strategy

Planning branch and final merge target: `claude/festive-babbage-lhkqac`. Topology `single_branch`: work happens in the repository root checkout; prepare with `spec-kitty agent action implement WP05 --agent claude`.

## Subtasks

### T020

pack_skill_drift.py: findings for (a) rendered copy whose bytes hash ≠ manifest content_hash (drift, points at source_ref) and (b) prepared source_hash ≠ manifest source_hash (staleness, points at source_ref). Surface in `doctor skills` (doctor.py:282) and upgrade assessment output. Tests for both + clean case.

### T021

Packaging safety: add explicit assertion no `packs/internal/skills/` path in wheel (test_packaging_safety.py).

### T022

ADR → Accepted (status front-matter + body), resolve open questions with plan decisions 1–3; note #2470 supersession remains owner call. Update src/charter/offering/skills/README.md to mention pack skills. CHANGELOG [Unreleased] entry `(#5193)` bold impact-first. Run scripts/docs/docs_index.py --write, scripts/docs/check_docs_freshness.py --ci, tests/architectural/test_no_legacy_terminology.py.

### T023

Quality sweep: ruff check, ruff format --check --force-exclude on changed files, mypy on changed modules, complexity ≤15; make test-fast + targeted dirs (tests/charter tests/doctrine tests/specify_cli/skills + specific architectural gates). Record commands/counts in the mission tracer.

## Amendments (post-tasks anti-laziness squad — binding)

- WP05 owns upgrade/assessment.py surfacing. Tests hit the real surfaces (`doctor skills` and the upgrade assessment) and assert each finding names `source_ref`. Backward-compat: an old manifest without origin/source_* produces no false drift.

## Definition of Done

- Every subtask done; new branches/helpers carry focused tests in the same commit (Sonar new-code gate).
- `ruff check`, `ruff format --check --force-exclude <changed files>`, `mypy` on changed modules: zero findings; complexity ≤15; no new suppressions.
- Targeted tests for touched modules plus owning subsystem dirs pass; record commands and counts in the activity log.
- Layer direction respected: `charter` never imports `specify_cli`.

## Risks

- Exact-set/totality tests across `tests/charter`, `tests/doctrine`, `tests/architectural` enumerate kinds — find them by running those directories' fast tier.
- Out-of-map edits are allowed only with a one-line rationale in the activity log.

## Reviewer Guidance

Verify each requirement in the objective has a non-vacuous test; reject no-op passes.

## Activity Log

