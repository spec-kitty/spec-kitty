---
work_package_id: WP01
title: Route every charter reported repo-relative path through one POSIX seam
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7044-charter-reported-paths-posix
merge_target_branch: issue-7044-charter-reported-paths-posix
branch_strategy: Planning artifacts for this mission were generated on issue-7044-charter-reported-paths-posix. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7044-charter-reported-paths-posix unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-reported-paths-posix-7044-01M6EJRR
base_commit: 9606359a8b9955f09bf16f7bd3162f4eafed798d
created_at: '2026-11-02T16:58:32.211483+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - POSIX reported paths
history:
- at: '2026-11-02T16:55:51Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_charter_reported_paths_posix.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/kernel/charter_pack_paths.py
- src/specify_cli/cli/commands/charter/_common.py
- src/specify_cli/cli/commands/charter/generate.py
- src/specify_cli/cli/commands/charter/interview.py
- tests/specify_cli/cli/commands/charter/test_charter_reported_paths_posix.py
- tests/specify_cli/cli/commands/charter/test_status_collectors_legacy_md_shape.py
- tests/kernel/test_charter_pack_paths.py
- docs/changelog/unreleased/7044-*.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7044'
---

# Work Package Prompt: WP01 – Route every charter reported repo-relative path through one POSIX seam

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (implementer role) via the resolver-backed profile-load skill and
behave per its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## Objectives & Success Criteria

Fix **#7044**: `spec-kitty charter generate --json` and `spec-kitty charter interview --json`
report a repository-relative path spelled with the host separator (`str(Path.relative_to(...))`),
so Windows emits `.kittify\charter\charter.md` where Linux and macOS emit
`.kittify/charter/charter.md`. The same spelling leaks into the two commands' text output, the
missing/malformed-interview error, and `_display_path()`, which renders the path for the other
charter verbs. Route all of them through the one seam #6277 introduced for `charter synthesize`:
`kernel.charter_pack_paths.repo_relative_posix(path, repo_root)`.

Done when:

