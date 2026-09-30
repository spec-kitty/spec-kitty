---
work_package_id: WP02
title: Protected-target preflight
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-003
- C-004
planning_base_branch: claude/5385-single-rollback-authority-qqt180
merge_target_branch: claude/5385-single-rollback-authority-qqt180
branch_strategy: Planning artifacts for this mission were generated on claude/5385-single-rollback-authority-qqt180. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/5385-single-rollback-authority-qqt180 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-rollback-authority-01M3RCP4
base_commit: e0235952dc5794a1f0a4129183d8d117ba430752
created_at: '2026-09-30T07:31:38.926770+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Preflight
agent: claude
history:
- at: '2026-09-30T06:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/preflight.py
create_intent:
- tests/terminus/test_repro_5385_protected_target.py
- tests/specify_cli/coordination/test_transaction_preflight_refusal.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/preflight.py
- src/specify_cli/consolidation/forecast.py
- src/specify_cli/coordination/transaction.py
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/cli/commands/consolidate.py
- tests/terminus/test_repro_5385_protected_target.py
- tests/terminus/lanes_fixture.py
- tests/consolidation/test_preflight_seam.py
- tests/specify_cli/coordination/test_transaction_preflight_refusal.py
role: implementer
---

# WP02 — Protected-target preflight

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`/ad-hoc-profile-load python-pedro`), then read `.kittify/charter/charter.md` and `spec-kitty charter context --action implement`.

## Objective

A consolidation whose done bookkeeping the workflow mutation policy would refuse on the mission's status write target is refused BEFORE any branch moves, with the policy's own `error_code`, message and `next_step`. The live trigger is #5385: a LANES mission (or a SINGLE_BRANCH mission with no mission branch) targeting a protected branch squashes onto `main` and then `BookkeepingPolicyRefused` (`PROTECTED_BRANCH_REFUSED`) is raised from `coordination/transaction.py:520` inside `_phase_record_done_and_project`. After WP01 that crash is rolled back; this WP stops it from happening at all.

**Constraint C-001: one protection authority.** Do not write a new "is this LANES and protected" rule. Reuse the transaction's own pre-flight policy gate (`WorkflowMutationPolicy.assert_allowed` in `coordination/policy.py:143-284`, fed exactly as `_acquire_locked` feeds it) and the transactional status door's own arm selection. Research R-2 in `kitty-specs/single-rollback-authority-01M3RCP4/research.md` explains why a standalone rule over-refuses.

## Branch Strategy

Planning base and final merge target: `claude/5385-single-rollback-authority-qqt180`. Run `spec-kitty agent action implement WP02 --agent claude` and work in the returned lane workspace. WP01 must be approved first (both touch `consolidation/executor.py`).

## Subtasks

### T007 — Red-first real-CLI repro (FIRST)

`tests/terminus/test_repro_5385_protected_target.py`, markers `[integration, git_repo, regression]`.
- `build_lanes_mission(tmp_path, wps=("WP01","WP02"), target_branch="main", mid8=...)`; snapshot all branch tips (`tests.terminus.test_repro_5318.ref_shas`); `run_terminus(mission, ["consolidate", "--mission", slug, "--yes"])`.
- Assert: exit code 1; output contains `PROTECTED_BRANCH_REFUSED` and the policy's remedy text; NO traceback (`"Traceback"` not in stderr); every branch tip unchanged; no reflog entry added on `main` or the mission branch during the run; no merge record `state.json` under `.kittify/runtime/merge/` (NFR-001).
- `--dry-run` case: `run_terminus(mission, ["consolidate", "--dry-run", "--mission", slug, "--json"])` reports `PROTECTED_BRANCH_REFUSED` as its error code.
- Controls on the SAME fixture shape (so a do-nothing preflight cannot pass): `target_branch="develop"` consolidates successfully; `target_branch="main"` with env `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1` is NOT refused by the preflight (assert the refusal code is absent; the run may succeed); a protection config `.kittify/config.yaml` with `protection: {protected_branches: []}` is not refused.
- `--target` cannot launder the refusal: a LANES mission whose RECORDED target is `main`, run with `--target develop` (create `develop` first), is still refused (the status write target is the recorded meta target; the CLI always passes `resolved_target_branch` as `target_override`, `consolidate.py:684-691`, so a preflight reading `lanes_manifest.target_branch` would wrongly pass).
- Real-CLI controls that must NOT be refused on protected `main`: a SINGLE_BRANCH mission with `commit_to_target: true` (see `tests/integration/test_issue_5100_single_branch_topology.py` for how to build one) and a coordination-topology mission (`tests.terminus.conftest.build_coord_mission`).
- Any `.kittify/config.yaml` a control writes must be committed first, or the dirty-tree preflight refuses before yours.
- An all-done resume is not refused: build the mission, mark both WPs `done` in the status log (append `done` events; see `tests/terminus/conftest.py::_approve_events` for the event shape), and assert the preflight does not print the refusal code.
- Run on the WP01 head before implementing and record the RED output in your report.

