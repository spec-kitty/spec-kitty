---
work_package_id: WP01
title: Research owned-checkout placement (#5882)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- SC-001
- SC-002
planning_base_branch: issue-5882-owned-research-placement-and-plan
merge_target_branch: issue-5882-owned-research-placement-and-plan
branch_strategy: Planning artifacts for this mission were generated on issue-5882-owned-research-placement-and-plan. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5882-owned-research-placement-and-plan unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Research placement
history:
- at: '2026-10-12T22:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/research.py
create_intent:
- tests/integration/test_owned_research_placement.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/research.py
- tests/integration/test_owned_research_placement.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5882'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP01 – Research owned-checkout placement (#5882)

## Objectives & Success Criteria

- `spec-kitty research` accepts `--owned-checkout <P>` and, when run from inside an owned checkout, auto-adopts it (FR-001, FR-002).
- For an owned run, `research.md` / `data-model.md` / the two research CSV stubs are scaffolded under `owned.mission_dir`; nothing is resolved, read, or written under `repository_root/kitty-specs` (FR-003, SC-001, SC-002).
- An invalid owned target refuses via `emit_owned_refusal` before any `mkdir`/copy (NFR-003).
- The non-owned path is byte-for-byte behaviour-identical; `tests/specify_cli/cli/commands/test_research_read_surface.py` stays green (NFR-001).
- Ownership resolved only through the existing `_owned_checkout` / `core.owned_mission` seam; no new resolver (NFR-002, C-001). `ruff`/`mypy` clean on changed files.

## Context & Constraints

- Grounding + provenance: `../analysis-report.md` (§2 Surface A) and `../plan.md` IC-01.
- Reproduction (already RED on the base): `tests/integration/test_owned_research_placement.py` — `test_research_accepts_owned_checkout_and_scaffolds_into_owned` and `test_research_from_owned_cwd_does_not_redirect_into_dirty_primary`, built on the canonical `owned_checkouts` / `stale_root_copy` / `r_snapshot` fixtures.
- Root cause (origin/main `research.py`): `research(...)` (170-177) exposes only `--mission`/`--force`; `repo_root = find_repo_root()` (183) + `get_project_root_or_exit` (188) follow the owned worktree's `.git` pointer to the PRIMARY; the three `_read_mission_dir_or_exit(repo_root, slug, kind)` calls (212 STATUS_STATE, 248 RESEARCH, 261 FINALIZED_EXECUTION_PLAN) key the placement seam on the primary root with no `owned=`.
- Pattern to MIRROR (do NOT invent a new resolver, C-001): `mission_record_analysis.py` (option → `resolve_owned_or_refuse`/`resolve_owned_or_adopt` → `repo_root = owned.owned_root` → `placement_seam(repo_root, slug, owned=owned)`) and `mission_setup_plan.py` (owned → read dirs resolve to `owned.mission_dir`). Use `resolve_owned_or_adopt` so a flagless run from inside an owned checkout adopts it and a run from the primary keeps repo-root behaviour.
- Charter: C-001 single resolver / no `core/paths.py` change; DIRECTIVE_024 locality; smallest-viable-diff.

## Subtasks & Detailed Guidance

### Subtask T001 – ATDD: owned research placement reproduction (RED first)

- **Purpose**: Pin the containment invariant before the fix.
- **Status**: the reproduction file already exists and is RED on the base (`No such option: --owned-checkout`; flagless run resolves the primary). Confirm RED on the WP base and record the failure output.
- **Validation**: `.venv/bin/python -m pytest tests/integration/test_owned_research_placement.py -q` → both tests RED.

### Subtask T002 – Add `--owned-checkout` to `research`; resolve ownership once

- **Purpose**: Resolve ownership at the CLI boundary and carry the fact down.
- **Steps**: Add `owned_checkout: OwnedCheckoutOption = None` to `research(...)`. After `repo_root = find_repo_root()`, resolve once via `resolve_owned_or_refuse(repo_root, owned_checkout, mission, cwd=Path.cwd(), allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES, json_output=False, envelope=...)` (research has no `--json`; render the refusal on stderr). When `owned is not None`, set `project_root = repo_root = owned.owned_root`.
- **Files**: `src/specify_cli/cli/commands/research.py`.

### Subtask T003 – Thread `owned=` through the placement seam + validate owned plan

- **Purpose**: Make every mission-dir resolution and the plan-filled gate honour the owned fact.
- **Steps**: Give `_read_mission_dir_or_exit` an optional `owned: OwnedCheckout | None = None` and forward it as `placement_seam(repo_root, slug, owned=owned).read_dir(kind)`; pass `owned=owned` at all three call sites (STATUS_STATE, RESEARCH, FINALIZED_EXECUTION_PLAN). The RESEARCH `planning_dir` is where the four assets are written; the FINALIZED_EXECUTION_PLAN dir is where `validate_plan_filled` reads `plan.md` — both now land on `owned.mission_dir`. Keep `_write_research_asset` unchanged (it already writes under `planning_dir`).
- **Files**: `src/specify_cli/cli/commands/research.py`.

### Subtask T004 – Validate green (owned + non-owned read-surface)

- **Steps**: `.venv/bin/python -m pytest tests/integration/test_owned_research_placement.py tests/specify_cli/cli/commands/test_research_read_surface.py tests/research -q` (owned GREEN, non-owned read-surface unchanged). `make format-check-files FILES=src/specify_cli/cli/commands/research.py`; `ruff check src/specify_cli/cli/commands/research.py`; `mypy` on the changed file (attribute only NEW diagnostics vs the #5917 baseline).

## Definition of Done

- Repro RED on base → GREEN on final commit; non-owned research behaviour unchanged; refusals fire before writes; lint/type clean (no NEW mypy vs #5917).

## Reviewer Guidance

- Confirm no `find_repo_root`/`get_project_root_or_exit` result reaches the placement seam for an owned run (all three `_read_mission_dir_or_exit` calls thread `owned=`); confirm `resolve_owned_or_refuse`/`_adopt` (not a new resolver); confirm R-immutability holds against a stale primary copy.
