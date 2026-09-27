---
work_package_id: WP03
title: Remaining loop-sensitive guards
dependencies:
- WP01
requirement_refs:
- FR-004
planning_base_branch: claude/project-thread-hjiqjz
merge_target_branch: claude/project-thread-hjiqjz
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-hjiqjz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-hjiqjz unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Interpreter-invariant resolution
history:
- at: '2026-09-27T22:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- tests/specify_cli/coordination/test_atomic_write_symlink_loops.py
- tests/specify_cli/decisions/test_ownership_symlink_loops.py
- tests/charter/test_symlink_loop_guards.py
- tests/specify_cli/upgrade/test_skill_update_symlink_loops.py
- tests/specify_cli/test_analysis_report_symlink_loops.py
- tests/tracker/test_saas_client_symlink_loops.py
- tests/tracker/test_saas_client.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/atomic_write.py
- src/specify_cli/decisions/ownership.py
- src/charter/offering/drg/org_pack_config.py
- src/charter/activation/synthesizer/path_guard.py
- src/specify_cli/upgrade/skill_update.py
- src/specify_cli/analysis_report.py
- src/specify_cli/tracker/saas_client.py
- tests/specify_cli/coordination/test_atomic_write_symlink_loops.py
- tests/specify_cli/decisions/test_ownership_symlink_loops.py
- tests/charter/test_symlink_loop_guards.py
- tests/specify_cli/upgrade/test_skill_update_symlink_loops.py
- tests/specify_cli/test_analysis_report_symlink_loops.py
- tests/tracker/test_saas_client_symlink_loops.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Remaining loop-sensitive guards

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

- Every guard in spec FR-004 reaches the "After" verdict in plan.md's refusal-contract table on 3.11, 3.12, 3.13 and 3.14, via `kernel.resolution.resolve_rejecting_loops`.
- Each site has a real-loop test that was red on at least one interpreter before its change. The Activity Log records which interpreter was red and how.

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

> Execution worktrees are allocated per computed lane from `lanes.json`. Run `spec-kitty implement WP03` (or `spec-kitty agent action implement WP03 --agent claude`) to get the workspace path, and work only there.

## Subtasks & Detailed Guidance

For every subtask: write the loop test first, witness it red (typically `RuntimeError` on 3.11/3.12, or acceptance on 3.13/3.14), then replace the site's `.resolve(...)` of the **candidate** path with `resolve_rejecting_loops(...)`. Where the site's `except` does not already produce the target verdict, add the translation shown. Each test pairs the refusal with a same-fixture positive control. Leave root resolution as is unless the root itself could be the loop.

### Subtask T010 – coordination/atomic_write confinement

- **Sites**: `_confine_path_to_worktree` (about line 61) and `_resolve_confined_artifact_path` (about line 234; check how it resolves).
- **Target**: a loop ⇒ `ValueError` (the existing `except OSError` already converts to `ValueError`).
- **Test** (`tests/specify_cli/coordination/test_atomic_write_symlink_loops.py`): confining a final-component self-loop and an intermediate-component loop ⇒ `ValueError`. Also test through `_write_confined_artifact_bytes`: writing to a path that is a loop symlink raises and **leaves the symlink in place** (`os.path.islink` still true). The scout confirmed 3.13 replaces it with a regular file. Positive control: a normal relative path under the worktree is written.

### Subtask T011 – decisions/ownership

- **Sites**: `_mission_dirs` (about line 446) and `_read_ledger` (about line 511). Keep the load-bearing comments.
- **Also**: `specs_root = (root / _SPECS_DIRNAME).resolve()` (about line 309) sits outside any try. When `kitty-specs` itself is a loop, 3.11 crashes with `RuntimeError` and 3.13 returns an `"unlistable"` scan. Route it through the primitive and make the verdict the same on every interpreter: the `unlistable` scan 3.13 gives today, with `kitty-specs` named. Test it.
- **Target**: `_mission_dirs` treats a loop mission dir as absent. Check that `errno.ELOOP` is in `_ABSENT_ERRNOS`; the scout says 3.13 already behaves as intended. If ELOOP is not in `_ABSENT_ERRNOS`, work out how 3.13 reaches "absent" and keep that verdict. `_read_ledger` returns `unreadable=True` for a loop ledger.
- **Test** (`tests/specify_cli/decisions/test_ownership_symlink_loops.py`): 3.11/3.12 crash with `RuntimeError` today, and 3.13 already gives the intended answer. The red-first witness therefore **must be a 3.11 run**, recorded in the Activity Log. Use the module's public entry point that calls `_mission_dirs` if one is practical, otherwise the private helper with a comment. Pair with a normal mission dir that is listed.

