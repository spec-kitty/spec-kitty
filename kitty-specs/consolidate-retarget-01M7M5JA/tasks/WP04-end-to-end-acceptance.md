---
work_package_id: WP04
title: End-to-end acceptance
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
- FR-009
- FR-011
- FR-012
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
- SC-003
- SC-004
- C-004
planning_base_branch: issue-7692-consolidate-retarget
merge_target_branch: issue-7692-consolidate-retarget
branch_strategy: Planning artifacts for this mission were generated on issue-7692-consolidate-retarget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7692-consolidate-retarget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-retarget-01M7M5JA
base_commit: 740382db16d73f4ff6906b714eb54f51b0e0b45e
created_at: '2026-11-17T11:48:23.434983+00:00'
subtasks:
- T018
- T019
- T020
- T021
phase: Phase 4 - Acceptance
history:
- at: '2026-11-17T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/test_consolidate_retarget.py
execution_mode: code_change
owned_files:
- tests/terminus/test_consolidate_retarget.py
- tests/terminus/test_target_override_recorded_target_unwritable.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – End-to-end acceptance

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Any review feedback is your TODO list.

---

## Objectives & Success Criteria

Prove the spec through the REAL `spec-kitty consolidate` CLI over real git, on the #5783 fixtures (lanes and coord, `main` unprotected unless the arm says otherwise). Each arm is non-vacuous: its observable fails on a do-nothing or partial implementation.

