---
work_package_id: WP02
title: Adopt the isolation in every leaking test
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-007
planning_base_branch: issue-5317-charter-test-cwd-isolation
merge_target_branch: issue-5317-charter-test-cwd-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5317-charter-test-cwd-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5317-charter-test-cwd-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-test-cwd-isolation-01M43CM3
base_commit: f0f8ccdbf21812bbe5891c94e210d3b5a89136d7
created_at: '2026-10-04T12:35:38.713277+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Adoption
history:
- at: '2026-10-04T12:11:55Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/agent/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/agent/cli/commands/test_charter_cli.py
- tests/agent/cli/commands/test_charter_synthesize_cli.py
- tests/agent/cli/commands/test_charter_status_cli.py
- tests/charter/test_references_missing_failclosed.py
- tests/charter/test_reject_not_drop_cli.py
- tests/charter/test_presence_gate_bundle_authority.py
- tests/charter/test_phase3_integration.py
- tests/consolidation/test_profile_charter_e2e.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Adopt the isolation in every leaking test

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

Every test that directs a guarded charter write command at a test tmp project gives the same result from a linked worktree and from the repository root checkout.

Done when, run from the lane worktree (a linked worktree):

1. These tests pass (all red before this WP with `Refusing charter write from linked git worktree`):
   - `tests/agent/cli/commands/test_charter_cli.py`: `test_generate_command_success`, `test_generate_does_not_require_force_when_charter_yaml_already_exists`, `test_generate_command_force_overwrites`, `test_generate_force_preserves_curated_charter_prose_2772`, `test_generate_force_preserves_authored_charter_yaml_sections`, `test_context_bootstrap_then_compact`, `test_context_compact_mode_auto_syncs_missing_extracted_artifacts`
   - `tests/agent/cli/commands/test_charter_synthesize_cli.py`: `TestSynthesizeHappyPath::test_synthesize_fixture_dry_run`, `::test_synthesize_json_output`, `::test_synthesize_non_json_reminds_to_commit_artifacts`, `::test_synthesize_dry_run_json`, `TestSynthesizeEnvelopeContract::test_synthesize_fixture_envelope_has_contracted_fields`, `TestSynthesizeErrorPaths::test_pack_config_error_surfaces_diagnostic_body`
   - `tests/agent/cli/commands/test_charter_status_cli.py::TestCharterStatus::test_generated_host_roundtrip_status_reports_promoted_provenance`
   - `tests/charter/test_references_missing_failclosed.py`: `test_synthesize_json_fails_closed_when_charter_yaml_missing`, `test_synthesize_json_succeeds_past_preflight_when_bundle_complete`
   - `tests/charter/test_reject_not_drop_cli.py`: `test_synthesize_json_surfaces_unknown_artifact_id_without_traceback`, `test_synthesize_console_surfaces_unknown_artifact_id_without_traceback`
   - `tests/charter/test_presence_gate_bundle_authority.py::TestFR006JsonPresentSignalFlip::test_cli_context_json_present_survives_charter_md_deletion`
   - `tests/consolidation/test_profile_charter_e2e.py::test_local_support_declarations_end_to_end`
   - `tests/charter/test_phase3_integration.py::test_phase3_dry_run_evidence_smoke`
2. Every other test in those eight files still passes; no test count drops; no `skip`/`xfail` added (NFR-001).
3. No file under `src/` changed.

The list is the known set, not the contract (C-005): any other test in these files that reaches `generate`, `synthesize` or `resynthesize` with the working directory in the invoking checkout adopts the fixture too.

Requirement refs: FR-004, FR-007.

## Context & Constraints

Read before coding: `.kittify/charter/charter.md`, `kitty-specs/charter-test-cwd-isolation-01M43CM3/spec.md`, `kitty-specs/charter-test-cwd-isolation-01M43CM3/plan.md` (Design section), `kitty-specs/charter-test-cwd-isolation-01M43CM3/research.md`, `kitty-specs/charter-test-cwd-isolation-01M43CM3/contracts/test-isolation-contract.md`. Load action doctrine with `spec-kitty charter context --action implement`.

The defect in one paragraph: the charter commands `generate`, `synthesize` and `resynthesize` call `resolve_charter_write_root(Path.cwd())` (`src/specify_cli/cli/commands/charter/generate.py:438`, `synthesize.py:212`, `resynthesize.py:103`). The guard refuses when the **process working directory** is a linked worktree. Many tests point the command at a **test tmp project** by patching `specify_cli.cli.commands.charter.find_repo_root`, but never change directory, so the guard sees the **invoking checkout**. When pytest starts in a lane worktree (a linked worktree) those tests fail with `Refusing charter write from linked git worktree`.

Hard constraints (reviewers reject on any breach):