- **FR-001**: `charter generate --json` reports `charter_path` as POSIX (`.kittify/charter/charter.md`) on every OS.
- **FR-002**: `charter interview --json` reports `interview_path` as POSIX (`.kittify/charter/interview/answers.yaml`) on every OS.
- **FR-003**: generate, interview and `_display_path()` all render through `repo_relative_posix()`; no site computes its own spelling.
- **FR-004**: the `Charter:` and `Interview file:` text lines and the missing/malformed-interview error message report the POSIX spelling.
- **FR-005**: `_display_path()` keeps its out-of-repo fallback — a path outside the repository still returns a usable string and never raises.
- **NFR-001**: no envelope field name, field set, ordering or exit code changes.
- **NFR-002**: on a POSIX host every reported string is byte-identical to `main`; no existing expectation is edited.
- **NFR-003**: the regression module carries a non-vacuity control proving the Windows-rendering simulation really produces a backslash for a bare `str(relative_to(...))`.
- **C-001**: the separator swap stays inside `kernel.paths.to_posix()`; no hand-rolled `str.replace("\\", "/")`, no local `as_posix()` decision.
- **C-002**: `repo_relative_posix` is defined once, in `src/kernel/charter_pack_paths.py`, and imported.
- **C-003**: `charter synthesize`'s reporting surface and the committed `synthesis-manifest.yaml` are out of scope (that is #6277 / PR #7045).

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (single canonical authority; layer rule "`kernel` imports nothing upward"; ATDD-first).
- Spec / plan / discovery: `../spec.md`, `../plan.md`, `../research.md`.
- Read first, then implement: `src/kernel/paths.py` `to_posix()` (the single separator seam, #2836),
  `src/specify_cli/cli/commands/charter/_common.py` (`_display_path`),
  `src/specify_cli/cli/commands/charter/generate.py`,
  `src/specify_cli/cli/commands/charter/interview.py`.
- Never fake `os.name` to simulate Windows: `tests/kernel/test_is_windows_seam.py` documents that it
  flips `pathlib` to `WindowsPath` mid-run and crashes pytest. Simulate by patching `Path.relative_to`.

## The exact sites (verified on `origin/main` `9aed3a8012`)

| File | Line | Today |
| --- | --- | --- |
| `_common.py` | 108 | `return str(path.relative_to(repo_root))` inside `_display_path()` |
| `generate.py` | 343 | `rel_path = answers_path.relative_to(repo_root)` (fed into the missing/malformed-interview `ValueError`) |
| `generate.py` | 671 | `"charter_path": str(charter_path.relative_to(repo_root))` |
| `generate.py` | 690 | `console.print(f"Charter: {charter_path.relative_to(repo_root)}")` |
| `interview.py` | 523 | `"interview_path": str(answers_path.relative_to(repo_root))` |
| `interview.py` | 543 | `console.print(f"Interview file: {answers_path.relative_to(repo_root)}")` |

---

## Subtasks

### T001 — Write the regression module, red first

Create `tests/specify_cli/cli/commands/charter/test_charter_reported_paths_posix.py`.

Module markers: `pytestmark = [pytest.mark.regression, pytest.mark.git_repo]` (add
`pytest.mark.non_sandbox` only if the fixture needs it — check what
`tests/specify_cli/cli/commands/charter/test_interview_languages.py` uses for the same
`CliRunner` fixture and follow it).

Harness:

```python
def install_windows_path_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``Path.relative_to`` render Windows-style strings for charter state."""
    real_relative_to = Path.relative_to

    def windows_relative_to(self: Path, *args: Any, **kwargs: Any) -> Path:
        result = real_relative_to(self, *args, **kwargs)
        if result.parts and result.parts[0] == ".kittify":
            return PureWindowsPath(*result.parts)  # type: ignore[return-value]
        return result

    monkeypatch.setattr(Path, "relative_to", windows_relative_to)
```

Restricting the re-flavour to `.kittify` results keeps every other caller on real `Path`
objects, so an access path is never built from a `PureWindowsPath` on POSIX.

Fixtures: a tmp git repo (`git init --initial-branch=main`, local `user.email`/`user.name`,
`commit.gpgsign false`), run `charter_interview --defaults --json` via `CliRunner`, then
`charter generate --from-interview --json`. Use `contextlib.chdir` like the sibling modules.

Tests:

1. `test_simulation_renders_backslashes_for_a_bare_str` — control. Under the simulation,
   `str((tmp_path / ".kittify" / "charter" / "charter.md").relative_to(tmp_path))` contains `\`
   and `.as_posix()` is `.kittify/charter/charter.md`. Fail with a message naming the
   vacuity risk if it does not.
2. `test_interview_json_reports_posix_interview_path` — `payload["interview_path"] ==
   ".kittify/charter/interview/answers.yaml"`, no `\`, and `(repo / payload["interview_path"]).exists()`.
3. `test_generate_json_reports_posix_charter_path` — `payload["charter_path"] ==
   ".kittify/charter/charter.md"`, no `\`, resolvable on disk.
4. `test_generate_text_reports_posix_charter_line` — the text run's `stdout` contains
   `Charter: .kittify/charter/charter.md` and no `.kittify\\`.
5. `test_interview_text_reports_posix_interview_line` — same for `Interview file: .kittify/charter/interview/answers.yaml`.
6. `test_generate_missing_interview_names_posix_path` — with `--from-interview` and no
   `answers.yaml`, the invocation exits non-zero and the message contains
   `.kittify/charter/interview/answers.yaml`, with no `\`. Do this both for text and `--json`
   (`payload["error"]`), because the error string is carried by `_emit_error`.
7. `test_display_path_in_repo_is_posix_and_out_of_repo_keeps_fallback` — a single fixture with two
   assertions (the FR-005 positive/negative pair): an in-repo path renders
   `.kittify/charter/charter.md` under the simulation, and a path outside the repo returns
   `str(path)` unchanged without raising.

Record the pre-fix run in the commit message and the PR body: how many tests failed and which.
Expect 6 of 7 red (the control passes by design) — if the control passes but a behavioural test
also passes, the test is vacuous: fix the test, not the expectation.

### T002 — Add the seam

In `src/kernel/charter_pack_paths.py`, add the same function PR #7045 (for #6277) adds, so the two
PRs cannot disagree:

```python
from kernel.paths import to_posix
...
def repo_relative_posix(path: Path, repo_root: Path) -> str:
    """Return *path* as a repo-relative POSIX string. ..."""
    return to_posix(path.relative_to(repo_root))
```

Add `"repo_relative_posix"` to `__all__` (alphabetical, matching the module's existing order) and
carry the same docstring as #7045: *what* is reported is decided here, *how* it is spelled is
`to_posix`'s job, both arguments are `Path` by design, and it raises `ValueError` outside the repo
so the caller keeps its fallback.

### T003 — `_display_path()` renders POSIX in-repo, keeps the fallback

```python
def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return repo_relative_posix(path, repo_root)
    except ValueError:
        return str(path)
```

Keep the out-of-repo branch as `str(path)`: an absolute path outside the repository is not a
repository-relative path, and a Windows operator copying it needs the native spelling. Extend the
docstring with one line saying so (it currently has none).

### T004 — generate.py's three sites

- `:671` → `"charter_path": repo_relative_posix(charter_path, repo_root)`.
- `:690` → `f"Charter: {_display_path(charter_path, repo_root)}"`.
- `:343` → `rel_path = _display_path(answers_path, repo_root)`; keep both error messages' text
  otherwise byte-identical (they are matched by operator workflow docs and the `#2940` honesty
  note).