- **Red-first evidence (charter SO #4).**
  1. Write the file.
  2. Run it against the planning base `issue-7692-consolidate-retarget`, before WP01–WP03 (`git stash` / a scratch worktree at the base). Record the failing counts and the failure reasons in the WP history with `add-history`.
  3. Then run it on the lane, where it must be green.

  The real red witnesses are the success arm's `done` / flatten / `meta.json` rows. The retrospective row already goes to the effective target (#7201), so it is a weak witness (squad T3).

## Context & Constraints

- Read `spec.md` (all FRs, NFR-001..003, SC-001..004), `research.md` (§ Planned acceptance tests, squad T1–T12), and `contracts/cli-retarget.md`.
- Reuse, do not copy: `tests/terminus/test_target_override_recorded_target_unwritable.py` (`_lanes`, `_coord`, `_check_out_override`, `_consolidate`, `_branches`, `_reflogs`, `_assert_refused_before_any_mutation`, `_EMPTY_PROTECTION`), `tests/terminus/conftest.py` (`run_terminus`, `blob_present_at`, `_git`), and `tests/terminus/rollback_harness.py` (`flat`, `reflog_shas`, `_HARD_KILL`, the `-c` wrapper pattern).
- NFR-003: at most 60 s added. A run is about 8 s, so parametrise lanes/coord only where the topology matters (the success arm, the failure arm). Every other arm uses `_lanes`.
- Mark the module `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`, like its sibling.

## Branch Strategy

- **Planning base branch**: `issue-7692-consolidate-retarget`
- **Merge target branch**: `issue-7692-consolidate-retarget`

`spec-kitty agent action implement WP04 --agent claude --mission consolidate-retarget-01M7M5JA`

## Subtasks & Detailed Guidance

### Subtask T018 – Success observables per S4 row (lanes + coord)

`test_retarget_lands_every_write_on_the_new_target[lanes|coord]`. Build the Mission, run `_check_out_override` (which cuts `develop`), record `main`'s tip and reflog, then run `consolidate --mission <m> --yes --target develop --retarget --retarget-reason "e2e"`. Assert:

1. Exit 0. No `Traceback` on stderr.
2. `git show develop:kitty-specs/<slug>/meta.json`:
   - `target_branch == "develop"`;
   - `retarget_history` has length 1 with `from == "main"`, `to == "develop"`, `reason == "e2e"`, and a non-empty `actor` and `at`;
   - `mission_number` is an int;
   - coord: no `coordination_branch` key (flattened). Read the flatten's exact shape from `phase_teardown.py`'s flatten and assert what it writes; do not guess.
3. The status surface on `develop`: every WP is `done`. Reduce `develop:kitty-specs/<slug>/status.events.jsonl` with `specify_cli.status.reducer`, reading the blob to a temp file, or use `spec-kitty agent tasks status --json` if it supports a ref; pick what the sibling tests use.
4. `develop:kitty-specs/<slug>/retrospective.yaml` exists. Check the exact path the retrospective terminus writes (`post_merge/retrospective_terminus.py`).
5. `git log --format=%s pre_tip..develop`:
   - contains exactly one `retarget main -> develop` subject;
   - that commit is the FIRST after the pre-run tip (`rev-list --reverse`);
   - the done / retrospective / flatten (coord) subjects are present.
   - Use the real subjects; grep the sources for the message templates.
6. `main`'s tip and reflog are unchanged, and `blob_present_at(repo, "main", "src/pkg/wp01.py")` is False.
7. `git status --porcelain -- kitty-specs` is empty. Scope to `kitty-specs` only, because `.kittify/` runtime files are legitimately untracked.

### Subtask T019 – Failure, abort, re-run and resume arms

1. **Injected failure after the retarget commit** (`[lanes|coord]`).
   - Run the CLI through a `-c` wrapper modelled on `rollback_harness._HARD_KILL`: before `main()`, patch `specify_cli.consolidation.executor._phase_merge_lanes` to `raise RuntimeError("injected")`.
   - Assert:
     - exit ≠ 0;
     - the output contains the rollback report;
     - `develop`'s tip equals its pre-run tip;
     - `develop:meta.json` has `target_branch == "main"`;
     - lanes: the Mission branch tip equals its pre-run tip;
     - `state.json` (`.kittify/runtime/merge/*/state.json`) still has `retarget` with `committed == False`.
   - Then re-run `--target develop --retarget` (no patch). Expect exit 0 and exactly ONE `retarget main -> develop` commit on `develop` (NFR-002).
2. **Abort.** After the injected failure, run `consolidate --abort --mission <m>`.
   - Assert: exit 0, no merge record, `develop` at its pre-run tip.
   - Then a plain `--target develop` (no `--retarget`) is refused with `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE` through `_assert_refused_before_any_mutation`.
3. **Resume after an interrupt** (lanes).
   - Hard-kill at `phase_advance._persist_retarget_committed` (WP03 makes it a module-level callable), then run `consolidate --resume`.
   - This is the documented residual. Assert the refusal is `UNEXPLAINED_BRANCH_MOVE`, with exit code 1, and that nothing else moved.
   - Then `--abort --release-branch develop --release-reason "e2e"` followed by a fresh `--target develop --retarget` lands. If the release flow cannot be driven deterministically, assert only the refusal code and record that in the history.
   - Add a second resume arm: kill at `executor._phase_merge_lanes` AFTER the retarget committed (patch it to `os.kill(os.getpid(), signal.SIGKILL)`, like `tests/consolidation/characterization_support.py`), then `--resume`. Expect exit 0, the landing on `develop`, and exactly one retarget commit.
4. **Resume mismatch.** After the second kill, run `--resume --target other --retarget` (create the branch `other` first). Expect `RETARGET_RESUME_MISMATCH`, exit 1, and nothing moved.

### Subtask T020 – Protection, FR-011, CLI validation, divergent `<b>`, dry-run parity

All on `_lanes` unless noted.

1. **Protected `<b>`.** Commit `protection:\n  protected_branches: [develop]\n` instead of the empty list, then `--target develop --retarget`. Expect `PROTECTED_BRANCH_REFUSED`, and `_assert_refused_before_any_mutation`-style invariants (the helper asserts the #5783 code; write a sibling helper with the code as a parameter, inside this test file).
2. **Protected old target, admitted (D2 / flag).** Keep the default protection (no `_EMPTY_PROTECTION`, so `main` is protected), cut `develop`, and run `--target develop --retarget`. Expect exit 0 and the landing on `develop`. The test docstring states that this pins the D2 consequence the operator was told about.
3. **FR-011 arms**, each giving `RETARGET_RECORD_UNWRITABLE` with nothing moved, plus a `--dry-run --json` twin reporting the same `error_code`:
   - `develop` cut BEFORE the Mission existed. Find the init commit (`git rev-list --max-parents=0 main`); cut `develop` there, then check it out. If the Mission directory exists in the root checkout from an untracked state, the check must still refuse; verify.
   - A dirty `meta.json` on `develop`: modify it and do not commit.
   - An untracked `meta.json`: `git rm --cached` the file on `develop` and commit, leaving it on disk.
4. **CLI validation.**
   - `--retarget` without `--target` gives exit 2;
   - `--retarget-reason x` without `--retarget` gives exit 2;
   - `--target main --retarget` gives exit 0, the landing on `main`, and NO `retarget` commit (FR-012).
5. **Divergent `<b>`.** On `develop`, add a commit touching an unrelated file (for example `docs/x.md`) before the run. `--target develop --retarget` exits 0 and that commit stays reachable from `develop`.
6. **Dry-run parity** (SC-004). `--dry-run --json --target develop --retarget` on the success fixture: exit 0, the payload has `retarget == {"from": "main", "to": "develop"}`, and nothing moved.

### Subtask T021 – Re-pin the #5783 file

In `tests/terminus/test_target_override_recorded_target_unwritable.py::_assert_refused_before_any_mutation`, add `assert "--retarget" in output`. The plain-`--target` remedy now names the opt-in (FR-002). Change nothing else in that file.

## Test Strategy

```
.venv/bin/python -m pytest tests/terminus/test_consolidate_retarget.py tests/terminus/test_target_override_recorded_target_unwritable.py -n 6 --dist loadfile -q --durations=20
```
Record the durations. NFR-003 allows at most 60 s added, wall time with `-n 6`.
Ruff, ruff format (`--force-exclude`) and mypy on the test file.

## Risks & Mitigations

- **Flaky kill windows.** Use the exact `_HARD_KILL` mechanism; never sleep.
- **A wrong assumption about an exact path or subject.** Grep the source for the message or path; never hardcode a guess.
- **Time budget.** Drop parametrisation before dropping arms.

## Review Guidance

- Each success observable fails on the pre-change code. The red evidence is in the history.
- Refusal arms reuse the refusal invariant set.
- No arm is vacuous: each has a same-fixture positive control.

## Progress & Status

`spec-kitty agent tasks add-history WP04 --note "..."`; `spec-kitty agent tasks mark-status T0xx --status done --mission consolidate-retarget-01M7M5JA`.
