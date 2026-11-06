---
work_package_id: WP04
title: 'S1 tidy-first, lane-root normalization (carrying #6884) and the typed ref reader'
dependencies: []
requirement_refs:
- FR-002
- FR-004
- FR-043
- NFR-010
- C-015
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
- T021
- T022
- T023
phase: Phase 2 - S1 one status read contract
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/missions/
create_intent:
- tests/specify_cli/missions/test_lane_worktree_status_shadow.py
- tests/status/test_status_read_matrix.py
- tests/coordination/test_status_ref_reader.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/missions/_read_path_resolver.py
- src/specify_cli/coordination/status_service.py
- src/runtime/next/committed_authority.py
- tests/specify_cli/missions/test_lane_worktree_status_shadow.py
- tests/status/test_status_read_matrix.py
- tests/coordination/test_status_ref_reader.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 - S1 tidy-first, lane-root normalization (carrying #6884) and the typed ref reader

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission lane-worktree-model-hardening-01M6QY1M`). Feedback items are your TODO list. Record progress with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP04 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

Work in the workspace the command prints.

## Objectives & Success Criteria

S1 (#7277), first code slice. Two outcomes:

1. **FR-002**: every root-taking status entry point re-anchors a lane root to the repository root and never returns a lane directory or a path that does not exist. This finishes #6884.
2. **FR-004**: the coordination-branch reader returns a typed result: an absent file on a readable ref is an empty history; a missing/unreadable ref or a git failure raises `StatusSurfaceRefUnreadable` (code `STATUS_SURFACE_REF_UNREADABLE`). Today `read_event_log(COORDINATION_BRANCH_REF)` returns `[]` on any `git show` failure (`status_service.py:172-200`).

Acceptance (spec User Story 1, scenarios 2 and 3): a `lanes` Mission whose lane copy says `planned` while the write checkout says `in_progress` reports `in_progress` from inside the lane checkout; a bad ref exits non-zero with the typed error.

## Context & Constraints

- Read: charter; `spec.md` FR-001 to FR-007, Rules and Invariants 1; `research.md` R-1, R-2; `data-model.md` §2 (`RefRead`); `contracts/error-codes.yaml`; the WP01 ADR (`docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`) if already written.
- **#6884 is NOT merged** (branch `origin/issue-6466-lane-status-shadow`, author Ivan Melck `<22272470+Ivan-Melck@users.noreply.github.com>`, labelled taken-by-human, conflicts with `main`). This WP carries it forward as its FIRST commit (T017), then builds on it.
- **Registry-unreadable decision**: #6884 kept the caller's root when the worktree registry is unreadable (fail open; its test `test_an_unreadable_worktree_registry_keeps_the_callers_root`). The plan and Rule 1 tighten that to **fail closed with a typed error** (research R-1, design-decisions trace). Flip that test deliberately in a separate red-first commit and say so in the commit message.
- Shared files (sequenced out-of-map hunks; record each with a one-line rationale in your completion summary):
  - `src/specify_cli/cli/commands/implement_phases.py` (owned by WP06): the alias rename only.
  - `src/mission_runtime/resolution.py` (owned by WP06): stale docstrings at ~2480-2485 and ~2972-2975 only.
  - `src/specify_cli/coordination/surface_resolver.py` (owned by WP05): the one call to the normalization helper inside `resolve_status_surface_with_anchor` (line ~1256).
  - `src/specify_cli/status/aggregate.py` (owned by WP06): the normalization call in `MissionStatus.load` (~line 194).
- Layering: `src/runtime/next/committed_authority.py` already imports `specify_cli`; keep imports function-local where the module does so today. `mission_runtime` must not import `specify_cli` (`tests/architectural/test_layer_rules.py`).
- Charter C-011 / standing order 4: red-first tests committed BEFORE the implementation commit and red on the planning base. Never retry-to-green.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

> Execution worktrees are allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T017 - Carry #6884 forward as the first commit (with attribution)

- **Purpose**: keep the author's work and its 9 tests; avoid a second, divergent implementation.
- **Steps**:
  1. `git fetch origin issue-6466-lane-status-shadow` (shallow clones may need `--deepen`; see tracer friction about missing merge bases).
  2. `git cherry-pick -x -n 942ff4aed9 59bd93d6bd f404a0b240` (red-first test, fix, test-module formatting).
  3. Restore everything that is not ours to carry: `git restore --staged --worktree kitty-specs/lane-worktree-status-shadow-authority-01M68JFG docs/changelog/CHANGELOG.md body6466.md` (other Mission's files, the hand-edited CHANGELOG and a stray PR body; CLAUDE.md forbids editing CHANGELOG.md).
  4. Keep only `src/specify_cli/missions/_read_path_resolver.py` (the `_canonical_status_read_root` helper, ~60 lines) and `tests/specify_cli/missions/test_lane_worktree_status_shadow.py` (9 tests).
  5. Resolve conflicts against the current `_read_path_resolver.py` by hand.
  6. Commit:
     ```
     fix(7277): carry #6884 forward - a lane worktree root is never a status surface

     Carried forward from PR #6884 (issue-6466-lane-status-shadow) because that PR
     conflicts with main. Path-limited: the other Mission's kitty-specs files and the
     CHANGELOG.md hunk are dropped.

     (cherry picked from commit 942ff4aed9...)
     (cherry picked from commit 59bd93d6bd...)
     (cherry picked from commit f404a0b240...)
     Co-authored-by: Ivan Melck <22272470+Ivan-Melck@users.noreply.github.com>
     ```
     Use the full SHAs (`git rev-parse`).
  7. Run the 9 tests: they must pass on this commit.
- **Notes**: if #6884 merges into `main` before you start, rebase the topic branch instead and skip this subtask (record it).

### Subtask T018 - Tidy (behaviour-preserving)

- Rename the alias `resolve_status_surface_with_anchor as _resolve_status_surface` at `cli/commands/implement_phases.py:368` to the real name (it clashes with `agent/status.py:139`'s different `_resolve_status_surface`; see tracer friction).
- Fix stale docstrings: `mission_runtime/resolution.py:2480-2485, 2972-2975`, `coordination/status_service.py:320`.
- Commit as `refactor(7277): tidy ...` with no behaviour change; existing tests green.

### Subtask T019 - Characterization matrix

- New `tests/status/test_status_read_matrix.py`: parametrize topology (`single_branch`, `lanes`, `lanes_with_coord`) x coordination state (materialized, empty, unmaterialized) x owned (yes/no where applicable) x cwd (repository root checkout, lane checkout, coordination worktree). Pin TODAY's resolved directory per cell. Use `tests/integration/coord_topology_fixture.py` for real git fixtures.
- Cells that WP05 will change are marked with a comment `# changes in WP05 (FR-003)`, so WP05 flips them visibly.
- Mark tests `fast` or `unit` only if they truly are; otherwise leave unmarked so `make test-fast` does not grow slow tests.

### Subtask T020 - Red-first acceptance tests

Commit these BEFORE T021/T022; each must be red on the planning base:

- `test_lane_root_reads_write_checkout_state` (`tests/status/test_status_read_matrix.py`): lane copy `planned`, write checkout `in_progress`; three entry points (`resolve_status_surface_with_anchor`, `candidate_feature_dir_for_mission`, `MissionStatus.load`) called with the lane root each return the write checkout.
- `test_repository_root_input_unchanged` (positive control, FR-002): a repository-root input returns unchanged on the same fixture.
- `test_registry_unreadable_fails_closed`: replaces #6884's keep-the-root test (flip it in the same commit, explain why).
- `tests/coordination/test_status_ref_reader.py`: `test_ref_reader_bad_ref_raises_typed_error` (deleted/corrupt ref -> `StatusSurfaceRefUnreadable`), `test_ref_reader_absent_file_reads_empty` (readable ref, no log file -> `[]`), `test_ref_reader_git_failure_raises` (monkeypatched git failure).

### Subtask T021 - One normalization helper, fail closed

- **Steps**:
  1. Lift `_canonical_status_read_root` into one public helper in `_read_path_resolver.py` (e.g. `canonical_status_read_root(repo_root) -> Path`).
  2. Call it from the five root-taking entries: `resolve_status_surface_with_anchor` (`coordination/surface_resolver.py:1256`, out-of-map one-liner), `candidate_feature_dir_for_mission` (`_read_path_resolver.py:1314`), `resolve_surface_dir_or_typed_error` (`:1242`), `MissionStatus.load` (`status/aggregate.py:194`, out-of-map one-liner), `committed_authority.primary_surface_dir` (`src/runtime/next/committed_authority.py:156`).
  3. Registry unreadable -> raise a typed error (reuse an existing typed resolver error if one fits; otherwise add one in `_read_path_resolver.py` and export it). Never return a lane path or a nonexistent path.
  4. Keep complexity <= 15: split classification and re-anchoring into small helpers.

### Subtask T022 - Typed ref reader

- In `coordination/status_service.py`: add `RefRead` (ABSENT | PRESENT(bytes)) and `StatusSurfaceRefUnreadable` (code constant `STATUS_SURFACE_REF_UNREADABLE`).
- `read_event_log` / `read_event_stream_log` for `COORDINATION_BRANCH_REF`: distinguish "path not in tree" (`git cat-file -e <ref>:<path>` fails while `<ref>^{commit}` resolves) from a missing ref / object / git error. A missing coordination ref keeps raising `CoordinationBranchDeleted` where the resolver already detects deletion.
- Use `--end-of-options` or a fully-qualified `refs/heads/...` so a `-`-prefixed name is never an option.
- No empty `except`; map git failures explicitly.

### Subtask T023 - Quality gates and blast radius

See Validation.

## Validation

Targeted tests (run all, record commands and counts):

```bash
cd <workspace>
uv run --frozen pytest tests/specify_cli/missions/test_lane_worktree_status_shadow.py tests/status/test_status_read_matrix.py tests/coordination/test_status_ref_reader.py -q
uv run --frozen pytest tests/specify_cli/missions tests/missions tests/coordination tests/status tests/runtime tests/next -q -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_single_mission_surface_resolver.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_layer_rules.py tests/architectural/test_cold_import_status_boundary.py -q
make test-fast
```

Static gates on touched files:

```bash
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy --strict <touched src files>
```

- Complexity <= 15 per function (ruff C901). No new `# noqa` / `# type: ignore`. Repeated literals (>= 3) become constants.
- NEVER run `make test-full` or a bare `tests/architectural/` sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- Classify unrelated reds per CLAUDE.md "baseline-red gotcha" before touching them.

## Tracer files

Code WPs must not change Mission files from a lane worktree. Return tracer lines in your completion summary, formatted `- **[YYYY-MM-DD][implement WP04] <finding>.** <detail>. Disposition: <...>.`, naming the target file: `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/tooling-friction.md`, `.../traces/approach.md` or `.../traces/design-decisions.md`. The orchestrator appends them. Include the fail-closed decision and the #6884 carry-forward.

## Risks & Mitigations

- Cherry-pick drags other-Mission files: path-limit as in T017; verify `git show --stat HEAD`.
- Fail-closed breaks a caller that relied on fail-open: the matrix test (T019) surfaces it; fix the caller, do not widen the fallback.
- Hidden callers of `read_event_log` that expect `[]` on error: grep `read_event_log(` and check each.

## Review Guidance

- First commit carries attribution trailers and nothing from `kitty-specs/lane-worktree-status-shadow-authority-01M68JFG/`.
- Red-first commits precede implementation commits (`git log --oneline`).
- No lane path or nonexistent path can be returned; typed errors distinguish absent file vs bad ref.
- mypy/ruff/format clean on touched files.

## Definition of Done

- T017-T023 done; all targeted tests green; out-of-map hunks listed with rationale; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T017 ... T023 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP04 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
