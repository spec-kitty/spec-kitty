---
work_package_id: WP02
title: CLI flags, forecast, orchestrator-api
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-005
- FR-009
- FR-010
- FR-012
- NFR-004
planning_base_branch: issue-7692-consolidate-retarget
merge_target_branch: issue-7692-consolidate-retarget
branch_strategy: Planning artifacts for this mission were generated on issue-7692-consolidate-retarget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7692-consolidate-retarget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-retarget-01M7M5JA
base_commit: 772424961d464fb67ce3b8a8214d7cc3fb09f1e6
created_at: '2026-11-17T10:48:37.992031+00:00'
subtasks:
- T007
- T009
- T010
- T011
phase: Phase 3 - Entry points
history:
- at: '2026-11-17T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/consolidation/test_retarget_cli_and_forecast.py
- tests/orchestrator_api/test_consolidate_mission_retarget_refusal.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/consolidation/forecast.py
- src/specify_cli/orchestrator_api/consolidation.py
- src/specify_cli/consolidation/claim_inputs.py
- tests/consolidation/test_retarget_cli_and_forecast.py
- tests/orchestrator_api/test_consolidate_mission_retarget_refusal.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – CLI flags, forecast, orchestrator-api

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Any review feedback is your TODO list.

---

## Objectives & Success Criteria

- `spec-kitty consolidate` accepts `--retarget` and `--retarget-reason "<why>"`. Misuse exits 2 and moves nothing: `--retarget` without `--target`, or `--retarget-reason` without `--retarget` (FR-001, FR-005).
- The flags reach `_run_lane_based_consolidation(retarget=..., retarget_reason=...)`. WP03 adds those keywords.
- `--dry-run --target <b> --retarget` uses `target_override_verdict(retarget=True)` and the re-pointed #5385 probe (`refuse_protected_status_target(retarget_to=<b>)`). It reports the same codes as the real run, and its JSON payload carries `"retarget": {"from": <recorded>, "to": <b>}` (FR-009).
- `--target <recorded> --retarget` is not a retarget: no `retarget` object, and the run proceeds as without the flag (FR-012).
- `orchestrator-api consolidate-mission` gets no flag. It calls `target_override_verdict(retarget=False)` instead of its two hand-chained calls, keeps raising `RuntimeError` for #6464 and `CodedPreflightRefused` for #5783 (so the envelope does not change), and `CONTRACT_VERSION` does not change (FR-010).

## Context & Constraints

- Read `spec.md` (FR-001, FR-005, FR-009, FR-010, FR-012), `plan.md` D8, D9 and D11, and `contracts/cli-retarget.md`.
- WP01 provides `preflight.target_override_verdict`, `retarget_record_refusal` and the codes; WP03 provides the executor keywords and the entry-preflight arm.
- Do not bump `orchestrator_api/envelope.py::CONTRACT_VERSION`, and do not change any envelope field.

## Branch Strategy

- **Planning base branch**: `issue-7692-consolidate-retarget`
- **Merge target branch**: `issue-7692-consolidate-retarget`

`spec-kitty agent action implement WP02 --agent claude --mission consolidate-retarget-01M7M5JA`

## Subtasks & Detailed Guidance

### Subtask T007 – CLI flags, validation and threading

- **Steps**:
  1. In `cli/commands/consolidate.py`, find the options object (`ConsolidateOptions` or similar, around lines 1080–1100) and the typer command (around lines 1190–1220, near `attest_reason` / `dependency_refs`). Add:
     ```python
     retarget: bool = typer.Option(False, "--retarget", help="Adopt --target as the mission's new recorded target for this run, and record it (meta.json target_branch + retarget_history). Requires --target.")
     retarget_reason: str | None = typer.Option(None, "--retarget-reason", help="Reason recorded with --retarget.")
     ```
  2. Validation helper `_validated_retarget_flags(retarget, retarget_reason, target_branch) -> tuple[bool, str | None]`, in the style of the existing `_validated_*` helpers:
     - `--retarget` without `--target` raises `typer.BadParameter` or exits 2 with a clear message. Follow how `_validated_attestation_flags` refuses, and match its exit code (2 for usage).
     - `--retarget-reason` without `--retarget`: exit 2.
     - A blank reason is treated as absent.
  3. Thread the flags into both the real run's call to `_run_lane_based_consolidation(...)` (around line 907) and the dry-run forecast call.
  4. Thread `--resume`: when `--resume` is combined with `--target X --retarget`, pass both. WP03's entry preflight raises `RETARGET_RESUME_MISMATCH`.
  5. `--abort` with `--retarget` is a usage error (exit 2), because abort has no target semantics. Mirror `_validated_release_flags(..., abort=)` (`consolidate.py:~520`), the existing abort-aware validation.
- **Files**: `src/specify_cli/cli/commands/consolidate.py`.
- **Notes**: keep every function at complexity ≤ 15 by extracting helpers.