Import `_display_path` from `._common` (extend the existing
`from specify_cli.cli.commands.charter._common import _emit_error, _interview_path` line) and
`repo_relative_posix` from `kernel.charter_pack_paths` at module top — `kernel` is the floor and
already imported on this path, so no lazy import is needed.

### T005 — interview.py's two sites

- `:523` → `"interview_path": repo_relative_posix(answers_path, repo_root)`.
- `:543` → `f"Interview file: {_display_path(answers_path, repo_root)}"`.

`interview.py` already imports from `._common`; extend that import.

### T006 — Prove the fix half by half, then run the scoped suites

Half-by-half (tactic `acceptance-criteria-non-vacuity`): the fix has two independent parts — the
envelope sites (T004/T005 envelope lines) and `_display_path()` (T003 + the text/error sites).
Revert each part alone in the working tree and confirm a *distinct* subset goes red, then restore.
Record both runs (command + the failing test ids) in the PR body.

Then, all from the repo root with `uv run --frozen`:

```
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_charter_reported_paths_posix.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter -q
uv run --frozen pytest tests/charter -q
uv run --frozen pytest tests/agent/cli/commands/test_charter_cli.py -q
uv run --frozen pytest tests/cli/commands/test_charter_rendering.py tests/cli/commands/test_charter_orchestration.py -q
uv run --frozen pytest tests/kernel/test_is_windows_seam.py -q
.venv/bin/ruff check <changed files> && .venv/bin/ruff format --check --force-exclude <changed files>
.venv/bin/mypy src/kernel/charter_pack_paths.py src/specify_cli/cli/commands/charter/_common.py
```

No full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Any pre-existing red must be reproduced on
a pristine `origin/main` worktree before it is called pre-existing, and reported with its issue.

### T007 — Changelog fragment

`docs/changelog/unreleased/7044-charter-reported-paths.fixed.md`, one `fixed` entry in the shape
`docs/changelog/unreleased/README.md` requires: bold impact-first lead with `(#7044)`, then
**Before:**/**After:** under 1,200 characters. Rename the file to `<pr>.fixed.md` once the PR
number exists. Do **not** touch `docs/changelog/CHANGELOG.md`.

Then:

```
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
```

---

## Branch Strategy

- Planning branch: `issue-7044-charter-reported-paths-posix` (this mission's target branch).
- Final merge target: `main` on `spec-kitty/spec-kitty`.
- Execution worktrees are allocated per computed lane from `lanes.json`; never hand-build a
  workspace path, and never push `main`. This mission has one work package, so one lane.

## Definition of Done

- [x] All seven tests in the new module pass; the control passes both before and after the fix.
      (Delivered: 9 tests — the 7 planned plus the `#2940` malformed-interview message and the
      `charter status --json` consumer that the review round asked for — plus 2 unit tests for
      `repo_relative_posix` in `tests/kernel/test_charter_pack_paths.py`.)
- [x] The pre-fix red run is recorded (which tests failed, how many).
- [x] The half-by-half reverts each produce a distinct red set, recorded.
- [x] Scoped suites above are green, with **one** out-of-map exception: the analysis-report A1
      finding pre-approved replacing `str(Path(".kittify/charter/charter.md"))` with a literal
      POSIX string in `tests/specify_cli/cli/commands/charter/test_status_collectors_legacy_md_shape.py`,
      because that expectation encoded the Windows separator this Mission removes. On a POSIX host
      the value is byte-identical; no assertion was loosened. `tests/kernel/test_charter_pack_paths.py`
      is the same kind of exception (its `__all__` gate had to admit the imported `to_posix` seam).
      Both files are now in `owned_files` below.
- [x] `ruff check`, `ruff format --check`, `mypy` clean on the changed files.
- [x] Changelog fragment present and both docs checks at zero findings.
- [x] No `str.replace("\\", "/")` and no second copy of the helper anywhere in the diff.
- [x] `charter synthesize` files untouched (C-003).

## Risks

- **Duplicate seam with PR #7045.** Keep the function text and location identical so an
  identical-addition hunk merges cleanly; say so in the PR's `## Deferred`.
- **A golden moves.** POSIX output is byte-identical to `main` by construction; a moved expectation
  is a regression to investigate, never an expectation to update.
- **The out-of-repo fallback regresses.** Test 7 asserts both directions on one fixture.
- **A vacuous simulation.** The control test is non-negotiable; drop it and the module proves nothing.

## Reviewer Guidance

- Confirm zero hand-rolled separator logic in the diff (C-001/C-002) and that `kernel` imports only
  `kernel.paths` (layer rule).
- Confirm the `#2940` honesty distinction (present-but-unreadable vs absent) still reaches two
  different messages, only with a POSIX path inside.
- Confirm no envelope field, key order or exit code changed (NFR-001): diff the two envelopes'
  key sets before and after.
- Confirm no existing test expectation was edited.