- **C-001** No change under `src/`. `git diff --stat issue-5317-charter-test-cwd-isolation -- src/` must stay empty.
- **C-002** Never patch, stub or replace `resolve_charter_write_root` to change its result. The real guard must run.
- **C-003** The isolation fixture is opt-in.
- **C-004** Exactly one definition of the isolation fixture in `tests/`.
- **C-006** Run only the named test files below. No directory runs, no `make test-fast`, no `tests/architectural/` sweep.
- No `# noqa`, `# type: ignore`, `skip` or `xfail` added. New code passes `ruff check`, `ruff format --check --force-exclude <files>` and `mypy` clean.
- Keep the four terms distinct in docstrings and messages: process working directory / repository root checkout / linked worktree / test tmp project. Say "Mission", never "feature".

You work in a lane worktree, which is itself a linked worktree. That is useful: the affected tests are red here before the fix and green after. Run tests with the lane's own sources (`PYTHONPATH=$PWD/src <repo-root>/.venv/bin/python -m pytest ...` if the lane has no `.venv`; do not use a bare `uv run`).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5317-charter-test-cwd-isolation; completed changes must merge back into issue-5317-charter-test-cwd-isolation.
- **Planning base branch**: issue-5317-charter-test-cwd-isolation
- **Merge target branch**: issue-5317-charter-test-cwd-isolation

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path `spec-kitty agent action implement` gives you, never a reconstructed one.

`charter_cwd_isolation` comes from `tests/_support/charter_cwd.py` (WP01). Request it as a fixture argument and call it with the test's project root before the first guarded invoke. It sets the process working directory and `find_repo_root` to that root. Tests may keep their own `with patch("specify_cli.cli.commands.charter.find_repo_root")` blocks; both end at the same root. Prefer the smallest diff: add the fixture argument and one call per test (or one small autouse fixture per test class/file when every test in it uses the same root), rather than rewriting the test.

## Subtasks & Detailed Guidance

### Subtask T006 – `tests/agent/cli/commands/` (three files)