### Subtask T009 – Forecast: retarget arm and JSON [P]

- **Steps**:
  1. In `consolidation/forecast.py`:
     - `_refuse_protected_target_override_in_forecast` calls `target_override_verdict(..., retarget=retarget)`;
     - `_refuse_protected_status_target_in_forecast` passes `retarget_to=effective` when the forecast is a retarget (effective ≠ recorded and `retarget` is set).
  2. Add the forecast entry parameter `retarget: bool = False`, threaded from the CLI.
  3. When it is a retarget and no refusal fires, add `"retarget": {"from": recorded, "to": effective}` to the JSON payload. Find where the payload dict is assembled and the existing keys (for example `window_gaps`). In human output, print one line: `Retarget: <from> -> <to> (would be recorded first)`.
  4. A refusal uses the same `_emit_dry_run_error(error_msg=..., error_code=...)` path, so `error_code` is the verdict's own code.
  5. **Claim parity (squad):** `consolidation/claim_inputs.py` builds the forecast's claim on the status surface. For a retarget forecast, pass the same `(from, to)` swap to `status_surface_tip`, using the keyword WP03 adds in `status_surface.py`. The forecast then judges the window the real run will. It stays read-only.
  6. **Attestations:** the forecast reports `RETARGET_WITH_ATTESTATION_UNSUPPORTED` exactly when the entry preflight does (WP03 T008 step 6). Reuse WP03's predicate.
- **Files**: `src/specify_cli/consolidation/forecast.py`.

### Subtask T010 – orchestrator-api through the shared verdict [P]

- **Steps**:
  1. In `orchestrator_api/consolidation.py` (around lines 494–535), replace the separate `refuse_protected_target_override` call and the `_refuse_unwritable_recorded_target` helper with one `target_override_verdict(..., retarget=False)` call. Then dispatch on `verdict.error_code`:
     - `PROTECTED_BRANCH_REFUSED`: raise exactly what is raised today (`RuntimeError` with today's message).
     - `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`: raise today's `CodedPreflightRefused`.
  2. The remedy text from WP01 now ends with the CLI `--retarget` sentence. That is the only visible change.
- **Files**: `src/specify_cli/orchestrator_api/consolidation.py`.
- **Notes**: if the dispatch-on-code shape reads worse than the two calls, keep the two calls and only make sure the shared text is used. The reducer asked for one verdict, but not for a worse API (R4). Record the choice in the WP history.

### Subtask T011 – Tests

- **Steps**:
  1. `tests/consolidation/test_retarget_cli_and_forecast.py`:
     - CLI validation with typer's `CliRunner` on the `consolidate` app: `--retarget` alone exits 2; `--retarget-reason x` alone exits 2; `--abort --retarget` exits 2.
     - Threading: monkeypatch `executor._run_lane_based_consolidation` / the forecast entry and assert the keywords received.
     - Forecast unit: monkeypatch the verdicts and assert the JSON has a `retarget` object on success, the verdict's `error_code` on refusal, and no `retarget` object for `--target <recorded> --retarget`.
  2. `tests/orchestrator_api/test_consolidate_mission_retarget_refusal.py`, modelled on `tests/orchestrator_api/test_consolidate_mission_protected_target.py`:
     - a differing target still gives `PREFLIGHT_FAILED` and `data.preflight_error_code == TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`;
     - the message contains `--retarget`;
     - `CONTRACT_VERSION` equals its value on the planning base (read it from `envelope.py` and pin the literal in the test).
  3. Run:
     ```
     .venv/bin/python -m pytest tests/consolidation/test_retarget_cli_and_forecast.py tests/orchestrator_api/ tests/specify_cli/orchestrator_api/ -n 6 --dist loadfile -q
     .venv/bin/python -m pytest tests/agent/cli/commands/test_merge_target_resolution.py tests/specify_cli/cli/commands/test_merge_cli_golden.py tests/consolidation -k "forecast or dry_run" -n 6 --dist loadfile -q
     ```
- **Files**: as listed.

## Test Strategy

Above, plus ruff, ruff format (`--force-exclude`) and mypy on the touched files, and `tests/architectural/test_no_dead_symbols.py` (the WP01 symbols now have callers).

## Risks & Mitigations

- **CLI golden tests** (`test_merge_cli_golden.py`) may pin `--help` output; re-pin intentionally and say so in the history.
- **Envelope drift**: assert the exception types are unchanged.

## Review Guidance

- Misuse exits 2 and moves nothing.
- The forecast and the real run give identical codes.
- The orchestrator-api envelope and `CONTRACT_VERSION` are unchanged.

## Progress & Status

`spec-kitty agent tasks add-history WP02 --note "..."`; `spec-kitty agent tasks mark-status T0xx --status done --mission consolidate-retarget-01M7M5JA`.
