---
work_package_id: WP02
title: Containment seams and the two witnessed 3.13 reds
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
planning_base_branch: claude/project-thread-hjiqjz
merge_target_branch: claude/project-thread-hjiqjz
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-hjiqjz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-hjiqjz unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 1 - Interpreter-invariant resolution
history:
- at: '2026-09-27T22:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/specify_cli/core/test_containment_symlink_loops.py
- tests/specify_cli/skills/test_command_installer_symlink_loops.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/core/utils.py
- src/specify_cli/skills/command_installer.py
- src/specify_cli/dashboard/handlers/features.py
- tests/specify_cli/core/test_containment_symlink_loops.py
- tests/specify_cli/skills/test_command_installer_symlink_loops.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Containment seams and the two witnessed 3.13 reds

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

- `ensure_within_directory` and `ensure_within_any` (`src/specify_cli/core/utils.py`) refuse a symlink loop on every interpreter by raising their documented `ValueError`.
- `command_installer._resolve_observed_input` and `_ensure_project_confined` use the kernel primitive. The hand-rolled 3.11 `RuntimeError`→`OSError` translation is deleted.
- The two witnessed 3.13 reds go green on 3.13/3.14 and stay green on 3.11/3.12:
  - `tests/dashboard/test_artifact_containment.py::TestArtifactPathIsContained::test_unresolvable_path_is_not_contained`
  - `tests/specify_cli/tool_surface/providers/test_command_skills.py::test_wp04_dispatch_config_observation_boundary`

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

> Execution worktrees are allocated per computed lane from `lanes.json`. Run `spec-kitty implement WP02` (or `spec-kitty agent action implement WP02 --agent claude`) to get the workspace path, and work only there.

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first seam tests

- **Steps**: create `tests/specify_cli/core/test_containment_symlink_loops.py` (`pytestmark = pytest.mark.fast`). For **each** of `ensure_within_directory` and `ensure_within_any`:
  - a two-link loop under the root ⇒ `pytest.raises(ValueError)`;
  - a loop in an intermediate component ⇒ `ValueError`;
  - same-fixture positive controls: an ordinary file under the root is returned resolved; a not-yet-existing path under the root is accepted (non-strict semantics preserved); an escaping regular symlink is still `ValueError`.
- Run on 3.11 and 3.13 before the fix and record the reds: 3.11 leaks `RuntimeError`, 3.13 accepts.

### Subtask T006 – Route the seams through the primitive

- **Steps**: in `ensure_within_directory` and `ensure_within_any`, resolve the candidate path with `kernel.resolution.resolve_rejecting_loops`.
  - Translate a loop error into the seam's `ValueError`: `raise ValueError(f"Refusing to access unresolvable path (symlink loop): {path}") from exc`. Hoist the message prefix to a module constant if it would repeat.
  - Keep root resolution unchanged. Keep `ensure_within_any`'s intentional non-strict acceptance of missing paths.
  - Update both docstrings to state the loop refusal.

### Subtask T007 – Caller audit

- **Steps**: for each `ensure_within_directory` / `ensure_within_any` call site listed in `plan.md` (Design, "Each `ensure_within_*` caller is audited"), plus `core/utils.py::write_text_within_directory` (about line 166), confirm what happens on a loop now. Against 3.11/3.12 the `ValueError` is a narrowing (callers got a leaked `RuntimeError`). Against 3.13+ it is new behaviour: those callers accept a loop today, so the audit must say, per caller, that refusing is correct.
  - Append the audit as a short table in the Activity Log: caller, catches `ValueError`?, operator-visible result, and whether the caller's own message misleads for a loop. For example, `status/store.py:205` logs "escapes the specs root" and `migration/backfill_runtime_state.py:1597/1606` says "resolves outside kitty-specs". Misleading messages are recorded, not rewritten, since those files are not owned here. The seam's own `ValueError` text names the loop.
  - No caller code changes unless one would turn a loop into a silent success. If you find one, stop and note it; it belongs in review, not in a drive-by fix.

### Subtask T008 – command_installer sites

- **Steps**: create `tests/specify_cli/skills/test_command_installer_symlink_loops.py`:
  - `_ensure_project_confined` with a loop target ⇒ `InstallerError` with code `unsafe_path`; positive control: a normal in-project path passes.
  - `_resolve_observed_input` on a loop ⇒ `OSError` with ELOOP; positive control: a regular file resolves.
- Then replace the body of `_resolve_observed_input` with a call to `resolve_rejecting_loops`, keeping the function (callers use it) and deleting the hand-rolled `RuntimeError` branch and the now-unused `errno` import if nothing else uses it. In `_ensure_project_confined`, use the primitive inside the existing `try/except OSError`.
- In `dashboard/handlers/features.py::_artifact_path_is_contained`, the seam now raises only `ValueError` for a loop. Drop `RuntimeError` from the except tuple, keeping `OSError`, which a root resolution failure can still raise. Update the docstring to say loops arrive as `ValueError` from the seam.
- Confirm `test_wp04_dispatch_config_observation_boundary` (all 6 params) and `test_wp04_dispatch_does_not_hide_programmer_runtime_error` pass on 3.11 and 3.13.

### Subtask T009 – Witnessed reds and interpreter parity

- **Steps**: run on 3.11, 3.12, 3.13 and 3.14 and record the counts:
  - `tests/dashboard/test_artifact_containment.py`
  - `tests/specify_cli/tool_surface/providers/test_command_skills.py`
  - the two new test files
  - `tests/specify_cli/core/test_ensure_within_any.py`
  - `tests/architectural/test_untrusted_path_containment.py`

## Test Strategy

- New files: `tests/specify_cli/core/test_containment_symlink_loops.py`, `tests/specify_cli/skills/test_command_installer_symlink_loops.py`.
- Existing: `tests/dashboard/test_artifact_containment.py`, `tests/specify_cli/tool_surface/providers/test_command_skills.py`, `tests/specify_cli/core/test_ensure_within_any.py`, `tests/specify_cli/skills/` (the directory's fast tier), `tests/architectural/test_untrusted_path_containment.py`.
- `mypy --strict` on both touched source files.

## Risks & Mitigations

- `ensure_within_any` deliberately accepts missing paths. Do not switch to strict resolution.
- `_resolve_observed_input` has callers that rely on `OSError(ELOOP)` specifically; keep that type.

## Review Guidance

- The seam tests pair each refusal with a same-fixture acceptance.
- The dashboard red and the command-skills `[loop]` red were witnessed red before the fix and are green after, on 3.13 and 3.14.
- The caller audit is present and says no caller turns a loop into silent success.
- The hand-rolled ELOOP translation is gone.

## Activity Log

- 2026-09-27T22:30:00Z – system – Prompt created.
