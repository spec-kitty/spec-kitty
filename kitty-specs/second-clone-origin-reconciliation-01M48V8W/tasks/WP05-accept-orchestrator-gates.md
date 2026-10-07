---
work_package_id: WP05
title: accept and orchestrator-api gates
dependencies:
- WP03
requirement_refs:
- FR-003
- FR-004
- FR-008
- FR-009
- FR-010
- SC-004
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T16:44:54.282156+00:00'
subtasks:
- T024
- T025
- T026
- T027
phase: Phase 3 - Gates
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/
create_intent:
- tests/terminus/test_accept_sees_teammate_rejection.py
- tests/orchestrator_api/test_origin_freshness_envelopes.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/orchestrator_api/consolidation.py
- src/specify_cli/orchestrator_api/envelope.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
- tests/contract/test_breaking_check.py
- tests/terminus/test_accept_sees_teammate_rejection.py
- tests/orchestrator_api/test_origin_freshness_envelopes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – accept and orchestrator-api gates

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address every feedback item before handing back.

---

## Objectives & Success Criteria

- `spec-kitty accept` (FR-003) refuses `ORIGIN_STATUS_STALE` / `ORIGIN_UNREACHABLE` when the status evidence is stale / the remote unreachable, with `--origin-check warn` and `SPEC_KITTY_ORIGIN_CHECK=warn` as opt-out (FR-009). `--no-commit` and `--diagnose` (read-only) always warn, never refuse.
- `orchestrator-api accept-mission` refuses with `MISSION_NOT_READY` + `data.preflight_error_code` + `data.origin_freshness` before `materialize`; `consolidate-mission` refuses with `PREFLIGHT_FAILED` + `data.preflight_error_code` / `data.preflight_error_codes` + `data.origin_freshness` before `_execute_lane_merge` (covers the planning-only arm) — evidence AND approved lanes (FR-004). Both accept `--origin-check`.
- `CONTRACT_VERSION` 1.10.0 → 1.11.0 with a comment line in `envelope.py` naming the additive fields.

## Context & Constraints

- Read `spec.md` FR-003/FR-004/FR-009/FR-010, `plan.md` ("Where each gate calls the check"), `contracts/{origin-freshness.md,cli-surface.md}`, `research.md` R-10.
- `origin_freshness` (WP03): `check_status_evidence(repo_root, slug, owned=...)`, `check_branches`, `enforce_merge_gate`, `resolve_origin_check_mode`, `OriginFreshnessRefused`.
- accept CLI: ONE site, in `accept()` (~:1371) between `_verify_merge_commit` (~:1466) and `_collect_summary_or_exit` (~:1467); thread `owned=run.owned` (the post-plan squad confirmed the two `collect_feature_summary` calls at ~:770/~:798 are a repair retry, not separate sites). `--merge-commit` needs no skip.
- orchestrator-api: `accept_mission` (~:612) before `materialize(mission_dir)` (~:627); `consolidate_mission` (~:725) before `_execute_lane_merge` (~:766). Reuse the `ApprovedBoundRefused` envelope shape (#5668) for codes. The approved-lane list for consolidate-mission: `origin_freshness.approved_lane_branches(...)` (WP03) — the same selection the executor uses; never re-derive it.
- Contract docs (`docs/api/orchestrator-api.md`) are WP08's.

## Branch Strategy

- **Strategy**: lanes; worktree allocated by `spec-kitty implement WP05`.
- **Planning base / merge target**: `claude/happy-keller-r38xig`.

## Subtasks

### T024 — Red-first tests (first commit)

- `tests/terminus/test_accept_sees_teammate_rejection.py` (`integration`, `git_repo`): `build_coord_mission` + `two_clone_support`; B pushes a rejection event on the coordination branch; A runs real `spec-kitty accept --mission <m> --json` → refuses with `ORIGIN_STATUS_STALE`; with `--origin-check warn` → not refused for freshness (may still fail readiness — assert on the freshness warning text, not exit 0). `--no-commit` → warning only.
- `tests/orchestrator_api/test_origin_freshness_envelopes.py`: same fixture; invoke the orchestrator CLI (see sibling tests in `tests/orchestrator_api/`, e.g. `test_issue_4934_accept_mission_readiness.py`, for the invocation harness); assert envelope `error_code`, `data.preflight_error_code`, `data.origin_freshness[0].state == "behind"`, `contract_version == "1.11.0"`; unreachable remote → `ORIGIN_UNREACHABLE`; `--origin-check warn` → no freshness refusal.
Prove red, commit.

### T025 — accept

Add `--origin-check` (`click.Choice(["enforce","warn"])`); compute `setting = resolve_origin_check_mode(flag)`. For the read-only modes (`--no-commit`, `--diagnose`) replace it with `OriginCheckSetting(mode=WARN, source="read-only")` (WP03 defines the `read-only` source) — so the verdict is printed but never refuses. Map `OriginFreshnessRefused` to the command's existing error rendering (`AcceptanceError` path or a clean `typer.Exit(1)` with the message) — follow how other refusals in `accept()` are surfaced, including `--json` output.

### T026 — orchestrator-api

- `accept_mission`: `--origin-check` option; before `materialize`, run the evidence check; on refusal `_fail(cmd, "MISSION_NOT_READY", <first line>, {**identity, "preflight_error_code": code, "preflight_error_codes": codes, "origin_freshness": [verdict dicts], "errors": [message]})`. Warnings go into `data["warnings"]` on success if a `warnings` field exists in the schema; otherwise add `data["origin_freshness"]` only. Check `validate_outbound_payload(data, "orchestrator_api")` — if a JSON schema constrains `data`, extend it (find it with grep) additively.
- `consolidate_mission`: same, evidence + lanes, `PREFLIGHT_FAILED`.
- `envelope.py`: `CONTRACT_VERSION = "1.11.0"` + history comment. Re-pin `tests/specify_cli/orchestrator_api/test_contract_version.py` and `tests/contract/test_breaking_check.py` (both pin 1.10.0) following their own supersession convention; sweep `tests/contract/test_orchestrator_api.py` and `tests/agent/test_envelope_unit.py`.

### T027 — Sweep

```bash
.venv/bin/python -m pytest -q tests/terminus/test_accept_sees_teammate_rejection.py tests/orchestrator_api/
.venv/bin/python -m pytest -q $(grep -rl "CONTRACT_VERSION\|contract_version" tests --include=*.py | sort -u | tr '\n' ' ')
.venv/bin/python -m pytest -q tests/acceptance tests/integration/test_coord_single_home_workflow.py
make test-fast
```
Plus ruff/format(`--force-exclude`)/mypy on touched files.

## Definition of Done

- [ ] Tests red first; green after.
- [ ] Contract bump + any schema/contract-version tests updated.
- [ ] Read-only accept modes never refuse on freshness.

## Risks

- Contract-version pin tests across the repo (grep them).
- `accept --json` output shape: add, never rename.

## Reviewer Guidance

Check refusal happens before any write (`materialize` is a read; acceptance stamping must not have run). Check envelope fields are additive.

## Post-tasks squad folds (binding — supersede conflicting text above)

- consolidate-mission uses `check_mission_branches` (one contact per remote). The outbound error-code list is the vendored `src/specify_cli/core/upstream_contract.json` (`orchestrator_api.allowed_error_codes`); `MISSION_NOT_READY` / `PREFLIGHT_FAILED` are already allowed — do NOT edit the vendored contract.
- Tests: an up-to-date control on the same fixture for each refusal arm; an unreachable arm for both commands (FR-008).

## Activity Log

- 2026-10-06 — prompt generated.
