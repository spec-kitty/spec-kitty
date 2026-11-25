---
work_package_id: WP04
title: accept CLI flags for the per-run waiver
dependencies:
- WP02
- WP03
requirement_refs:
- FR-009
- FR-011
- FR-013
- SC-004
- NFR-003
planning_base_branch: issue-7566-path-conventions-per-type
merge_target_branch: issue-7566-path-conventions-per-type
branch_strategy: Planning artifacts for this mission were generated on issue-7566-path-conventions-per-type. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7566-path-conventions-per-type unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-path-conventions-per-type-01M7VRQM
base_commit: b8415e6f0a3fdfd33825744dba2402cef1c65b8f
created_at: '2026-11-20T11:06:18.408817+00:00'
subtasks:
- T015
- T016
- T017
- T018
- T019
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T07:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/accept.py
create_intent:
- tests/specify_cli/cli/commands/test_accept_waive_path_conventions.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/cli/commands/agent/mission_accept_merge.py
- src/specify_cli/acceptance/__init__.py
- tests/specify_cli/cli/commands/test_accept_lenient_help.py
- tests/specify_cli/cli/commands/test_accept_waive_path_conventions.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – accept CLI flags for the per-run waiver

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address all feedback before completion.

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

## Objectives & Success Criteria

- `spec-kitty accept --waive-path-conventions --waive-reason "<why>"` makes path misses non-blocking for that run, while strict metadata validation still blocks (FR-009, SC-004).
- The reason is recorded on the acceptance history entry (`path_conventions_waived: {"reason": ...}`) through WP03's `record_acceptance` parameter.
- A flag without a non-blank reason, or a reason without the flag, is refused (exit 2) before any write (FR-011).
- `spec-kitty agent mission accept` forwards both flags.
- The `--lenient` help still mentions path conventions (the existing pin) and points at the narrow flag.
- orchestrator-api offers no per-run waiver but honours a well-formed `meta.json` waiver like the CLI (operator ruling Q4, FR-013); controls prove both.

## Context & Constraints

- Spec FR-009, FR-011, FR-013, C-006. Contract: `contracts/accept-waiver-contract.md`.
- WP02 adds `evaluate_path_conventions(..., path_conventions_waiver_reason=...)`. WP03 adds `record_acceptance(..., path_conventions_waiver_reason=...)`.
- Plumbing today: `accept()` → `_plan_run(... lenient=...)` → `_AcceptRun.lenient` → `_collect_summary_or_exit` → `_collect_summary_with_optional_repair` → `collect_feature_summary(strict_metadata=...)` → `_collect_...` → `evaluate_path_conventions`. Recording: `perform_acceptance(..., lenient=run.lenient)` → `_record_and_commit_acceptance` → `_stamp_acceptance_record` → `record_acceptance`. Follow the `lenient` thread exactly; add a parallel `path_conventions_waiver_reason: str | None` thread.
- The refusal pattern to mirror: `_validated_no_implementation_request` (`--attest-no-implementation` needs `--attest-reason`). Use flag-name constants (S1192).
- `orchestrator_api` is **not** changed; it never passes the new keyword.
- C901 ≤ 15 in `accept()`. If adding options pushes it over, extract a validator helper.

## Branch Strategy

- **Planning base branch**: `issue-7566-path-conventions-per-type`
- **Merge target branch**: `issue-7566-path-conventions-per-type`
- Implement with `spec-kitty agent action implement WP04 --agent claude --mission path-conventions-per-type-01M7VRQM`.

## Subtasks & Detailed Guidance

### Subtask T015 – Red-first CLI tests

