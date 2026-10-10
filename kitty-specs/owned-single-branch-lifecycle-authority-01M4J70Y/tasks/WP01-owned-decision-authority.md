---
work_package_id: WP01
title: Decision Moment owned authority (host CLI + orchestrator-api)
dependencies: []
requirement_refs:
- C-001
- C-003
- FR-001
- FR-008
- NFR-002
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Decision entry points
history:
- at: '2026-10-10T06:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/specify_cli/cli/commands/test_decision_owned_checkout.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/decision.py
- src/specify_cli/decisions/service.py
- src/specify_cli/decisions/emit.py
- src/specify_cli/orchestrator_api/decision_verbs.py
- tests/specify_cli/cli/commands/test_decision_owned_checkout.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5874'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP01 – Decision Moment owned authority (#5874)

## Objectives & Success Criteria

- `agent decision open/resolve/defer/cancel/verify/list` (host CLI, `decision.py`) resolves an owned single_branch mission from the owned checkout and writes the ledger + `status.events.jsonl` under `owned.mission_dir`; nothing is written under `repository_root/kitty-specs` or `repository_root/.worktrees` (FR-001).
- The same owned authority is threaded through `orchestrator_api/decision_verbs.py` open/resolve/defer/cancel/verify/list (operator decision D2 — the repair branch omitted this).
- Non-owned and coordination missions keep current behaviour; invalid owned claims refuse before any write (FR-008).
- Targeted tests green; `ruff` + `mypy --strict` clean (NFR-002).

## Context & Constraints