### T008 — Extract the transaction's pre-flight gate (`coordination/transaction.py`)

1. Extract step 4 of `_acquire_locked` (lines ~490-522: build `GitChangeSet(destination_ref, repo_root=primary_root or repo_root, worktree_root, paths=(events_path, snapshot_path), ...)`, compute `coord_available = mission_has_coordination_branch(repo_root, slug)`, call `WorkflowMutationPolicy.assert_allowed`) into one private function (e.g. `_preflight_policy_verdict(...) -> PolicyVerdict`). `_acquire_locked` calls it and raises `BookkeepingPolicyRefused` on `Refused` exactly as today (behaviour byte-identical; existing transaction tests must stay green: `rg -l "BookkeepingTransaction" tests/specify_cli/coordination` and run them).
2. Add `BookkeepingTransaction.preflight_refusal(*, repo_root, mission_slug, mid8, destination_ref, operation, capability=GuardCapability.STANDARD) -> Refused | None` (classmethod, no lock, no worktree creation, no writes):
   - validate segments like `_acquire_locked`; accept `effective_root: Path | None = None` and classify the arm on `effective_root or repo_root`, exactly as `acquire` hands `_acquire_locked` its `repo_root`;
   - arm selection with the SAME classifiers: if `_is_legacy_mission(...)` is False (coordination arm): the caller-ref verdict, then (when recoverable, by the exact predicate `_acquire_locked` uses; extract it so both share it) the step-4 gate against the redirected coordination branch, as `_acquire_locked` does (transaction.py:490-522); return whichever `Refused` the real acquire would raise, else `None`;
   - if legacy and `_warrants_legacy_warning(...)` is True (genuinely legacy; destination is the operator's lane HEAD, not knowable pre-run) return `None`;
   - modern coordination-less arm: `worktree_root = repo_root`; compute the same events/snapshot paths; return the `Refused` from `_preflight_policy_verdict`, else `None`.
3. Unit tests in `tests/specify_cli/coordination/test_transaction_preflight_refusal.py` over real temp repos: coordination-less mission on protected `main` -> `Refused` with `PROTECTED_BRANCH_REFUSED`; unprotected target -> `None`; hatch env -> `None`; coordination mission -> `None`; and an equivalence test that `acquire` raises `BookkeepingPolicyRefused` with the same `error_code` whenever `preflight_refusal` returns one (same fixture).

### T009 — `status_write_refusal` in the status door (`coordination/status_transition.py`)

Add a public `status_write_refusal(request: TransitionRequest, *, capability: GuardCapability = GuardCapability.STANDARD, operation: str | None = None) -> Refused | None` next to `emit_status_transition_transactional`:
- `identity, topology_available = _resolve_transaction_entry(request, mission_slug)` (the same entry the real door uses);
- `if not topology_available: return None` (the non-transactional fallback never consults the policy);
- otherwise `BookkeepingTransaction.preflight_refusal(repo_root=identity.primary_root or identity.repo_root, mission_slug=..., mid8=identity.mid8, destination_ref=identity.destination_ref, operation=..., capability=capability)`.
Default `operation` to `f"status transition {request.wp_id}"` (the real door's default, status_transition.py ~1555) and pass `effective_root` through for owned requests exactly as `_acquire_status_transaction` does. Keep it pure (no writes; `_identity_for_request` / `_resolve_transaction_entry` only read meta and git). Tests next to the existing status_transition tests (find them with `rg -l "emit_status_transition_transactional" tests`) or in the T008 file.

### T010 — Consolidation preflight + executor call

In `src/specify_cli/consolidation/preflight.py` add `refuse_protected_status_target(main_repo, mission_slug, lanes_manifest, *, excluded_canceled_wp_ids) -> Refused | None` (name to taste):
- Build the request the done write builds (`done_bookkeeping._mark_wp_merged_done`): `feature_dir = placement_seam(main_repo, slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)`, `mission_slug=slug`, `wp_id=<first pending WP>`, `to_lane="done"`, `repo_root=main_repo`.
- Pending write set: the lane WPs minus canceled-with-provenance, whose current lane (reduced status snapshot on the status surface, `specify_cli.status.read_events` + `reduce`, same reader `_assert_mission_terminal_ready` uses) is not `done`. Empty -> return `None` (an all-done resume writes nothing; post-spec squad H3).
- Return `status_write_refusal(request)`.
- The status target is the mission's recorded target (meta), never `--target` (`_resolve_write_target`); do not pass the manifest target.

In `executor._run_lane_based_consolidation` (out-of-map, note it in your report): that function measures complexity 14 today, so add exactly ONE call to a helper (e.g. `_refuse_protected_status_target_or_continue(main_repo, mission_slug, lanes_manifest)`) that owns every branch, placed in the pre-lock block right before `_pre_mutation_safety_preflight_with_recovery` (after the mission-branch check). The helper, on a `Refused`, prints `[red]Error:[/red] {error_code}: {message}`, the `next_step`, and "Consolidation refused before any branch moved.", then `raise typer.Exit(1)`. Pre-lock placement means no merge record is written.

### T011 — `--dry-run` parity (`consolidation/forecast.py`)

In `run_dry_run_forecast`, after the lanes manifest resolves, call the same preflight; on `Refused` call `_emit_dry_run_error(error_msg=..., json_output=json_output, error_code=verdict.error_code)` and `raise typer.Exit(1)`. Extend `tests/consolidation/test_forecast_seam.py` or the T007 file.

### T012 — Readable policy refusal at the command layer (`cli/commands/consolidate.py`)

In `_run_real_merge` (~683-713) add `except BookkeepingPolicyRefused as exc:` that prints `Error: Bookkeeping policy refused consolidation: {exc.verdict.error_code}: {exc.verdict.message}` and the `next_step`, then `raise typer.Exit(1) from exc` (pattern: `cli/commands/agent/workflow.py:512-518`). WP01's door has already rolled back by the time it reaches here. Test with an in-process `CliRunner` invocation that patches the executor to raise it.

### Out-of-map line in the `--abort` fixture

WP01 T013 rebuilt `tests/terminus/test_repro_5318_abort.py`'s crash wrapper around `os._exit(137)`. Add one line to that wrapper that makes your preflight helper return `None` so the #5385 shape still reaches the post-squash crash; note the out-of-map edit. Update `tests/terminus/lanes_fixture.py`'s module docstring ("Protected target (#5385)" trap) to the new up-front refusal.

### Residuals to name in your report (not fixed here)

A `BookkeepingPolicyRefused` can still escape unrendered from `_record_operator_attestations` (inside the lock, before the snapshot, with `--attest-*` on a protected LANES mission), from the post-gate phases, and via `orchestrator_api/commands.py:874` (catches only `typer.Exit`).

## Validation (targeted only)

- ruff, ruff format --check, mypy on changed src files; complexity <= 15.
- Run: T007 file, T008 file, `tests/terminus/test_repro_5318_abort.py` (out-of-map line), `tests/terminus/test_repro_5296.py`, `tests/terminus/test_lanes_fixture_smoke.py`, the transaction/status_transition/policy test files you touched or that import them (`rg -l "BookkeepingTransaction|status_transition" tests/specify_cli/coordination`), `tests/consolidation/test_preflight_seam.py`, `tests/consolidation/test_forecast_seam.py`, `tests/integration/test_issue_5100_single_branch_topology.py` (single_branch protected landing must NOT be refused), and `make test-fast`.
- Planted-break proof: make `refuse_protected_status_target` return `None` unconditionally -> T007 goes red; make `preflight_refusal` ignore the hatch -> the hatch control goes red. Record both, then revert.

## Definition of Done

- T007 red on the WP01 head, green now; controls green.
- No new protection rule outside the policy; the transaction gate has one implementation used by both `acquire` and `preflight_refusal`.
- Commits per subtask, `(#5385)` in messages, session trailers.

## Reviewer guidance

Verify the equivalence test (acquire vs preflight) exists and uses the same fixture; verify the all-done resume, hatch, coordination and single_branch landing controls; verify no merge record is written on refusal.
