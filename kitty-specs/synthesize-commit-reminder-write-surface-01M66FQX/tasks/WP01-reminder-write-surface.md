---
work_package_id: WP01
title: Derive the synthesize commit reminder from the write surface
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-005
- SC-001
- SC-002
planning_base_branch: issue-6631-synthesize-reminder-write-surface
merge_target_branch: issue-6631-synthesize-reminder-write-surface
branch_strategy: Planning artifacts for this mission were generated on issue-6631-synthesize-reminder-write-surface. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6631-synthesize-reminder-write-surface unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-synthesize-commit-reminder-write-surface-01M66FQX
base_commit: a36128ba7d9bbae8f4a3d65f84cd98d9ed8fed29
created_at: '2026-10-30T13:32:13.926159+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Implementation
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/reach_only.py
- src/charter/activation/api.py
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/cli/commands/charter/resynthesize.py
- tests/charter/synthesizer/test_synthesize_activation_append.py
- tests/charter/synthesizer/test_reach_only_delivery.py
- tests/charter/synthesizer/test_styleguide_reach_only.py
- tests/agent/cli/commands/test_charter_synthesize_cli.py
- tests/acceptance/test_persistent_deactivation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Derive the synthesize commit reminder from the write surface

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history <WPID> --note "..."`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

`charter synthesize` prints a `spec-kitty safe-commit` recipe. Today its path
list (`_SYNTHESIS_ARTIFACT_PATHS` in `src/specify_cli/cli/commands/charter/_synthesis.py`)
names three paths but omits `.kittify/charter/synthesized-artifacts.yaml`
(`CREATED_ARTIFACTS_PATH` in `src/charter/activation/synthesizer/reach_only.py`)
and the activation write target, both written by the same run through
`append_synthesized_activations`. An operator running the printed command
verbatim leaves the record uncommitted (#6631).

Done when:

1. `append_synthesized_activations` returns a structured result: the existing
   warnings (byte-identical content) plus the repo-relative POSIX paths the
   call wrote — the record path when `_record()` actually wrote (content
   changed), the activation target when `_promote` fired.
2. `_print_synthesis_commit_reminder` renders the base paths plus exactly
   those extra paths (deduplicated, stable order); `_emit_real_run_report`
   threads them from the synthesize command; `resynthesize` consumes only the
   warnings.
3. The end-to-end regression test (T001) is green: run the real synthesize on
   the canonical fixture, extract the printed safe-commit line, execute it in
   the test repo, assert `git status --porcelain .kittify/` is empty.
4. No behavior change to what synthesis writes; `--json` envelopes unchanged;
   the fresh-project seed reminder unchanged.

## Context & Constraints

- Spec: `kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/spec.md` (FR-001..FR-003, NFR-001..003, C-001..C-003, C-005).
- Plan: `kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/plan.md` (IC-01, IC-02, IC-03).
- Research (grounding, call sites, fixture inventory): `kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/research.md`.
- Write-surface facts:
  - `_record()` in `reach_only.py` writes the record only when `updated != recorded`.
  - `_promote(repo_root, additions, write_target)` writes `write_target[0]` (a `Path`); the write target resolves via `resolve_activation_write_target` (ledger: `.kittify/charter/activation.yaml`; legacy: pointed-at `charter.yaml` or `.kittify/config.yaml`). Report it repo-relative via `Path.relative_to(repo_root).as_posix()`.
  - `restamp_bundle_hash` rewrites the synthesis manifest (already in the base list) — no extra reporting needed.
- Callers of `append_synthesized_activations`: `synthesize.py` (~line 556), `resynthesize.py` (~line 216), re-export in `src/charter/activation/api.py`.
- The append runs under the synthesis lock; collect the written-paths list inside the same locked body.
- Constraint C-001: absent activation keys stay absent; do not touch write behavior.
- Constraint C-003: `--json` output shapes unchanged; the reminder stays human-branch-only.
- NFR-003: the reminder must never hard-code the record or activation-target paths — they reach it only through the reported written paths.

## Branch Strategy

- **Strategy**: single lane on the mission topic branch
- **Planning base branch**: `issue-6631-synthesize-reminder-write-surface`
- **Merge target branch**: `issue-6631-synthesize-reminder-write-surface`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first e2e regression test

- **Purpose**: Pin the invariant generically — every path the run wrote is named by the printed command — before any fix, so the test is provably red on current behavior.
- **Steps**:
  1. Add a test to `tests/charter/synthesizer/test_synthesize_activation_append.py` (it already owns the canonical fixture: `_seed_project`, `_request`, `_invoke`, `_TACTIC`, `_EXISTING`; `pytestmark` includes `pytest.mark.integration` and `pytest.mark.git_repo`).
  2. Initialize a real git repo in `tmp_path` on a NON-protected initial branch (e.g. `kitty/mission-test-01TEST663`), with `user.email`/`user.name`/`commit.gpgsign false` configured and one initial commit — follow `_init_lane_repo` in `tests/specify_cli/cli/commands/test_safe_commit_cli.py`.
  3. `_seed_project(tmp_path, activated_tactics=[_EXISTING])`, then invoke `charter synthesize --adapter fixture` (NOT `--json`) via the `_invoke` patch convention.
  4. From the human output, extract the line starting with `spec-kitty safe-commit` (strip ANSI first — see `_plain_output` in `tests/agent/cli/commands/test_charter_synthesize_cli.py`). Parse it with `shlex.split`; drop the leading program token.
  5. Invoke the root CLI app (`from specify_cli import app as cli_app`) via `CliRunner` with the parsed args (`catch_exceptions=False`, `monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)`), cwd already at the repo via `charter_cwd_isolation`.
  6. Assert exit code 0, then assert `git status --porcelain .kittify/` output is empty.
  7. Run it before the fix and confirm it fails with `?? .kittify/charter/synthesized-artifacts.yaml` (and possibly the activation file) left behind. Record that red evidence.
- **Files**: `tests/charter/synthesizer/test_synthesize_activation_append.py`
- **Parallel?**: No — first.
- **Notes**: The assertion is over the whole `.kittify/` tree, not a path list. Once green, the test carries `@pytest.mark.regression` (issue-pinned, already-fixed bugs — see pytest.ini); while red during development it is simply a failing new test in the same PR as the fix (this is a P3 bug, not an open P0, so `p0_repro` does not apply).

### Subtask T002 – Structured append result with written paths

- **Purpose**: Single authority for "which activation-surface files did this run write".
- **Steps**:
  1. In `reach_only.py`, introduce a frozen dataclass (e.g. `SynthesizedActivationAppend`) with `warnings: tuple[str, ...]` and `written_paths: tuple[str, ...]` (or lists; follow the module's existing style). Document it as the append step's write report.
  2. `append_synthesized_activations` and `_append_synthesized_activations_locked` return it. Every existing `return [...]` warnings site becomes `return SynthesizedActivationAppend(warnings=[...])`; the early "nothing to do" returns carry empty written paths.
  3. In the locked body: when `_record()` writes, append `CREATED_ARTIFACTS_PATH.as_posix()`; when `_promote` fires, append the write target's repo-relative POSIX path. Only report paths actually written this call.
  4. Keep warning strings byte-identical.
  5. Export the result type from the module's `__all__`.
- **Files**: `src/charter/activation/synthesizer/reach_only.py`
- **Parallel?**: No.
- **Notes**: `_write_record` may also fire for the legacy `synthesized-tactics.yaml` union — the record path reported is `CREATED_ARTIFACTS_PATH` (the file `_record` writes); check `_write_record`'s actual target before assuming.

### Subtask T003 – api re-export and production callers

- **Purpose**: Adapt the seam's consumers without behavior change.
- **Steps**:
  1. `src/charter/activation/api.py`: re-export the result type alongside `append_synthesized_activations` (follow the existing re-export pattern; update `tests/architectural/test_charter_activation_api_reexport.py` expectations if it enumerates names).
  2. `synthesize.py`: `append_result = append_synthesized_activations(...)`; `warnings_collected.extend(append_result.warnings)`; pass `append_result.written_paths` into `_emit_real_run_report` (new keyword-only parameter, default empty).
  3. `resynthesize.py`: adapt to `.warnings` only (it prints no commit reminder today; do not add one — out of scope).
- **Files**: `src/charter/activation/api.py`, `src/specify_cli/cli/commands/charter/synthesize.py`, `src/specify_cli/cli/commands/charter/resynthesize.py`
- **Parallel?**: No.
- **Notes**: `--json` envelopes keep their current fields (C-003). Do not add the written paths to JSON.

### Subtask T004 – Reminder derivation

- **Purpose**: Render base paths + the run's activation-written paths.
- **Steps**:
  1. `_print_synthesis_commit_reminder(repo_root, extra_paths: Sequence[str] = ())`: build `list(_SYNTHESIS_ARTIFACT_PATHS)`, append each extra path not already present (stable order, dedup), render via `safe_commit_recipe` as today. Update the function's docstring/comment to state the derivation contract (base = always-written synthesis paths; extras = paths the activation append reported writing).
  2. `_emit_real_run_report`: accept the extra paths and forward them at the existing `_print_synthesis_commit_reminder(repo_root)` call site.
  3. Leave the fresh-project seed call site (`synthesize.py`, `_print_synthesis_commit_reminder(repo_root)`) unchanged — no append runs there.
- **Files**: `src/specify_cli/cli/commands/charter/_synthesis.py`
- **Parallel?**: No.
- **Notes**: NFR-003 — no literal activation-surface path may appear in the reminder construction.

### Subtask T005 – Seam tests for written-paths reporting

- **Purpose**: Prove the report matches the disk.
- **Steps**: In `tests/charter/synthesizer/test_synthesize_activation_append.py` (or `test_reach_only_delivery.py` where the fixture already lives):
  1. A run that appends to an explicit list reports BOTH the record path and the activation target path; both files changed on disk.
  2. A run with no explicit list (`activated_tactics=None`) that creates a slug reports the record path only.
  3. A run that changes nothing (second identical run) reports no written paths.
  4. An unreadable-record run reports no written paths and the existing warning.
- **Files**: `tests/charter/synthesizer/test_synthesize_activation_append.py`, `tests/charter/synthesizer/test_reach_only_delivery.py`
- **Parallel?**: Yes, after T002-T004.
- **Notes**: Reuse existing fixtures; do not build new project shapes.

### Subtask T006 – Adapt existing tests; extend reminder assertions

- **Purpose**: Keep the suite green and strengthen the reminder coverage.
- **Steps**:
  1. Mechanically adapt every `append_synthesized_activations(...)` call site in tests to the new result shape (`== []` → `.warnings == []` or an empty-result assertion; `extend(warnings)` → `.warnings`).
  2. In `tests/agent/cli/commands/test_charter_synthesize_cli.py`, keep the existing three-path substring assertion (it must stay green — that run writes no activation-surface path) and add an assertion that no activation-surface path appears when none was written (guards against the fixed-list drift in the other direction).
- **Files**: all test files in `owned_files`.
- **Parallel?**: Yes, after T002-T004.
- **Notes**: Warning-content assertions must not change meaning.

## Test Strategy

- Commands (targeted, no full heavy suites):
  - `uv run pytest tests/charter/synthesizer/test_synthesize_activation_append.py tests/charter/synthesizer/test_reach_only_delivery.py tests/charter/synthesizer/test_styleguide_reach_only.py -x -q`
  - `uv run pytest tests/agent/cli/commands/test_charter_synthesize_cli.py tests/acceptance/test_persistent_deactivation.py -x -q`
  - `uv run pytest tests/architectural/test_charter_activation_api_reexport.py -q`
  - `uv run ruff check src/charter/activation/synthesizer/reach_only.py src/charter/activation/api.py src/specify_cli/cli/commands/charter/_synthesis.py src/specify_cli/cli/commands/charter/synthesize.py src/specify_cli/cli/commands/charter/resynthesize.py`
  - `uv run mypy src/charter/activation/synthesizer/reach_only.py src/specify_cli/cli/commands/charter/_synthesis.py` (or the repo's configured typecheck invocation — match CI).
- Diff-cover: changed lines need ≥90% coverage — the new tests cover the new branches.

## Risks & Mitigations

- Contract-change ripple into unknown callers → grep for `append_synthesized_activations` across `src/` and `tests/` before changing the shape; all call sites are enumerated in this prompt.
- Reminder naming a path safe-commit cannot commit (nonexistent) → extras come only from actual writes; the e2e test executes the real command.

## Review Guidance

- Verify the red-first evidence (T001 failed before the fix with the record left untracked).
- Verify no literal record/activation path in the reminder construction (NFR-003).
- Verify warnings byte-identical; `--json` unchanged; fresh-seed reminder unchanged.
- Verify the e2e test asserts over the whole `.kittify/` tree.

## Progress & Status

- Record notes: `spec-kitty agent tasks add-history WP01 --note "..."`
- Change status: `spec-kitty agent tasks move-task WP01 --to <status>`