New `tests/specify_cli/cli/commands/test_accept_waive_path_conventions.py`:
1. Help: `accept --help` lists `--waive-path-conventions` and `--waive-reason`, and the help mentions metadata stays strict.
2. Refusals (CliRunner on a standalone Typer app, as in `test_accept_lenient_help.py`): the flag without a reason → exit 2 and a message naming `--waive-reason`; a blank reason → exit 2; a reason without the flag → exit 2. Patch the downstream collector to assert it was **not** called.
3. Threading: patch `collect_feature_summary` (at the accept module's import site) and `perform_acceptance`; invoke with the flag and reason; assert `collect_feature_summary` received `path_conventions_waiver_reason="why"` **and** `strict_metadata=True`, and `perform_acceptance` received `path_conventions_waiver_reason="why"` and `lenient=False`.
4. Agent wrapper: `spec-kitty agent mission accept --waive-path-conventions --waive-reason why` forwards both to the top-level accept (patch `mission.top_level_accept`, the documented seam).
5. End-to-end at summary level (no CLI): a real mission fixture (reuse helpers from `tests/specify_cli/acceptance/` such as those in `test_accept_contracts_waiver.py`) with `src/` missing **and** a WP missing required metadata → `collect_feature_summary(..., strict_metadata=True, path_conventions_waiver_reason="why")` has no path violation **but** still reports the metadata issue. This is the SC-004 discriminator.
6. orchestrator controls (operator ruling Q4): `collect_feature_summary(..., strict_metadata=True)` with no waiver → a path violation is present; with a well-formed `meta.json` waiver and no per-run reason → no path violation, metadata still strict. No orchestrator source change is needed: it reaches the same evaluator.

Confirm red.

### Subtask T016 – Options and refusal

- In `accept()` add:
  - `--waive-path-conventions` (bool, default False) with help: "Treat missing path-convention directories as warnings for this run only; metadata validation stays strict. Requires --waive-reason; recorded in the acceptance history."
  - `--waive-reason` (str | None) with help: "Why path conventions are waived (required with --waive-path-conventions)."
- A helper `_validated_path_conventions_waiver(json_output, waive, reason) -> str | None` refuses misuse with `typer.Exit(2)`, printing via the same JSON/console path `_validated_no_implementation_request` uses, before any write.
- Add `path_conventions_waiver_reason: str | None = None` to `_AcceptRun` and `_plan_run`.

### Subtask T017 – Threading

- `_collect_summary_or_exit` → `_collect_summary_with_optional_repair(..., path_conventions_waiver_reason=...)` → `collect_feature_summary(..., path_conventions_waiver_reason=...)` → the internal collector → `evaluate_path_conventions(..., path_conventions_waiver_reason=...)`. Both calls in the repair helper (initial and re-collect) pass it.
- `perform_acceptance(..., path_conventions_waiver_reason=...)` → `_record_and_commit_acceptance` → `_stamp_acceptance_record` → `record_acceptance(..., path_conventions_waiver_reason=...)`. Check every `perform_acceptance` / `_record_and_commit_acceptance` caller and the `acceptance/__init__.py` line ~2317 path; default `None` keeps them unchanged.

### Subtask T018 – Agent wrapper, help, positive control

- `agent/mission_accept_merge.py::accept_feature`: add both options and forward them to the top-level accept call. Add an example to the docstring.
- `--lenient` help: keep "path-convention" (the pin); append "use --waive-path-conventions to waive only the path check".
- The orchestrator positive control from T015.6 lives in the new test file (no orchestrator source change).

### Subtask T019 – Verify

```bash
uv run --frozen pytest -q tests/specify_cli/cli/commands/test_accept_waive_path_conventions.py tests/specify_cli/cli/commands/test_accept_lenient_help.py tests/specify_cli/acceptance/ tests/specify_cli/test_canonical_acceptance.py tests/specify_cli/test_acceptance_regressions.py tests/specify_cli/test_validate_mission_paths_single_caller.py tests/architectural/test_lifted_root_validate_mission_paths_single_caller.py
uv run --frozen ruff check <touched>; uv run --frozen ruff format --check --force-exclude <touched>; uv run --frozen mypy src/specify_cli/cli/commands/accept.py src/specify_cli/acceptance/__init__.py src/specify_cli/cli/commands/agent/mission_accept_merge.py
```

## Test Strategy

CLI refusal and threading tests plus one summary-level discriminator that proves metadata stays strict.

## Risks & Mitigations

- Many call sites of `perform_acceptance`: default the new keyword to `None`.
- The `accept()` complexity grows: extract helpers.

## Review Guidance

- The waiver never changes `strict_metadata`.
- No change under `src/specify_cli/orchestrator_api/`.

## Progress & Status

`spec-kitty agent tasks mark-status T015 T016 T017 T018 T019 --status done --mission path-conventions-per-type-01M7VRQM`.
