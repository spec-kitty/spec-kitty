---
work_package_id: WP01
title: One POSIX spelling for reported charter paths
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
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
- SC-005
planning_base_branch: issue-6277-charter-synthesize-json-posix-paths
merge_target_branch: issue-6277-charter-synthesize-json-posix-paths
branch_strategy: Planning artifacts for this mission were generated on issue-6277-charter-synthesize-json-posix-paths. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6277-charter-synthesize-json-posix-paths unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-synthesize-json-posix-paths-01M6BTVM
base_commit: 536364d23aad2fcf602400ce8978467fa88e7465
created_at: '2026-11-01T15:21:41.252856+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Core fix
history:
- at: '2026-11-01T15:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/charter_pack_paths.py
create_intent:
- tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/kernel/charter_pack_paths.py
- src/specify_cli/cli/commands/charter/_fresh_project_layer.py
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/charter/activation/synthesizer/write_pipeline.py
- tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One POSIX spelling for reported charter paths

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`spec-kitty charter synthesize --json` must report repository-relative paths with `/` on
every operating system — in `files_written`, `files_planned`, `planned_deletes` and
`written_artifacts[].path` — and the committed `.kittify/charter/synthesis-manifest.yaml`
must record the same POSIX spelling. The defect is issue #6277.

Done when:

- A Windows-simulated regression test exists and is demonstrated **red** against the
  unfixed source, then green after the fix (SC-004).
- All four reported field families are POSIX under simulation (SC-001, SC-002).
- The recorded manifest path and the real-run envelope projection are POSIX, including
  when the on-disk manifest was written by an older Windows run (SC-003).
- POSIX-host output is unchanged: the existing charter synthesis tests pass with no
  expected-value edits (SC-005, NFR-001).

## Context & Constraints

- Spec: `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/spec.md`
- Plan: `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/plan.md` (IC-01, IC-02, IC-03)
- Research: `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/research.md` (D-001…D-003)
- Envelope contract: `contracts/synthesis-envelope.schema.json` — field names, types and
  required set do not change (C-001).
- `kernel/` imports nothing upward; `src/kernel/charter_pack_paths.py` is the sanctioned
  home for charter-pack path arithmetic and already owns `PROJECT_PACK_ROOT_POSIX`.

Defect sites (verified on `main` @ `287a226cfe`):

| Site | Line | Current spelling |
| --- | --- | --- |
| `_fresh_project_layer._materialize_fresh_project_layer` | 139-142 | `str(p.relative_to(repo_root))` |
| `_fresh_project_layer._planned_fresh_project_layer_paths` | 154-157 | same |
| `_fresh_project_layer._planned_fresh_project_layer_deletes` | 163-166 | same |
| `write_pipeline.promote` (`rel_content`) | 654 | same, and it is what the manifest records |
| `_synthesis._load_written_artifacts_from_manifest` | 448-508 | projects `entry.path` verbatim |

The direct-write branch already uses `.as_posix()` (`_fresh_project_layer.py:226,234`;
`_synthesis.py:332,361`) — that is the intended spelling this WP generalises.

## Branch Strategy

- **Strategy**: feature-branch (`issue-6277-charter-synthesize-json-posix-paths`)
- **Planning base branch**: `issue-6277-charter-synthesize-json-posix-paths`
- **Merge target branch**: `issue-6277-charter-synthesize-json-posix-paths`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Add a repo-relative POSIX helper

- **Purpose**: one spelling rule, so a future envelope field cannot reintroduce the
  OS-dependent string (FR-004).