- **Purpose**: 14 of the known failures live here.
- **Steps**:
  1. Run the three files from the lane first and save the failing ids (expected: the 14 listed above). This is the before-evidence.
  2. `test_charter_cli.py`: the seven affected tests create their project root inside the test body (for example `tmp_path / "repo"`, then the file's `_git_init` helper) and patch `find_repo_root` to it. Add the `charter_cwd_isolation` argument and call `charter_cwd_isolation(repo_root)` **after** the root has been created and git-initialised and **before** the first invoke — calling it at the top of the test would change directory into a path that does not exist yet. The two `context` tests fail in their preparatory `generate` invoke; isolate before that step.
  2b. Vacuous-green trap: `TestSynthesizeErrorPaths::test_missing_interview_answers_exits_1` and `::test_unknown_adapter_exits_1` (`test_charter_synthesize_cli.py:423-435`) assert only exit code 1, which the guard's refusal also produces from a linked worktree — they "pass" today for the wrong reason. Isolate them too, and add to each an assertion that `Refusing charter write from linked git worktree` is NOT in the output, so they prove they reached the error they are named for. Look for other exit-code-only tests of guarded commands in the eight files and treat them the same way.
  3. `test_charter_synthesize_cli.py` and `test_charter_status_cli.py`: find each test's project root and do the same. Where a whole class shares one root fixture, a class-level autouse fixture that requests `charter_cwd_isolation` and calls it is acceptable.
  4. Watch for assertions on relative paths or on output that embeds the working directory; changing directory can alter them. If one changes, understand why before touching the assertion; do not weaken an assertion to get green.
  5. Re-run the three files: all pass, same total count as before.
- **Parallel?**: Independent of T007/T008 (different files).

### Subtask T007 – `tests/charter/` (three files)

- **Steps**:
  1. Before-evidence as in T006 (expected failing: the 5 ids listed above for these files).
  2. `tests/charter/conftest.py` has an autouse `_git_init_tmp_path` that makes `tmp_path` a git repository, so a project directory nested under `tmp_path` resolves to that toplevel. That is fine for the guard (a non-linked repository), but note it when reading results.
  3. `test_reject_not_drop_cli.py:69-73` is deliberately a no-mocking test: it uses `monkeypatch.chdir` only, with no `find_repo_root` patch. Leave chdir-only tests like that as they are — the shared fixture would add a mock they are designed not to have. Only tests that patch `find_repo_root` and leave the working directory in the invoking checkout adopt the fixture. `contextlib.chdir` helpers elsewhere (for example `test_synthesize_cli_reconcile.py:278`) are out of scope.
  4. `test_references_missing_failclosed.py` patches with `patch(..., return_value=...)` (near line 161); `test_presence_gate_bundle_authority.py` patches near line 227. Adopt the fixture in each affected test.
  5. Re-run the three files: all pass.

### Subtask T008 – `tests/consolidation/test_profile_charter_e2e.py` (#5601)

- **Steps**:
  1. `test_local_support_declarations_end_to_end` (line 301) patches `find_repo_root` at line 321 and invokes `charter generate`. Add the fixture and isolate to the test's project root.
  2. Check the sibling tests in the file that invoke `generate` (for example `test_local_support_additive_warning_when_overlapping_built_in_concept`, line 369): if they reach the guard with the working directory in the invoking checkout they pass or fail together with the first one. Adopt the fixture in every one that reaches a guarded command, including those that currently pass for another reason.
  3. Run the file: all pass.

### Subtask T009 – Dry-run smoke test remedy (`test_phase3_dry_run_evidence_smoke`)

- **Purpose**: This test starts `python -m specify_cli charter synthesize --adapter fixture --dry-run-evidence` as a subprocess with `cwd` = the invoking checkout (`tests/charter/test_phase3_integration.py:314-342`). The guard runs before the dry-run branch (`synthesize.py:212` vs `:393`), so it is refused from a linked worktree. The fixture cannot help a subprocess.
- **Steps**:
  1. Read the test and the two assertions that must stay: `Evidence dry-run summary` and `Code signals:` in stdout (around lines 350-354).
  2. Read the dry-run path in `src/specify_cli/cli/commands/charter/synthesize.py` to learn what it reads from the working directory / resolved root (the code-reading collector, any `.kittify` requirement).
  3. Feasibility was checked at planning: in a seeded tmp project the dry-run exits 0 with both asserted strings once the directory is a git repository (a plain directory fails with "Unable to locate repository root"); `tests/charter/conftest.py:39` already git-initialises `tmp_path`. Change the test to take `tmp_path`, seed a small Python project in it (a couple of `.py` files and a `conftest.py`, as the collector test earlier in the same file does around lines 280-300), and run the subprocess with `cwd=str(tmp_path)`. Keep `PYTHONPATH` pointing at the invoking checkout's `src/` exactly as now.
  4. If the command needs the directory to be a git repository or to hold a `.kittify` layout, add the minimum to the seeded project. `tests/charter/conftest.py` already git-initialises `tmp_path`.
  5. Both assertions stay. No `skip`, `xfail`, or branch on the kind of checkout. Do not use another real checkout (for example the repository root checkout found through `git worktree list`) as the working directory.
  6. **Deferral path**: if the dry-run genuinely needs something only the real checkout provides and the test would stop testing what it was written for, stop. Leave the test unchanged, and report in the Activity Log exactly what is needed and why, so the orchestrator can record the deferral and file the follow-up (FR-007 second branch). Do not change `src/`.
  7. Run `tests/charter/test_phase3_integration.py` in full: all pass.

### Subtask T010 – Verify and hand over

- **Steps**:
  1. From the lane worktree:

     ```bash
     pytest tests/agent/cli/commands/test_charter_cli.py \
            tests/agent/cli/commands/test_charter_synthesize_cli.py \
            tests/agent/cli/commands/test_charter_status_cli.py \
            tests/charter/test_references_missing_failclosed.py \
            tests/charter/test_reject_not_drop_cli.py \
            tests/charter/test_presence_gate_bundle_authority.py \
            tests/charter/test_phase3_integration.py \
            tests/consolidation/test_profile_charter_e2e.py -q
     ```

     Expect zero failures. Compare total collected counts with the before-run: equal.
  2. `ruff check` and `ruff format --check --force-exclude` on the eight files. Some may be on the formatter-debt ratchet; `--force-exclude` keeps those from being reformatted wholesale. Do not reformat lines you did not change.
  3. `git diff --stat issue-5317-charter-test-cwd-isolation -- src/` is empty.
  4. Activity Log: before/after counts per file, commands, and any test whose assertion you had to touch, with the reason.

## Test Strategy

The eight files above, run from the lane worktree, are the proof: red before, green after. The reviewer repeats the run from the lane and the orchestrator repeats it from the repository root checkout after consolidation.

## Risks & Mitigations

- **Changing directory alters output or relative-path behaviour** → investigate; never loosen an assertion to pass.
- **A test needs the invoking checkout's working directory for another reason** → isolate only around the guarded invoke if possible; otherwise report it.
- **Ratchet-listed files get reformatted** → use `--force-exclude`; keep the diff to the lines you changed.
- **Smoke test cannot be made independent test-side** → deferral path in T009, not a product change.

## Review Guidance

- Re-run the eight files from a linked worktree; zero failures, counts unchanged.
- Grep the diff for `skip`, `xfail`, `resolve_charter_write_root`, and loosened assertions: none.
- Confirm the exit-code-only tests named in T006 step 2b now assert the refusal text is absent.
- Chdir-only, no-mock tests (for example `test_reject_not_drop_cli.py:69-73`) are correctly left unchanged.
- Smoke test: both assertions present; `cwd` is a tmp project, not a real checkout.
- `git diff --stat issue-5317-charter-test-cwd-isolation -- src/` empty.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last). Append at the end, format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`, UTC.

- 2026-10-04T12:11:55Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status. Record subtask completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.
