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

- 2026-10-04 claude (python-pedro, WP05) -- implemented T020-T023 plus the read-only temp-root follow-up.
  - T020: `skills/pack_skill_drift.py` (`find_pack_skill_findings`): drift (installed bytes hash != manifest `content_hash`) and staleness (read-only `stage=False` prepared `source_hash` != manifest `source_hash`), each naming `source_ref`; absent files, builtin/old manifests (no origin/source_*), pack entries without `source_hash`, unresolvable catalog -> no finding. Surfaced in `doctor skills` (`pack_skills` JSON key, human "Pack skills" section, `ok` false -> exit 1) and in the upgrade assessment as non-blocking `warning` diagnostics (`pack_skill_drift` / `pack_skill_stale`; also in the upgrade `--json` diagnostics).
  - T021: `test_wheel_ships_no_internal_pack_skills` (slow, inspects the built wheel like its neighbours) plus a fast config-level twin `test_wheel_config_only_includes_built_in_pack_skills` (pyproject include/force-include scoped to `packs/built-in`).
  - T022: ADR 2026-09-27-1 -> Accepted (frontmatter, body, description); "Open questions" replaced by "Resolved questions": project namespace = required key `charter_packs.project.skill_namespace` (org `skill_namespace` also required); run-time binding placeholders deferred to slice 2; `/name` finding: `capability_matrix.py` records only native named-agent primitives and says nothing about `/name` exposure, the only in-repo record is the AGENTS.md command-surface table (Codex `$name`, Pi `/skill:name`, Vibe `/name`, Letta model-routed), so no `/name` promise is made; #2470 supersession left as owner's call. `prepare_skill_activations` reworded to `prepare_project_skill_activations` in ADR, plan.md, spec.md. Skills README gained a "Pack Skills" section. CHANGELOG `[Unreleased]` Added entry with `(#5193)`. `docs_index.py --write` (no drift; retrieval-index regenerated), `check_docs_freshness.py --ci` errors=0 (12 pre-existing link-health warnings, HTTP 403), `test_no_legacy_terminology.py` passed (both need `PYTHONPATH=.`).
  - Follow-up: `catalog._stage_read_only` now uses one lazily created per-process temp root (`_READ_ONLY_ROOT`, single `atexit` registration), cleared on every resolution; a registry from an earlier read-only resolution is valid only until the next one (documented). Test `test_read_only_resolution_reuses_one_cleared_temp_root`.
  - Tests (passed/failed): `tests/specify_cli/skills/test_pack_skill_drift.py` 9 passed (CLI-runner `doctor skills`, `prepare_upgrade_repairs`, clean, backward-compat); `test_packaging_safety.py -m "not slow"` + drift 10 passed; fast tier `tests/specify_cli/skills tests/upgrade tests/cross_cutting/packaging` + doctor tests (`test_doctor_slash_commands`, `test_doctor_cli_surface_golden`, `test_cli_boundary_json_seam`) -> 1248 passed, 1 failed (pre-existing `test_readonly_gitignore_clear_error`); gate files (`test_layer_rules`, `test_no_dead_symbols`, `test_no_dead_modules`, `test_ratchet_baselines`, `test_skill_catalog_seam`, `test_no_legacy_terminology`) 278 passed + 1 red caught (KIND_* in `__all__` unimported -> trimmed `__all__`), re-run dead-symbol/dead-module gates 40 passed; `make test-fast` once -> 2251 passed, 8 skipped, 0 failed. Slow wheel test not run (needs a build).
  - Lint: whole-repo `ruff check .` and `ruff format --check .` clean; mypy clean on pack_skill_drift.py and catalog.py. No new suppressions; complexity well under 15.
  - Out-of-map edit: `src/specify_cli/cli/commands/_command_surface_doctor.py` (the real body of `doctor skills`; `doctor.py` only delegates, so findings are wired there); `src/specify_cli/skills/catalog.py` (the requested follow-up); `kitty-specs/.../plan.md`, `spec.md` (rewording, docs); `docs/development/docs-retrieval-index.yaml` (generated).
  - Deviations: none beyond the above. Note the process caveat: findings are only as fresh as read-only resolution; absent-file and unresolvable-catalog cases are reported by the verifier/assessment, not here.
- 2026-10-04 reviewer (reviewer-renata/opus): cycle 1 REJECT (shared read-only temp root invalidated held registries → upgrade precondition_changed). Fix d1a2373c (content-addressed read-only staging). Cycle 2 APPROVE; red-proof: pre-fix catalog.py fails test_prepare_then_apply_upgrade_with_active_pack_skill_is_not_invalidated with precondition_changed. Slow wheel test passed.