- **Steps**: add `repo_relative_posix(path: Path, repo_root: Path) -> str` (name it
  consistently with the module's existing helpers) to `src/kernel/charter_pack_paths.py`.
  It returns `path.relative_to(repo_root).as_posix()`. Add it to `__all__`. Document the
  contract: *a repo-relative path handed to a consumer is a POSIX string; a `Path` is an
  access path.*
- **Files**: `src/kernel/charter_pack_paths.py`
- **Parallel?**: no (T002/T003 consume it).
- **Notes**: take `Path` arguments, never `str` — an already-relative string cannot be
  normalised safely and must not silently double-prefix.

### Subtask T002 – Fresh-seed reported paths are POSIX

- **Purpose**: fixes `files_written`, `files_planned`, `planned_deletes` and the
  `written_artifacts` entries built from them (FR-001, SC-001, SC-002).
- **Steps**: replace the five `str(...relative_to(repo_root))` sites in
  `_fresh_project_layer.py` with the T001 helper. Keep the function signatures and list
  ordering identical.
- **Files**: `src/specify_cli/cli/commands/charter/_fresh_project_layer.py`
- **Parallel?**: after T001.
- **Notes**: `_planned_fresh_project_layer_paths` must stay byte-identical to
  `_materialize_fresh_project_layer`; after the change both are POSIX on every host, which
  is the dry-run/real-run parity guarantee the module docstring already claims.

### Subtask T003 – Manifest record and projection are POSIX

- **Purpose**: the real-run envelope projects `ManifestArtifactEntry.path` from disk, so
  the recorded value must be POSIX, and a manifest written by an older Windows run must not
  re-leak a backslash into the envelope (FR-002, FR-003, SC-003).
- **Steps**: in `write_pipeline.promote`, compute `rel_content` through the T001 helper.
  In `_synthesis._load_written_artifacts_from_manifest`, normalise `entry.path` to POSIX
  when projecting (for example `PurePosixPath(entry.path.replace("\\", "/")).as_posix()`,
  or an equivalent small helper). Keep the manifest-absent `[]` behaviour and the
  never-raises contract.
- **Files**: `src/charter/activation/synthesizer/write_pipeline.py`,
  `src/specify_cli/cli/commands/charter/_synthesis.py`
- **Parallel?**: after T001.
- **Notes**: normalise only the reported projection; do not rewrite a manifest file on
  read, and do not touch `provenance_path` (already a POSIX literal from
  `provenance_path_for`).

### Subtask T004 – Windows-simulated regression test (red first)

- **Purpose**: make the Windows spelling observable on POSIX CI and prove the harness is
  not vacuous (FR-006, SC-004).
- **Steps**: create
  `tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py`.
  - A fixture patches `Path.relative_to` (via `monkeypatch.setattr`) so it returns a
    Windows-flavoured path for the call duration: build `PureWindowsPath(*parts)` from the
    real result's parts, so `str()` renders `\` while `.as_posix()` renders `/`.
  - **Control assertion (non-vacuity)**: prove the simulation actually renders backslashes
    on a plain `str(Path(...).relative_to(...))` in the same fixture — a harness that does
    not reproduce the bug must fail the test, not pass it.
  - Drive the **pre-existing entry point**: `runner.invoke(charter_app, ["synthesize",
    "--json"])` (and the `--dry-run` variant) on a fresh project scaffolded the way
    `tests/integration/test_charter_synthesize_fresh.py` does it (`git init`, minimal
    interview answers, `charter generate`).
  - Assert every string in `files_written`, `files_planned`, `planned_deletes` and
    `written_artifacts[].path` contains no `\`, equals the POSIX spelling of the file that
    exists on disk, and that `files_planned == files_written` for the same project.
  - Add a real-run case (authored doctrine present) asserting the manifest records POSIX
    paths and the envelope projection has no `\`; include a case where the on-disk manifest
    is seeded with a backslash path to prove the projection normalises on read.
  - Mark the module `[pytest.mark.unit]` (or the closest tier the sibling CLI tests use)
    and keep it subprocess-free so it stays fast (NFR-003).
- **Files**: `tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py` (new)
- **Parallel?**: author it before T001–T003; run it against the unfixed source first.
- **Notes**: do **not** fake `os.name` — `tests/kernel/test_is_windows_seam.py` records
  that this flips `pathlib` to `WindowsPath` mid-run and crashes pytest. Patch rendering,
  not the platform.

### Subtask T005 – Targeted verification

- **Purpose**: prove no POSIX-host output moved and the change is type/lint clean.
- **Steps**: run, from the repository root:
  - `uv run pytest tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py -q`
  - `uv run pytest tests/integration/test_charter_synthesize_fresh.py tests/charter_pack_synthesizer -q` (targeted; never a full heavy sweep)
  - `uv run ruff check <changed files>` and `uv run ruff format --check <changed files>`
  - `uv run mypy <changed source files>` (or the repo's configured mypy entry point)
- **Files**: n/a (verification)
- **Parallel?**: last.
- **Notes**: record the red run (test failing before the fix) and the green runs in the
  work-package history. If a failure is unrelated to this diff, stop and report it; do not
  skip, xfail or weaken a gate.

## Test Strategy

- New regression module as described in T004 (red → green proof).
- Existing synthesis pipeline and integration tests must stay green with **no** edit to
  their expected values — that is the POSIX-host no-op guarantee (NFR-001).
- If the changed source files are typed, the configured compiler/typecheck command must
  pass, not just pytest.

## Risks & Mitigations

- **POSIX churn**: any accidental change to POSIX-host strings breaks committed fixtures.
  Mitigation: assert existing suites unchanged, edit no expected value.
- **Simulation fragility**: patching `Path.relative_to` globally can affect unrelated calls
  inside the invoked command. Mitigation: return the same relative path with a Windows
  flavour only (parts preserved), so callers that re-split or re-join still work; keep the
  patched window to the invoke.
- **Projection normalisation hiding a real bug**: normalising on read must not mask a
  writer regression. Mitigation: T003 fixes the writer too, and the test asserts both the
  manifest bytes and the envelope.

## Review Guidance

- Confirm the regression test fails when the source change is reverted (ask for the red run
  output, or revert locally and run it).
- Confirm the control assertion genuinely fails under a no-simulation harness.
- Confirm no expected value in an existing test was edited, and no gate was weakened.
- Confirm envelope schema and field names are untouched.
- Confirm the manifest projection remains non-raising and still returns `[]` when the
  manifest is absent.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
