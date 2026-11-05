---
work_package_id: WP04
title: doctor workspaces --prune CLI
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-006
- FR-012
- NFR-004
planning_base_branch: issue-7173-landed-worktree-cleanup
merge_target_branch: issue-7173-landed-worktree-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-7173-landed-worktree-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7173-landed-worktree-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-landed-worktree-cleanup-01M6KZNP
base_commit: d8e21e049a723d89885ed4076422183ee61ba0e9
created_at: '2026-11-05T07:07:26.899645+00:00'
subtasks:
- T014
- T015
- T016
- T017
phase: Phase 2 - Operator surface
history:
- at: '2026-11-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/_landed_worktree_doctor.py
create_intent:
- src/specify_cli/cli/commands/_landed_worktree_doctor.py
- tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/cli/commands/_workspace_husk_doctor.py
- src/specify_cli/cli/commands/_landed_worktree_doctor.py
- tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – `doctor workspaces --prune` CLI

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback; record changes with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Objectives & Success Criteria

- `spec-kitty doctor workspaces` prints, after the unchanged husk report, a "Worktrees" section with every verdict from `assess_worktrees` (WP03).
- `--prune` runs `prune_landed` and prints, per removal, path, branch, SHA, the recreate command and any kept ref (format in `contracts/doctor-workspaces-cli.md`).
- `--fix` keeps its exact husk-only contract (FR-006). `--fix --prune` does both, husks first.
- `--json` keeps every existing husk key and adds `worktrees` (and `pruned` with `--prune`).
- Exit codes per the contract: landed worktrees alone never make exit non-zero; a guard refusal during `--prune` does (exit 1); an unreadable worktree list does (exit 1).

## Context & Constraints

- `doctor.py` holds thin `@app.command` shells only (module docstring); logic lives in `_*_doctor.py` helpers. Put the new rendering in `src/specify_cli/cli/commands/_landed_worktree_doctor.py` and call it from `run_workspaces` in `_workspace_husk_doctor.py` (it currently branches on `fix`).
- Import discipline of `_workspace_husk_doctor.py` (docstring "I-2"): import shared infra from `._doctor_shared`, never from `doctor`. Heavy imports stay function-local.
- `--prune` help text must say: removes only worktrees proven landed into the local `origin/<primary>` (no fetch), never uses --force, prints a recreate command; Mission worktrees are only reported.
- Update the command docstring examples (`spec-kitty doctor workspaces --prune`). The JSON-contract enumeration test (`tests/architectural/test_json_contract_enumeration.py`, entry `"doctor workspaces": ((), 1, "outside")`) must stay green — do not change behaviour outside a repository.
- Keep every function ≤ 15 complexity; repeated literals ≥ 3 → module constants (Sonar S1192).

## Branch Strategy

- **Planning base branch**: `issue-7173-landed-worktree-cleanup`
- **Merge target branch**: `issue-7173-landed-worktree-cleanup`

Run `spec-kitty agent action implement WP04 --agent claude --mission landed-worktree-cleanup-01M6KZNP` and work in the printed workspace.

## Subtasks & Detailed Guidance

### Subtask T014 – `--prune` flag

- Add `prune: Annotated[bool, typer.Option("--prune", help=...)] = False` to `workspaces` in `doctor.py`; pass to `run_workspaces(repo_root, fix, json_output, prune=prune)` (keyword with default so other callers are unaffected).
- Pass `current_dir=Path.cwd()` into the assessment so the worktree the operator stands in is excluded.

### Subtask T015 – Rendering

- Text, per verdict, one line: `<relative path> (<branch or detached @sha12>): <verdict> — <reason detail>`; for `landed` without `--prune` add `remove with: spec-kitty doctor workspaces --prune`.
- Group order: landed, not landed, unproven, Mission-owned, excluded (excluded hidden unless `--json`).
- Summary line: `N landed, M kept`.
- JSON: merge into the existing husk payload: `{"worktrees": [v.to_json() ...], "pruned": [o.to_json() ...]}` (`pruned` only with `--prune`); `worktrees_error` when the list could not be read.
- Paths shown relative to the repo root when inside it, absolute otherwise.

### Subtask T016 – Exit codes and flag combination

- Compute the husk exit code exactly as today, then OR in: worktree list unreadable → 1; any `PruneOutcome.refusal` → 1.
- `--fix` alone must not run the prune. The text report runs for both modes.

### Subtask T017 – CLI tests

- `tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py` with `typer.testing.CliRunner` against a real temp repo (reuse the fixture helpers pattern from WP03's tests by copying the small builder locally — do not import test modules across packages).
- Cases: report lists a landed worktree and exits 0 with no husks; report writes nothing (worktree still present); `--prune` removes it and prints `git branch <b> <sha>`; `--prune --json` payload has `pruned[0].removed == true` and husk keys unchanged; `--fix` alone leaves the landed worktree in place; `--fix --prune` with a husk and a landed worktree removes both; a dirty landed-content worktree is kept and listed with `UNCOMMITTED_CHANGES`; a guard refusal (monkeypatch `guarded_worktree_remove` to raise) → exit 1 and the worktree is listed with the refusal.
- Run unchanged: `tests/specify_cli/cli/commands/test_workspace_husk_doctor.py`, `tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py`, `tests/architectural/test_json_contract_enumeration.py`, `tests/architectural/test_docs_cli_reference_parity.py`.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py tests/specify_cli/cli/commands/test_workspace_husk_doctor.py tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_docs_cli_reference_parity.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/doctor.py src/specify_cli/cli/commands/_workspace_husk_doctor.py src/specify_cli/cli/commands/_landed_worktree_doctor.py tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/cli/commands/doctor.py src/specify_cli/cli/commands/_workspace_husk_doctor.py src/specify_cli/cli/commands/_landed_worktree_doctor.py tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py
uv run --frozen mypy src/specify_cli/cli/commands/_landed_worktree_doctor.py src/specify_cli/cli/commands/_workspace_husk_doctor.py src/specify_cli/cli/commands/doctor.py
```

## Risks & Mitigations

- Changing husk output that other tests snapshot: the husk section is printed first and unchanged.
- `doctor.py` is large: only the `workspaces` shell changes.

## Review Guidance

- `--fix` contract unchanged (run the old husk tests).
- Exit codes match the contract.
- JSON keeps old keys.

## Progress & Status

Record notes with `spec-kitty agent tasks add-history WP04 --note "..."`.
