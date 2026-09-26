---
work_package_id: WP02
title: Compare-and-swap ref advance (S-A)
dependencies: []
requirement_refs:
- FR-003
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-merge-integrity-01M380R6
base_commit: b68e56894dad773cb6244c5b423f6a97e9184583
created_at: '2026-09-23T22:00:30.887557+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Parallel fan (file-isolated)
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/ref_advance.py
create_intent:
- tests/git/test_ref_advance_cas.py
execution_mode: code_change
owned_files:
- src/specify_cli/git/ref_advance.py
- tests/git/test_ref_advance_cas.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Compare-and-swap ref advance (S-A)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter before parsing the
rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Apply the resolved initialization, boundaries (no architectural decisions), directives, and tactics
(TDD red-green-refactor). State which you applied, then continue.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks (` ```python `,
` ```bash `).

---

## Objectives & Success Criteria

Bring the forward merge advance to the same compare-and-swap discipline the rollback path already
uses. Success (FR-003; traces #4996 #4982 #4997):

- `advance_branch_ref` performs `git update-ref <ref> <new_sha> <expected_old_sha>` — **3-arg CAS**,
  not the current 2-arg `update-ref <ref> <new_sha>`.
- On a value mismatch at write time, the advance **fails closed** (raises `RefAdvanceError`); it
  never falls back to a 2-arg write and never retries silently.
- The module docstring + `advance_branch_ref` docstring no longer frame safety on the external
  `__global_merge__` lock (that lock is unlinkable by `merge --abort`, #4996).

**Ship with WP06.** Without CAS, the WP06 verifier only detects divergence *after* a non-atomic
clobber already destroyed work (DEBRIEF §3, S-A "Must ship with S-D").

## Context & Constraints

- Spec: [../spec.md](../spec.md) FR-003; US2 scenario 2 (a changed ref value fails closed).
- Contract: [../contracts/terminus-reconciliation.md](../contracts/terminus-reconciliation.md)
  §"CAS advance contract".
- Research: [../research.md](../research.md) D2. DEBRIEF §2 smoking gun — `restore_branch_ref`
  (rollback) is already 3-arg CAS in the SAME file; bring `advance_branch_ref` to parity.
- **Grounded anchors** (verify in-tree; line numbers drift slightly from the debrief's
  `upstream/main` HEAD — the function names are the durable anchors):
  - `def advance_branch_ref(...)` ≈ `ref_advance.py:324`; the 2-arg write is
    `_run_git(repo_root, ["update-ref", ref, new_sha], env=env)` ≈ `:410`.
  - `def restore_branch_ref(...)` ≈ `:426` already calls
    `["update-ref", ref, restored_sha, expected_current_sha]` ≈ `:443` — copy its 3-arg shape.
  - Module docstring framing the global lock ≈ `ref_advance.py:1-24`.
- Locality (C-004): edits confined to `git/ref_advance.py` + its own test. Do NOT touch the executor
  or the lock (WP09 owns lock ownership).

## Branch Strategy

- **Strategy**: file-isolated parallel-fan — start immediately, but land before WP06 begins.
- **Planning base branch**: `fix/terminus-merge-integrity`
- **Merge target branch**: `fix/terminus-merge-integrity`

## Subtasks & Detailed Guidance

### T006 – Red unit: CAS argv + fail-closed on mismatch
- **Purpose**: pin the exact `update-ref` argv and the fail-closed behavior before the fix (TDD red).
- **Steps**: create `tests/git/test_ref_advance_cas.py`. Build a real temp git repo; capture the
  argv passed to `git` (spy on `_run_git` **only to observe argv** — the assertion is on the real
  command shape, not a mock of git itself). Assert:
  1. `advance_branch_ref(repo, ref, new_sha, expected_old_sha)` issues
     `["update-ref", ref, new_sha, expected_old_sha]` (4 tokens after `git`).
  2. When the ref's on-disk value ≠ `expected_old_sha`, the call raises `RefAdvanceError` and the
     ref is **unchanged** (no 2-arg fallback, no retry). Construct the mismatch by advancing the ref
     out-of-band between read and write.
  3. The happy path (value matches) advances the ref and returns as before (NFR-004 parity).
- **Files**: `tests/git/test_ref_advance_cas.py`.
- **Notes**: RED on base (today argv is 3 tokens, no fail-closed).

### T007 – Fix: 2-arg → 3-arg CAS in `advance_branch_ref`
- **Purpose**: make the forward advance atomic (D2).
- **Steps**:
  1. Extend `advance_branch_ref`'s signature to accept `expected_old_sha` (the value read at the
     start of the merge transaction). Thread it from the caller in WP06's wiring — for THIS WP,
     add the parameter with a keyword-only, non-defaulted form so callers must pass it (or a
     narrowly-scoped default that WP06 replaces; document the choice inline).
  2. Replace the 2-arg `_run_git(repo_root, ["update-ref", ref, new_sha], env=env)` ≈ `:410` with
     the 3-arg CAS `["update-ref", ref, new_sha, expected_old_sha]`, mirroring `restore_branch_ref`
     ≈ `:443`.
  3. On a non-zero `update-ref` (value changed since read), raise `RefAdvanceError` naming the ref +
     the expected vs actual value. Never fall back to a 2-arg write; never retry.
- **Files**: `src/specify_cli/git/ref_advance.py`.
- **Notes**: keep the existing worktree-scan/resync error handling; only the write becomes CAS.
  Complexity: keep `advance_branch_ref` `<=15` (extract a helper if the CAS + error branch pushes it
  over — Sonar S3776 / ruff C901).

### T008 – Fix: correct the docstrings (drop lock-dependence)
- **Purpose**: DIRECTIVE_010 — stop the docstring asserting safety rests on the global lock.
- **Steps**: rewrite the module docstring (≈ `:1-24`) and `advance_branch_ref`'s docstring so they
  state the advance is atomic **by CAS** and no longer depend on the `__global_merge__` lock for
  correctness. Note the parity with `restore_branch_ref`. (The CLAUDE.md-level correction is WP10;
  here fix only the in-file docstring.)
- **Files**: `src/specify_cli/git/ref_advance.py`.

### T009 – Verify red→green + gates
- **Steps**:
  1. Confirm `tests/git/test_ref_advance_cas.py` is RED on base, GREEN on the fix.
  2. Run `PWHEADLESS=1 .venv/bin/python -m pytest tests/git/ -q` (own module blast radius) and paste
     terminal output into *Tests run*.
  3. `uv run --frozen ruff check src/specify_cli/git/ref_advance.py tests/git/test_ref_advance_cas.py`
     and `ruff format --check` the touched files; `uv run --frozen mypy src/specify_cli/git/ref_advance.py`
     clean (no new `# type: ignore`).
- **Files**: touched surfaces only.

## Test Strategy

- `tests/git/` is the owning subsystem — run it in full plus the new CAS test.
- Compiler gate: `mypy src/specify_cli/git/ref_advance.py` must pass in addition to pytest.

## Risks & Mitigations

- **Silent 2-arg fallback** on CAS failure reopens #4996 — the T006 assertion forbids it.
- **Retry-on-mismatch** masks the race — forbidden; fail closed once.
- **Caller breakage**: the new `expected_old_sha` parameter is consumed by WP06's wiring; document
  the interim default and flag it for WP06.

## Definition of Done

- `test_ref_advance_cas.py` RED on the mission base, GREEN on the fix.
- `advance_branch_ref` issues 3-arg CAS `update-ref <ref> <new> <old>`, matching `restore_branch_ref`.
- A value mismatch raises `RefAdvanceError` and leaves the ref unchanged — no 2-arg fallback, no
  retry.
- Happy-path advance is unchanged (NFR-004); the docstrings no longer rest safety on the global lock.
- `ruff check` + `ruff format --check` + `mypy src/specify_cli/git/ref_advance.py` clean; no new
  `# type: ignore`; `advance_branch_ref` stays `<=15` complexity.

## Handoff note to WP06

The new `expected_old_sha` parameter is consumed by WP06's gate wiring (it threads the value read at
the start of the merge transaction). Record the interim default (if any) and the exact call sites
WP06 must update, so the serial lane does not discover the signature change late.

## Review Guidance

- Verify the argv is 3-arg CAS and matches `restore_branch_ref`'s shape.
- Verify fail-closed on mismatch leaves the ref unchanged (no fallback, no retry).
- Verify the docstrings no longer rest safety on the global lock.
- Verify the `expected_old_sha` handoff to WP06 is documented.

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP02 --to <lane>`.