- Grounding + provenance: `../research.md` (row #5874) and `../plan.md` IC-01.
- Repair branch to land-and-verify: `codex/5874-owned-decisions`, fix `28e526d73` + test `a3ec03b59`. **Adopt-with-rebase**: `emit.py`/`service.py`/test auto-merge; `decision.py` has ONE import-line conflict — take the fix's superset (`OwnedCheckoutOption, resolve_owned_or_adopt, stale_copy_payload, echo_stale_copy_warning`). `main` already imports `OwnedCheckoutOption` for `cmd_widen`/`cmd_repair_runtime_lock`.
- Root cause (origin/main): `decision.py` verbs call `_resolve_repo_root_and_slug(mission)` with no owned threading (`cmd_open`, `cmd_resolve`, `cmd_defer`, `cmd_cancel`, `cmd_verify`, `cmd_list`); `_resolve_ledger_dir` folds through `placement_seam` to the repo root. `decisions/service.py` + `emit.py` path helpers call `placement_seam(repo_root, slug)` with no `owned=`. `orchestrator_api/decision_verbs.py` folds `_common._get_main_repo_root()` (lines ~268, 338, 398, 456, 630, 663).
- Model (same file): `cmd_repair_runtime_lock` / `cmd_widen` already thread `OwnedCheckoutOption`; mirror them but use `resolve_owned_or_adopt` (returns `None` for non-owned so default/coord missions keep working), per the fix.
- Charter: C-001 single resolver / no `core/paths.py` change; C-003 ATDD red-first; DIRECTIVE_024 locality.

## Branch Strategy

- **Planning base branch**: main · **Merge target branch**: main. Runs in the write checkout (single_branch); fields normalized by finalize-tasks.

## Subtasks & Detailed Guidance

### Subtask T001 – ATDD: port the owned decision reproduction (RED first)

- **Purpose**: Pin the owned lifecycle before the fix.
- **Steps**: Port `tests/specify_cli/cli/commands/test_decision_owned_checkout.py` from `a3ec03b59`. Core case `test_owned_complete_lifecycle` (parametrized `explicit=[True,False]`): run open→list→resolve→verify from the owned checkout and assert the 2 DecisionPoint events land in the owned `mission_dir`, and `repository_root/kitty-specs/<slug>` does NOT exist and `repository_root/.worktrees/*` is empty. Include `test_owned_dry_run_and_stale_primary`, `test_wrong_owned_checkout_refuses_before_writes`, `test_owned_escaped_ledger_refuses` (symlinked ledger → `OWNED_MISSION_PATH_REFUSED`), `test_owned_verify_still_reports_deferred_drift`.
- **Validation**: Run the file on the WP base — it must be RED (resolver folds to repo root). Record the failure.

### Subtask T002 – Thread owned through the host decision verbs

- **Purpose**: Resolve ownership once at the CLI boundary and carry it down.
- **Steps**: Apply `28e526d73`'s `decision.py` changes: add `owned_checkout: OwnedCheckoutOption = None` to the six verbs; add `_resolve_decision_context(mission_handle, owned_claim)` that validates once via `resolve_owned_or_adopt(repo_root, owned_claim, handle, cwd=..., allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)` and returns `(repo_root, owned.mission_dir.name, owned)`, falling back to `_resolve_repo_root_and_slug` when `owned is None`; thread `owned=` into every service call and `_resolve_ledger_dir(..., owned=owned)`; route output through `_echo_decision_payload` (stamps `stale_repository_root_copy`); `verify()` skips coordination fork-detection when owned. Resolve the import-line to the fix's superset.
- **Files**: `src/specify_cli/cli/commands/decision.py`.

### Subtask T003 – Thread owned through the decision service + emit placement

- **Purpose**: Make placement honour the owned fact.
- **Steps**: Apply `28e526d73`'s `service.py` + `emit.py` changes: add optional `owned: OwnedCheckout | None` to `_ledger_dir`, `_write_events_path`, `_write_mission_dir`, `_mission_dir`, `_events_path`, `_resolve_mission_id`, `open_decision`, `_terminal_command`, `resolve|defer|cancel_decision`, `emit_decision_*`; forward as `placement_seam(..., owned=owned)`; add `owned.files([...])` containment checks on the ledger dir, events path, and `DM-*.md` (raise `OWNED_MISSION_PATH_REFUSED` on escape).
- **Files**: `src/specify_cli/decisions/service.py`, `src/specify_cli/decisions/emit.py`.

### Subtask T004 – EXTEND: thread owned through the orchestrator-api decision verbs (#5874 D2)

- **Purpose**: Close the scope gap the repair branch left open.
- **Steps**: In `orchestrator_api/decision_verbs.py`, add an owned selector to `open_decision`/`resolve_decision`/`defer_decision`/`cancel_decision`/`verify_decision`/`list_decisions` and replace the `_common._get_main_repo_root()` fold (≈268/338/398/456/630/663) with the validated owned authority (mint via `resolve_owned_mission`/`resolve_owned_or_adopt`, thread `owned=` into the decision-service calls). Preserve the orchestrator-api envelope and non-owned behaviour. Add an owned-path case to the reproduction file (or a focused case) exercising the orchestrator-api verbs with no primary copy.
- **Files**: `src/specify_cli/orchestrator_api/decision_verbs.py`, test file.
- **Notes**: Keep the one-resolver rule — no second ownership resolver; reuse the existing seam.

### Subtask T005 – Validate green

- **Steps**: Run `tests/specify_cli/cli/commands/test_decision_owned_checkout.py` + the decision/orchestrator-api decision test modules; `make format-check-files FILES=<changed>`; `ruff check <changed>`; `mypy` on the changed files. All green.

## Definition of Done

- Repro RED on base → GREEN on final commit; orchestrator-api owned path covered; non-owned decision behaviour unchanged; refusals fire before writes; lint/type clean.

## Reviewer Guidance

- Confirm no `get_main_repo_root`/`_get_main_repo_root` fold remains reachable from an owned decision arm (host and orchestrator-api); confirm `resolve_owned_or_adopt` (not `_or_refuse`) so non-owned missions still resolve; confirm `owned.files()` containment on ledger/events/DM paths.
