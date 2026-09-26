---
work_package_id: WP03
title: Surface-authority WRITE gate (S-C)
dependencies: []
requirement_refs:
- FR-006
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-merge-integrity-01M380R6
base_commit: 73b60a95270592c7aefc031fd0f5b9787e49df78
created_at: '2026-09-23T22:18:54.605706+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Parallel fan (file-isolated)
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/write_seam.py
create_intent:
- tests/coordination/test_surface_write_gate.py
execution_mode: code_change
owned_files:
- src/specify_cli/coordination/write_seam.py
- src/mission_runtime/write_target_degrade.py
- src/specify_cli/tasks/issue_matrix.py
- src/specify_cli/cli/commands/agent/issue_verdict.py
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/coordination/surface_resolver.py
- tests/coordination/test_surface_write_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Surface-authority WRITE gate (S-C)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (frontmatter) before parsing the rest of
this prompt, and behave according to its guidance.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Apply the resolved boundaries (no architectural decisions) and TDD discipline. State what you
applied, then continue.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use fenced code-block language identifiers.

---

## Objectives & Success Criteria

Close the wrong-surface write that corrupts the very log the reconciliation gate trusts. Success
(FR-006; traces #4970 #4969):

- A terminus **WRITE** to the coordination surface **fails closed** when the authoritative coord
  worktree/branch is unresolved or unmaterialized — it never degrades to reading/committing over an
  empty/stale primary directory.
- The gate lives at the **real degrade point** — `mission_runtime.write_target_degrade
  .resolve_write_target_or_degrade` — consumed by `write_seam.write_artifact` and the
  `issue-verdict → issue_matrix → write_seam` chain (RN-F1). `surface_resolver.resolve_for_write`
  becomes a thin helper the real write chain calls, not a redundant guard.
- The **READ** path is unchanged — `resolve_for_read`'s loud-primary-fallback is correct for reads
  (D1); only writes get the fail-closed posture.
- `implement._validate_base_ref` consults `origin/<lane>` so a teammate's pushed approved lane is not
  shadowed by a fresh branch cut from local main (#4969).

## Context & Constraints

- Spec: [../spec.md](../spec.md) US3 (both scenarios), FR-006. Research D1; DEBRIEF §3 S-C, §4
  (#4970/#4969). Post-plan disposition RN-F1 ([../research.md](../research.md)) pins the real chain.
- Data model: [../data-model.md](../data-model.md) `SurfaceAuthority` (two entry points, one object).
- **Grounded anchors** (verify in-tree; names are the durable anchors):
  - `resolve_write_target_or_degrade(...)` ≈ `src/mission_runtime/write_target_degrade.py:67` — the
    real degrade helper. It already documents distinct per-caller degrade policies (fail-open vs
    fail-closed); add the fail-closed WRITE pre-gate here.
  - `write_seam.write_artifact(...)` ≈ `coordination/write_seam.py` (the single write locus;
    `issue_matrix.py` calls it ≈ `:372`, importing at ≈ `:356`).
  - `issue_verdict.py` routes through `write_artifact` (see module docstring ≈ `:8`).
  - `implement._validate_base_ref(repo_root, base_ref)` ≈ `cli/commands/implement.py:286`, called
    ≈ `:1427`.
  - `surface_resolver.resolve_for_write` (the thin helper) — home the fail-closed decision once.
- **Layer note**: `mission_runtime` is a deeper layer than `specify_cli`; edits there respect the
  enforced chain `…{mission_runtime} <- specify_cli`. Do not import `specify_cli` from
  `mission_runtime`.
- Locality (C-004, widened): stay within the six owned files + the new test.

## Branch Strategy

- **Strategy**: file-isolated parallel-fan — start immediately.
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T010 – Red: unmaterialized-coord WRITE refuses
- **Purpose**: reproduce #4970 at the real write chain (TDD red).
- **Steps**: create `tests/coordination/test_surface_write_gate.py`. Build a coord mission whose
  coord worktree is NOT materialized (fresh clone / CI checkout shape). Drive a coord-surface write
  through `write_seam.write_artifact` (or the `issue-verdict` command path). Assert the write
  **refuses** with structured guidance and the committed coord surface is **not** overwritten. RED
  on base (today it degrades to the primary dir and commits over the coord branch).
- **Files**: `tests/coordination/test_surface_write_gate.py`.
- **Notes**: also add a fail-open READ case proving `resolve_for_read` still degrades loudly (no
  regression to reads, D1).

### T011 – Fix: fail-closed WRITE gate at `resolve_write_target_or_degrade`
- **Purpose**: home the write fail-closed decision at the real degrade point (RN-F1).
- **Steps**: in `write_target_degrade.py`, add a fail-closed WRITE mode: when resolution yields no
  materialized authoritative coord target and the caller is a terminus WRITE, return a `Refusal`
  (or raise a structured error) rather than the primary/degrade ref. Preserve the existing fail-open
  READ callers' behavior — the mode is explicit per caller, not global.
- **Files**: `src/mission_runtime/write_target_degrade.py`.
- **Notes**: keep the resolution-first ordering the module already documents; the raise/refusal is
  consulted only once, after resolution genuinely fails.

### T012 – Fix: `surface_resolver.resolve_for_write` thin helper
- **Purpose**: one authority object, two entry points (D1) — the write side calls one helper.
- **Steps**: make `resolve_for_write` a thin wrapper that delegates the fail-closed decision to
  `resolve_write_target_or_degrade`'s WRITE mode; it must NOT re-implement resolution (avoids the
  redundant-guard drift RN-F1 warns about). Keep `resolve_for_read` untouched.
- **Files**: `src/specify_cli/coordination/surface_resolver.py`.

### T013 – Fix: wire the write chain
- **Purpose**: route `write_seam.write_artifact` and its consumers through the fail-closed WRITE gate.
- **Steps**: in `write_seam.write_artifact`, resolve the write target via the WRITE-mode helper and
  refuse (structured, non-zero) when unmaterialized. Confirm `tasks/issue_matrix.py` (≈ `:372`) and
  `cli/commands/agent/issue_verdict.py` invoke that single locus (no per-caller open-coded degrade).
- **Files**: `src/specify_cli/coordination/write_seam.py`,
  `src/specify_cli/tasks/issue_matrix.py`, `src/specify_cli/cli/commands/agent/issue_verdict.py`.
- **Notes**: hoist repeated refusal messages/paths to module constants if used `>=3` times (Sonar
  S1192).

### T014 – Fix: `implement._validate_base_ref` consults `origin/<lane>`
- **Purpose**: close #4969 — a fresh lane cut from local main shadows a pushed approved lane.
- **Steps**: in `_validate_base_ref` (≈ `:286`), before cutting/validating the base from local main,
  consult `origin/<lane>` (the pushed approved lane) and prefer it when present. Assert (test) that
  a lane existing only as `origin/<lane>` resolves to the origin ref, not a fresh local cut.
- **Files**: `src/specify_cli/cli/commands/implement.py`.
- **Notes**: coordinate the origin-aware base semantics with WP04 (which owns `workspace/context.py`
  and `lanes/compute.py`); this WP owns only the `implement.py` site.

### T015 – Verify red→green + gates
- **Steps**: confirm the new test RED→GREEN; run
  `PWHEADLESS=1 .venv/bin/python -m pytest tests/coordination/ -q` and the write-seam/issue-matrix
  tests; paste output. `ruff check` + `ruff format --check` + `mypy` clean over all six touched
  files (`mypy src/specify_cli/coordination/write_seam.py src/specify_cli/tasks/issue_matrix.py
  src/specify_cli/cli/commands/agent/issue_verdict.py src/specify_cli/cli/commands/implement.py
  src/specify_cli/coordination/surface_resolver.py` and `mypy src/mission_runtime/write_target_degrade.py`).

## Test Strategy

- `tests/coordination/` is the owning subsystem — run it in full plus the write-seam/issue-matrix
  tests (`grep -rl write_artifact tests/`).
- Compiler gate on every touched typed source.

## Risks & Mitigations

- **Gating the READ path** breaks correct loud-primary-fallback — only writes get fail-closed (D1).
- **Redundant guard** on a helper the real chain never calls (RN-F1) — home the decision at
  `resolve_write_target_or_degrade` and make `resolve_for_write` thin.
- **Cross-layer import**: never import `specify_cli` from `mission_runtime`.

## Definition of Done

- `test_surface_write_gate.py` RED on the mission base, GREEN on the fix; WP01's #4970/#4969 repros
  flip GREEN.
- A terminus WRITE to an unresolved/unmaterialized coord surface fails closed at
  `resolve_write_target_or_degrade`, exercised through the real write chain; the committed coord
  surface is never overwritten.
- The READ path (`resolve_for_read` loud-primary-fallback) is unchanged (regression-guarded).
- `_validate_base_ref` consults `origin/<lane>`; a lane existing only as `origin/<lane>` resolves to
  the origin ref.
- No `mission_runtime → specify_cli` import introduced (layer chain respected).
- `ruff` + `ruff format --check` + `mypy` clean over all six touched sources; no new `# type: ignore`.

## Review Guidance

- Confirm the fail-closed gate is at `resolve_write_target_or_degrade`, exercised by the real write
  chain (not only a helper).
- Confirm reads are unchanged.
- Confirm `_validate_base_ref` consults `origin/<lane>`.
- Confirm no cross-layer import and no per-caller open-coded degrade remains.

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP03 --to <lane>`.
