---
work_package_id: WP03
title: Squash projection refusal names what did not land (#5867)
dependencies:
- WP02
requirement_refs:
- FR-009
- FR-014
- NFR-004
planning_base_branch: fix/7598-coord-closeout-leftovers
merge_target_branch: fix/7598-coord-closeout-leftovers
branch_strategy: Planning artifacts for this mission were generated on fix/7598-coord-closeout-leftovers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7598-coord-closeout-leftovers unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-closeout-leftovers-01M78FRR
base_commit: 64b666d3da000381821323dae7f043864881c2a7
created_at: '2026-11-12T21:05:17.830384+00:00'
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 2 - Closeout fixes
history:
- at: '2026-11-12T18:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/phase_gate.py
create_intent:
- tests/consolidation/test_squash_projection_refusal_paths.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/phase_gate.py
- src/specify_cli/consolidation/bookkeeping_projection.py
- src/specify_cli/consolidation/_constants.py
- tests/consolidation/test_executor_coverage.py
- tests/consolidation/test_constants_seam.py
- tests/consolidation/test_squash_projection_refusal_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Squash projection refusal names what did not land (#5867)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before reading further.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address all feedback; record progress with `add-history`.

---

## Objectives & Success Criteria

Operator ruling Decision `01M78G5ZPT2R106TZ26HB4EG5W`: name the paths and reasons, add a new
error code, per-reason remedy; exit code and rollback unchanged.

Today (`research/code-grounding.md` §2, §7):
- `phase_gate.py:355-361` raises `typer.Exit(1)` after printing `SQUASH reconciliation refused: projected coordination bookkeeping content did not land on the target. Nothing was torn down; re-run spec-kitty consolidate --resume.` — no code, no path.
- `bookkeeping_projection.projected_content_matches_target` (`:1539-1574`) collapses per-path verdicts with `all(...)`; `_projected_path_content_matches` (`:1490-1537`) has distinct failures: coordination blob missing; target untouched since checkpoint yet bytes differ; both changed and no driver / driver error / driver output mismatch; and `GitProbeError` → `False` (transient).
- The `Exit(1)` sits **inside** the executor's single rollback door (`executor.py:696-702`), so the target IS rolled back; the comment at `phase_gate.py:347-355` says otherwise (FR-014 fold).

Done when (FR-009, FR-014, NFR-004):
- Output carries `Error code: SQUASH_PROJECTION_NOT_LANDED.` (new constant in `_constants.py`), keeps the phrase "projected coordination bookkeeping content did not land", lists up to 20 `path — reason` lines plus "and N more", and gives a remedy per reason.
- Exit code 1 and the rollback-door behaviour are unchanged.
- A transient probe failure says a re-run may succeed; deterministic causes say what to change.

## Context & Constraints

- C-002: exit code and severity unchanged; only text, a code and a structured return.
- Keep `projected_content_matches_target` as a thin `not unlanded_projected_paths(...)` wrapper; its callers include `tests/terminus/test_repro_5038.py` and `tests/consolidation/test_bookkeeping_projection_seam.py`.
- `tests/consolidation/test_executor_coverage.py:585-597` patches `projected_content_matches_target` — if the gate now calls the new function, update that patch so the test still targets the gate (otherwise real git runs on fake SHAs).
- A new code needs a pin in `tests/consolidation/test_constants_seam.py`; the `docs/api/cli-commands.md` row is WP07's.
- Complexity ≤ 15 per function; hoist repeated reason strings to constants (Sonar S1192).
- WP02 touched `_record_reconciliation_pass` in `phase_gate.py` and docstrings in `bookkeeping_projection.py` before you (dependency): rebase onto them, do not undo them.

## Branch Strategy

Planning base / merge target: `fix/7598-coord-closeout-leftovers`.

```bash
spec-kitty agent action implement WP03 --agent claude --mission coord-closeout-leftovers-01M78FRR
```

## Subtasks & Detailed Guidance

### Subtask T009 – Red: the refusal names paths and the code

- **Steps**:
  1. `tests/consolidation/test_squash_projection_refusal_paths.py`:
     - Unit level: build a tiny real git repo with a checkpoint commit, a coordination branch whose `kitty-specs/<slug>/issue-matrix.json` (a coordination kind) differs from the target's copy while the target never touched it since the checkpoint; call `unlanded_projected_paths(...)` → expect `[(path, ProjectedPathReason.CONTENT_DIFFERS)]`. One cell per reason: coordination blob missing; content differs; no merge driver / driver mismatch (use a `.gitattributes` driver like the existing seam tests do); probe error (monkeypatch the probe to raise `GitProbeError`).
     - Gate level: call `_assert_squash_projected_content_landed` (phase_gate) with a stub run whose projected paths fail, capture the rich console (see how `test_executor_coverage.py` captures output), assert the code line, the phrase, the path and the remedy; assert `typer.Exit` with exit_code 1.
  2. Red on the base (`ImportError` / missing text). Commit `test(consolidation): squash projection refusal names its paths (#5867, red)`.

### Subtask T010 – `unlanded_projected_paths` with reasons

- **Steps**:
  1. In `bookkeeping_projection.py`, add `class ProjectedPathReason(StrEnum)` (`COORDINATION_BLOB_MISSING`, `CONTENT_DIFFERS`, `NO_MERGE_DRIVER`, `MERGE_DRIVER_MISMATCH`, `PROBE_FAILED`) and `unlanded_projected_paths(...) -> list[tuple[str, ProjectedPathReason]]` with the same parameters as `projected_content_matches_target`.
  2. Refactor `_projected_path_content_matches` to return `ProjectedPathReason | None` (None = landed). Keep the logic byte-for-byte equivalent; only the return shape changes.
  3. `projected_content_matches_target` = `not unlanded_projected_paths(...)`.
  4. Check `tests/architectural/dead_symbol_allowlist.yaml` entries for `bookkeeping_projection` still hold.

### Subtask T011 – Gate renders code, paths, per-reason remedy

- **Steps**:
  1. `_constants.py`: `SQUASH_PROJECTION_NOT_LANDED = "SQUASH_PROJECTION_NOT_LANDED"` beside the other codes.
  2. `phase_gate.py::_assert_squash_projected_content_landed`: call `unlanded_projected_paths`; on a non-empty result render (helper `_render_unlanded_projection(paths, coord_branch, target_branch) -> str`):
     ```
     SQUASH reconciliation refused: projected coordination bookkeeping content did not land on the target.
       kitty-specs/<slug>/issue-matrix.json — the target's copy differs from <coordination branch>
       ... (at most 20, then "and N more")
     The landing was rolled back; nothing was torn down.
     Remedy: <per reason, deduplicated>
     Error code: SQUASH_PROJECTION_NOT_LANDED.
     ```
     Remedies: CONTENT_DIFFERS / MERGE_DRIVER_MISMATCH → "make the target's copy match the coordination branch, or revert the coordination change, then re-run `spec-kitty consolidate`"; NO_MERGE_DRIVER → "the path's merge driver is not configured in this clone; run `spec-kitty upgrade` (it installs the merge drivers), then re-run"; COORDINATION_BLOB_MISSING → "the coordination branch deleted or renamed it; restore it on the coordination branch, then re-run"; PROBE_FAILED → "a git probe failed; re-running `spec-kitty consolidate --resume` may succeed". Verify the driver remedy against how merge drivers are installed in this repo (grep `merge-driver` in `src/specify_cli/upgrade/migrations/`) and name the real command.
  3. Exit code stays 1.

### Subtask T012 – Stale comment; existing tests follow the new call

- **Steps**:
  1. Rewrite the `phase_gate.py:347-355` comment: the `Exit(1)` lands in the executor's single rollback door, which restores the target; the record re-baselines after a full restore.
  2. Update `tests/consolidation/test_executor_coverage.py:585-597` to patch the function the gate now calls.
  3. Add the constant pin to `tests/consolidation/test_constants_seam.py`.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/consolidation/test_squash_projection_refusal_paths.py tests/consolidation/test_executor_coverage.py tests/consolidation/test_constants_seam.py tests/consolidation/test_bookkeeping_projection_seam.py tests/terminus/test_repro_5038.py
.venv/bin/python -m pytest -q --dist loadfile -n 8 tests/consolidation
.venv/bin/python -m pytest -q tests/architectural/test_merge_reconciliation_class_guard.py tests/architectural/test_no_dead_symbols.py tests/consolidation/test_single_rollback_authority.py
ruff / format --force-exclude / mypy on changed files
```

## Risks & Mitigations

- Behaviour drift in the per-path proof: T010 is a return-shape refactor only; existing seam tests must pass unchanged.

## Review Guidance

- Red→green; exit code unchanged; phrase kept; cap at 20; no remedy tells the operator to merely resume for a deterministic cause.

## Progress & Status

Event log only.