### Subtask T012 – charter org_pack_config and path_guard

- **Sites**: `charter/offering/drg/org_pack_config.py::resolve_relative_path_within_root` and `charter/activation/synthesizer/path_guard.py::PathGuard._assert_allowed`.
- **Target**: a loop ⇒ `OrgPackSubdirEscapeError` or `PathGuardViolation` respectively. Wrap the primitive call and translate `OSError` loop errors with `from exc`. Keep the non-strict acceptance of a missing subdir in `org_pack_config`.
- **Test**: `tests/charter/test_symlink_loop_guards.py`, with positive controls (a valid subdir; an allowed target).

### Subtask T013 – upgrade/skill_update.is_external_symlink

- **Target**: a loop ⇒ `False` on every interpreter (its `except OSError: return False` as authored; 3.11 crashes today).
- **Test**: `tests/specify_cli/upgrade/test_skill_update_symlink_loops.py`. Positive control: a symlink pointing outside the project ⇒ `True`.

### Subtask T014 – analysis_report._relativize_or_raise

- **Target**: a loop ⇒ `PathRelativizationError` with a **loop-specific** sanitized message (e.g. "cannot resolve artifact 'x' (symlink loop) under root basename 'y'"). "does not lie under that root" is wrong for a loop. Raise it `from None`, as the existing `ValueError` branch does, because the primitive's `OSError` carries the absolute path and `from exc` would leak it in the traceback. Assert `__cause__ is None` and `__suppress_context__` in the test.
- **Test**: `tests/specify_cli/test_analysis_report_symlink_loops.py`. Assert the error type, and that neither `str(tmp_path)` nor the absolute artifact path appears in the message. Positive control: an in-root artifact returns the relative string.

### Subtask T015 – tracker/saas_client project root

- **Target**: a loop project root ⇒ `SaaSTrackerClientError` with `error_code == "project_root_resolution_failed"` on every interpreter.
- **Steps**: use the primitive, and narrow the except tuple to `OSError` so a real programmer `RuntimeError` is no longer masked. Rewrite the existing mocked test in `tests/tracker/test_saas_client.py` (about line 923, which monkeypatches `Path.resolve` to raise a context-free `RuntimeError("symlink loop")`) to build a **real** loop instead, so it tests the real behaviour. That file is owned by this WP.
- **Test**: `tests/tracker/test_saas_client_symlink_loops.py`, with a real loop (not a mock). Positive control: a normal directory constructs a client. Construct the client the way the existing tests do (see `tests/tracker/test_saas_client.py`) so no network is touched.

## Test Strategy

- The six new test files, on all four interpreters (record counts).
- Existing neighbours: `tests/specify_cli/coordination/` fast tier, `tests/specify_cli/decisions/test_ownership_3111.py`, `tests/specify_cli/upgrade/test_skill_update_external_symlinks.py`, `tests/tracker/test_saas_client.py`, and the charter tests that import `org_pack_config` / `path_guard` (find them with `grep -rl`).
- `mypy --strict` on every touched source file.

## Risks & Mitigations

- `atomic_write.py` and `ownership.py` are heavily commented, load-bearing modules. Keep edits to the resolution line and its except-clause only.
- `org_pack_config` sits in `charter`. Importing `kernel` is allowed there; importing `specify_cli` is not.

## Review Guidance

- Every site has a red-first witness in the Activity Log and a paired positive control.
- The `atomic_write` test proves a loop symlink is not replaced.
- No absolute path leaks in the `analysis_report` message.

## Activity Log

- 2026-09-27T22:30:00Z – system – Prompt created.
