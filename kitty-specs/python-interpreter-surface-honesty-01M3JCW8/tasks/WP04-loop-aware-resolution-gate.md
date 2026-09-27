---
work_package_id: WP04
title: Architectural gate for loop-aware resolution
dependencies:
- WP02
- WP03
requirement_refs:
- FR-005
planning_base_branch: claude/project-thread-hjiqjz
merge_target_branch: claude/project-thread-hjiqjz
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-hjiqjz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-hjiqjz unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
phase: Phase 1 - Interpreter-invariant resolution
history:
- at: '2026-09-27T22:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_loop_aware_resolution.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_loop_aware_resolution.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – Architectural gate for loop-aware resolution

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

- **Scope, stated honestly**: this gate blocks *hand-rolled* `RuntimeError`/`ELOOP` translation around path resolution, the pattern `command_installer` used. It does **not** detect the wider resolve-then-contain shape (`try: p.resolve() except OSError` followed by `relative_to`); the post-tasks review counted about 88 such functions. That wider class is recorded as a follow-up in the PR body. Do not describe the gate as closing it.
- `tests/architectural/test_loop_aware_resolution.py` fails on any `try` under `src/` whose body calls `resolve`/`realpath` and whose handlers catch `RuntimeError` (bare or in a tuple) or reference `ELOOP`, unless the file is the primitive module or is on a reasoned, shrink-only allowlist.
- The gate is non-vacuous: it has a floor, a self-mutation test, and a stale-allowlist check.

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

> Execution worktrees are allocated per computed lane from `lanes.json`. Run `spec-kitty implement WP04` (or `spec-kitty agent action implement WP04 --agent claude`) to get the workspace path, and work only there.

## Subtasks & Detailed Guidance

### Subtask T016 – Scanner

- **Steps**: an AST scanner over `src/**/*.py`. For each `ast.Try`:
  - does its body (walk the statements, not nested functions) contain a `Call` whose func is an `Attribute` or `Name` named `resolve` or `realpath`?
  - does any handler's type mention `RuntimeError` (a `Name`, or inside a `Tuple`), or does any handler body reference the name `ELOOP` (`errno.ELOOP` attribute or bare name)?
  - If both, record `(relative_path, lineno)`.
- Also count `resolve_rejecting_loops` call sites and `resolve`/`realpath` call sites across `src/`, for the floor.
- Model the structure and naming on the existing scanner-based gates in `tests/architectural/`, for example `_no_follow_symlinks_apply_scan.py` and its test, rather than inventing a new style.

### Subtask T017 – Allowlist with reasons

- **Steps**: run the scanner on the migrated tree (after WP02 and WP03). The post-tasks prototype expects 10 remaining hits in 7 files:
  - `cli/commands/safe_commit_cmd.py` (about line 446)
  - `cli/commands/spec_commit_cmd.py` (about line 180)
  - `dashboard/handlers/static.py` (about line 23)
  - `git/report_transaction.py` (about line 139). This is a false positive: `ProtectionPolicy.resolve` is not path resolution. Allowlist it with that reason.
  - `invocation/writer.py::normalise_ref`
  - `mission.py::get_active_mission`
  - `upgrade/migrations/m_0_10_8_fix_memory_structure.py`, 4 try-blocks. Key entries by `(path, enclosing function, ordinal within function)` so the 4 are distinct.
- WP04 owns only its test file, so **every** remaining hit is allowlisted, not migrated. Each allowlist entry is `{key: reason}`. Each reason is one line saying why the verdict is identical across interpreters or why `RuntimeError` is caught for a non-loop reason. Key entries by path and function name, not line number, so they survive edits.
- If a hit belongs to a file owned by neither WP02 nor WP03, allowlist it. Do not edit it here (ownership).

### Subtask T018 – Non-vacuity

- **Tests**:
  1. the real tree has zero unallowlisted offenders;
  2. floor: `resolve_rejecting_loops` call sites ≥ the observed count minus 1, and `resolve`/`realpath` call sites ≥ 90% of the observed count (about 516 today; the name match also counts non-path `.resolve` calls, so say so in a comment). Record the observed numbers in a comment;
  3. every allowlist entry still matches an actual hit (a stale entry fails, so the list only shrinks);
  4. self-mutation: write a synthetic module into `tmp_path` with `try: p.resolve()` / `except RuntimeError: ...`, run the scanner on it, and assert one hit. A second synthetic module with an `ELOOP` handler also gives one hit. A third, with `try: os.open(...)` / `except OSError as e: if e.errno == errno.ELOOP`, gives zero hits (the O_NOFOLLOW sense must not match).
- Mark the module `pytestmark = pytest.mark.fast` if its neighbours do, and make sure it is picked up by the architectural lane (check how sibling gates are marked).

## Test Strategy

- `tests/architectural/test_loop_aware_resolution.py` only, on 3.11 and 3.13.
- `ruff`/`mypy` on the test file.

## Risks & Mitigations

- Over-matching: the predicate must require a `resolve`/`realpath` call in the try-body, so O_NOFOLLOW `ELOOP` checks around `open` stay out.
- Floor numbers: set them just below the observed counts and state the observed numbers in a comment.

## Review Guidance

- The self-mutation cases include the O_NOFOLLOW negative.
- The allowlist has one-line reasons and a stale-entry check.
- The floor is concrete, not zero.

## Activity Log

- 2026-09-27T22:30:00Z – system – Prompt created.
