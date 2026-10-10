---
work_package_id: WP05
title: Owned record-analysis recording and material/charter authority
dependencies:
- WP04
requirement_refs:
- C-001
- C-002
- C-003
- C-004
- FR-006
- FR-006a
- FR-008
- NFR-002
- NFR-003
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
- T021
- T022
- T023
phase: Phase 5 - Analysis recording
history:
- at: '2026-10-10T06:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_record_analysis.py
create_intent:
- tests/integration/test_owned_analysis_recording.py
- tests/integration/test_analysis_template_mirrors.py
- tests/integration/test_owned_charter_generation.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- src/specify_cli/git/report_transaction.py
- src/specify_cli/analysis_inputs.py
- src/specify_cli/cli/commands/charter/generate.py
- tests/integration/test_owned_analysis_recording.py
- tests/integration/test_analysis_template_mirrors.py
- tests/integration/test_owned_charter_generation.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5893'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP05 – Owned record-analysis recording + material/charter authority (#5893)

> Operator decision D3: include BOTH halves (recording + material/charter authority). Keep the guard relaxation EXACTLY as reviewed (package-identical GLOBAL mirror only) — do NOT widen toward the separate #5253/#5380 external-authority classes (C-002).

## Objectives & Success Criteria

- Recording (FR-006): `record-analysis` resolves the owned mission, reads material/charter inputs from the owned checkout, writes the wrapped report under `owned.mission_dir`, and commits it on `owned.write_branch`; the primary/sibling stay unchanged; dirty/raced material still refuses (`DIRTY_ANALYSIS_INPUT`).
- Authority (FR-006a): a package-identical GLOBAL template mirror is admitted as a material input with a `template-selection:<kind>` freshness identity (byte-compared to the package default), and `charter generate` honours `--owned-checkout`/`--mission-handle` destinations (validated in the owned checkout before any write).
- Non-owned behaviour and external-authority guards (beyond the reviewed mirror) preserved (FR-008, C-002); `ruff`/`ruff format`/`mypy --strict` clean (NFR-002); terminology guard green (C-004).

## Context & Constraints

