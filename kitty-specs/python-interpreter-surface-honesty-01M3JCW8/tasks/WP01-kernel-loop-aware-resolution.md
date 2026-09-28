---
work_package_id: WP01
title: Kernel loop-aware resolution primitive
dependencies: []
requirement_refs:
- FR-001
- NFR-001
- NFR-002
- C-004
planning_base_branch: claude/project-thread-hjiqjz
merge_target_branch: claude/project-thread-hjiqjz
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-hjiqjz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-hjiqjz unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Interpreter-invariant resolution
history:
- at: '2026-09-27T22:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/
create_intent:
- src/kernel/resolution.py
- tests/kernel/test_resolution.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/kernel/resolution.py
- tests/kernel/test_resolution.py
- src/kernel/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Kernel loop-aware resolution primitive

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission python-interpreter-surface-honesty-01M3JCW8`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

- Add `src/kernel/resolution.py` exposing `resolve_rejecting_loops(path: Path) -> Path` and `is_symlink_loop_error(exc: BaseException) -> bool`.
- Contract: behaves exactly like non-strict `path.resolve()`, except that a symlink loop anywhere in the path raises `OSError(errno.ELOOP, os.strerror(errno.ELOOP), str(path))` on **every** interpreter (3.11–3.14).
- Success: `tests/kernel/test_resolution.py` passes on `.venv` (3.11), `.venv312`, `.venv313` and `.venv314`, and its loop cases fail against a naive `return path.resolve()` implementation on every interpreter (prove this red-first).

## Context & Constraints

- Spec: `kitty-specs/python-interpreter-surface-honesty-01M3JCW8/spec.md`; plan (Design section and the refusal-contract table): `plan.md`; evidence: `research.md`.
- Charter: `.kittify/charter/charter.md`. Red-first (DIRECTIVE_034, ADR 2026-07-17-1): write the loop test first, run it, and see it red on at least one of the local interpreters before the fix. It is fine for it to be red on 3.13/3.14 only.
- Local interpreters: `.venv/bin/python` (3.11), `.venv312/bin/python`, `.venv313/bin/python`, `.venv314/bin/python`. All were synced with `uv sync --frozen --all-extras`. In a lane worktree, run them with `PYTHONPATH=src` from the worktree root (e.g. `PYTHONPATH=src /home/claude/spec-kitty/.venv313/bin/python -m pytest ...`). Before trusting a result, check the import path: `-c "import specify_cli;print(specify_cli.__file__)"` must print the worktree's `src`.
- Symlink tests: build real loops in `tmp_path` (`a.symlink_to(b); b.symlink_to(a)` or a self-loop `a.symlink_to("a")`). Skip with `pytest.mark.skipif` only where `os.symlink` is unavailable, following how the existing symlink tests in the touched module's test folder skip.
- A red-first repro may start as `@pytest.mark.regression` pinned to `#3189`, but must be converted to a plain focused unit test (marker removed, `fast` or `unit` marker as the neighbouring tests use) before the WP moves to review.
- No full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`): run the touched modules' test files and the named gates only.
- Quality: `ruff check`, `ruff format --check` and `mypy --strict` on touched files, all clean. No new `# noqa` / `# type: ignore`. Complexity ≤ 15.
- Commit through `spec-kitty safe-commit` or plain git inside the lane worktree, in small commits. Messages are conventional (`fix(...)`, `test(...)`), end with the `(#3189)` reference, and carry the trailer lines:
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01Su57nHB7srQQKTvD9Ltt1y`.

## Branch Strategy

- **Strategy**: lane-based (finalize-tasks fills in the exact values)
- **Planning base branch**: claude/project-thread-hjiqjz
- **Merge target branch**: claude/project-thread-hjiqjz

> Execution worktrees are allocated per computed lane from `lanes.json`. Run `spec-kitty implement WP01` (or `spec-kitty agent action implement WP01 --agent claude`) to get the workspace path, and work only there.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first tests for the primitive

- **Purpose**: pin the contract before writing code.
- **Steps**: create `tests/kernel/test_resolution.py` (module-level `pytestmark = pytest.mark.fast`, like its neighbours in `tests/kernel/`). Cases:
  1. two-link loop `a -> b -> a` ⇒ `OSError` with `errno == ELOOP` (and `is_symlink_loop_error(exc)` true);
  2. self-loop `a -> a` ⇒ same;
  3. loop in an **intermediate** component (`loop/child`) ⇒ same;
  4. positive controls on the same `tmp_path` fixture: a regular file, a directory, a relative path with `..` segments, a valid symlink chain ⇒ equal to `path.resolve()`;
  5. a missing path, and a dangling (non-looping) symlink ⇒ equal to non-strict `path.resolve()` (no raise);
  6. a `RuntimeError` that is **not** a loop (monkeypatch `Path.resolve` to raise `RuntimeError("programmer defect")` with no OSError context) ⇒ propagates unchanged;
  7. `is_symlink_loop_error`: true for `OSError(errno.ELOOP, ...)`; true for an `OSError` whose `winerror` attribute is 1921 (set the attribute on an instance); false for `FileNotFoundError` and for a plain `ValueError`.
- First write a stub `resolve_rejecting_loops = lambda p: p.resolve()`. Run on 3.11 and 3.13 and record in the Activity Log that the loop cases are red on both: `RuntimeError` on 3.11, no raise on 3.13.

### Subtask T002 – Implement the primitive

- **Steps**: in `src/kernel/resolution.py` (stdlib imports only: `errno`, `os`, `pathlib`):
  - `_WINERROR_CANT_RESOLVE_FILENAME = 1921` as a named constant.
  - `is_symlink_loop_error(exc)`: `isinstance(exc, OSError) and (exc.errno == errno.ELOOP or getattr(exc, "winerror", None) == _WINERROR_CANT_RESOLVE_FILENAME)`.
  - `resolve_rejecting_loops(path)`:
    1. `try: resolved = path.resolve()`; `except RuntimeError as exc:` look at `exc.__context__` then `exc.__cause__`. If either is a loop error, `raise _loop_error(path) from exc`; otherwise re-raise unchanged (the 3.11/3.12 branch).
    2. Probe `os.stat(resolved)`. On `OSError` that is a loop error, `raise _loop_error(path) from probe_exc`. Swallow any other `OSError` (missing, dangling, permission), because non-strict semantics must hold (the 3.13+ branch). This mirrors the probe CPython 3.11 `pathlib.Path.resolve` performs internally.
    3. Return `resolved`.
  - `_loop_error(path) -> OSError`: `OSError(errno.ELOOP, os.strerror(errno.ELOOP), str(path))`.
  - Module docstring: explain the 3.13 change (see `research.md` R-1), why the probe exists, the cost argument (one `stat`, the same one 3.11 `pathlib` already performed, NFR-002), and the Windows `winerror 1921` case. Keep it short.
  - Add `__all__`.

### Subtask T003 – Kernel README entry

- **Steps**: add one bullet for `kernel.resolution` to the "Currently it contains" list in `src/kernel/README.md`.

### Subtask T004 – Interpreter parity run

- **Steps**: run `tests/kernel/test_resolution.py` under all four venvs and record the four pass counts in the Activity Log. Also run `tests/architectural/test_layer_rules.py` once, the kernel leaf rule.

## Test Strategy

- `tests/kernel/test_resolution.py` on 3.11, 3.12, 3.13 and 3.14 (all four must pass).
- `tests/architectural/test_layer_rules.py` (kernel must stay a leaf).
- `ruff check`, `ruff format --check`, `mypy --strict src/kernel/resolution.py`.

## Risks & Mitigations

- The `__context__` of 3.11's `RuntimeError` is the `OSError` from `realpath` or from the post-`stat`; check both `__context__` and `__cause__`.
- Do not use `resolve(strict=True)`: it changes semantics for non-loop failures.

## Review Guidance

- Loop cases are genuinely red against the naive stub on both 3.11 and 3.13 (Activity Log evidence).
- The same-fixture positive controls exist.
- A programmer `RuntimeError` is not masked.
- Stdlib-only imports.

## Activity Log

- 2026-09-27T22:30:00Z – system – Prompt created.