- Grounding + provenance: `../research.md` (row #5893), `../plan.md` IC-05.
- Repair commits to land-and-verify:
  - Recording: `codex/owned-analysis-recording` fix `2084975b9` + test `2bfa4c485`. **Adopt-as-is** — base blobs byte-identical to origin/main; all seam deps present (`placement_seam(..., owned=)`, `preflight_commit(..., owned=)`, `commit_for_mission(..., owned=)` → `resolve_for_owned`).
  - Authority: `codex/owned-analysis-authority` fix `9dafc88d3` + test `627c01acc`. **Adopt-with-rebase** — real drift on `analysis_inputs.py`: `DoctrineService`→`ActiveCharterService`, `CharterPackConfigError`→`ActiveCharterConfigError`, and `_declared_paths(source=)`. Re-point those names when porting; re-verify `charter/generate.py` after the rename drift.
- Root cause (origin/main): `mission_record_analysis.py` L355 `get_main_repo_root(repo_root)` fold before `_find_feature_directory` L362; placement L434 + commit routing have no `owned`; `analysis_inputs.py::_resolved_template_paths` hard-raises `MaterialInputError("External mutable global template authority is unsupported")` for any GLOBAL tier.
- Model: `placement_seam(repo_root, slug, owned=owned).read_dir(kind)` (reads `owned.mission_dir`, never `get_main_repo_root`); `commit_for_mission(..., owned=)` → `resolve_for_owned`. `accept.py`/`review/cycle.py` thread the same fact.
- Charter: C-001 single resolver / no `core/paths.py`; C-002 scope fence; C-003 ATDD red-first; C-004 terminology guard (this WP touches charter/analysis prose).

## Branch Strategy

- **Planning base branch**: main · **Merge target branch**: main. Runs in the write checkout.

## Subtasks & Detailed Guidance

### Subtask T019 – ATDD recording: port the owned analysis-recording reproduction (RED first)

- **Steps**: Port `tests/integration/test_owned_analysis_recording.py` (from `2bfa4c485`/`2084975b9`): `test_analysis_records_in_owned_write_branch` (explicit+default × report_only) — report commits on owned HEAD, primary/sibling unchanged, `resolve_ownership_claim` called exactly once, charter hash matches the owned checkout; `test_report_only_material_dirt_refuses_before_write` (`DIRTY_ANALYSIS_INPUT`); `test_invalid_claim_refuses_before_writes`; symlink/foreign → `OWNED_MISSION_PATH_REFUSED`. RED on base (`FEATURE_CONTEXT_UNRESOLVED`).

### Subtask T020 – Recording fix: thread owned through discovery/placement/commit

- **Steps**: Apply `2084975b9`: add `owned_checkout: OwnedCheckoutOption` to `record_analysis`; replace the `_find_feature_directory` block with `resolve_owned_or_refuse(...)` + new `_record_analysis_feature_dir` (validate `owned.mission_dir/ANALYSIS_REPORT_FILENAME` via `owned.files(...)`); when owned rebind `repo_root = cwd_repo_root = owned.owned_root` and thread `owned=` into `placement_seam`, the preflight (uses `owned.topology`), `_commit_analysis_report`/`_run_report_only` (`target_branch = owned.write_branch`), adding `stale_copy_payload`. In `report_transaction.py`: add `owned=`, `_owned_canonical_inputs`/`_canonical_inputs_changed`/`_canonical_charter_dirt`; thread `owned=` into `placement_seam`/`preflight_commit`/`_commit_report`; surface `ActionContextError.code` as `error_code`.
- **Files**: `src/specify_cli/cli/commands/agent/mission_record_analysis.py`, `src/specify_cli/git/report_transaction.py`.

### Subtask T021 – ATDD authority: port the template-mirror + owned-charter reproductions (RED first)

- **Steps**: Port `tests/integration/test_analysis_template_mirrors.py` + `tests/integration/test_owned_charter_generation.py` (from `627c01acc`): a package-identical GLOBAL template mirror is admitted with a `template-selection:<kind>` identity (`path is None`, no home leakage); swapping `get_kittify_home` invalidates freshness; `charter generate --owned-checkout --mission-handle` stays entirely in the owned checkout, refuses non-regular/symlink destinations before any write, and `--mission-handle` without `--owned-checkout` errors. RED on base (hard-raise).

### Subtask T022 – Authority fix (rebased): admit package-identical mirror, owned charter generate

- **Steps**: Apply `9dafc88d3` with the rename rebase: in `analysis_inputs.py`, `_resolved_template_paths` returns `(paths, selections)` and admits a package-identical GLOBAL/GLOBAL_MISSION mirror via new `_global_template_mirror` (symlink-hardened, byte-compared to the package default) instead of hard-raising, emitting `template-selection:<kind>` identities — re-point `DoctrineService`→`ActiveCharterService` / `CharterPackConfigError`→`ActiveCharterConfigError` and fold around `_declared_paths(source=)`. In `charter/generate.py`, add `--owned-checkout`/`--mission-handle`, `_resolve_generate_write_root` + `_validate_owned_charter_destinations` (whole write batch validated in the owned checkout before provisioning). Keep the relaxation limited to the byte-identical mirror; do not touch the deeper #5253/#5380 guards.
- **Files**: `src/specify_cli/analysis_inputs.py`, `src/specify_cli/cli/commands/charter/generate.py`.

### Subtask T023 – Validate green + terminology guard

- **Steps**: Run the three new integration files + the record-analysis/report-transaction/analysis-inputs/charter-generate test modules; `pytest tests/architectural/test_no_legacy_terminology.py`; format-check + ruff + mypy on changed files. Green.

## Definition of Done

- Recording + authority repros RED→GREEN; report commits owned; mirror admitted with freshness identity; external-authority guards (beyond the reviewed mirror) intact; terminology guard green; lint/type clean.

## Reviewer Guidance

- Confirm the GLOBAL-mirror relaxation is strictly byte-identical (no widening to #5253/#5380); confirm `charter generate` validates the whole write batch in the owned checkout before any provisioning; confirm no `core/paths.py` change.
