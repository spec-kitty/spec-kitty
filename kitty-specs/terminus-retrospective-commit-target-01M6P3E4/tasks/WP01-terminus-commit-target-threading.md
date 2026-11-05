---
work_package_id: WP01
title: Thread the resolved landing target through the terminus retrospective commit
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
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
planning_base_branch: issue-7201-terminus-retrospective-target
merge_target_branch: issue-7201-terminus-retrospective-target
branch_strategy: Planning artifacts for this mission were generated on issue-7201-terminus-retrospective-target. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7201-terminus-retrospective-target unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 1 - The fix
history:
- at: '2026-11-05T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/post_merge/
create_intent:
- tests/specify_cli/post_merge/test_retrospective_commit_target.py
- tests/specify_cli/cli/commands/test_mission_close_target.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/specify_cli/post_merge/retrospective_terminus.py
- src/specify_cli/coordination/teardown.py
- src/specify_cli/consolidation/phase_teardown.py
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/cli/commands/mission_type.py
- tests/specify_cli/post_merge/test_retrospective_commit_target.py
- tests/specify_cli/cli/commands/test_mission_close_target.py
- docs/api/cli-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Thread the resolved landing target through the terminus retrospective commit

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for
this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

A `spec-kitty consolidate --mission <m> --target <branch>` run leaves
`kitty-specs/<slug>/retrospective.yaml` and its `status.events.jsonl` append **committed on
`<branch>`**, with no manual step and no ref other than `<branch>` moved. The refusal warning,
when it still fires, prints a recovery command that works as printed
(`spec-kitty mission close --mission <slug> --target <branch>`).

Done means:

- the terminus commits onto the caller-supplied resolved target (T001–T006);
- the consolidate run supplies that target on **both** legs — the teardown persist leg (where
  the commit normally happens) and the second terminus call site in the same run (T005, T006);
- `mission close` can be aimed at the same branch, and behaves exactly as today without it
  (T008, T009);
- the warning's recovery command carries the target when one was supplied (T007);
- `safe_commit`, `commit_guard` and the terminus's fail-open policy are **unchanged** (FR-006);
- the CLI reference is regenerated for the new option (T010) and the targeted blast radius is
  green (T011).

## Context & Constraints

### Why this shape (read before writing code)

Issue #7201 reproduced on `main@b4d1e918e2`:

```
safe_commit: worktree <repo> HEAD is 'topic-landing', expected 'main'
```

`safe_commit` refuses when `HEAD != destination_ref` before staging
(`src/specify_cli/git/commit_helpers.py`, validation step 4 → `SafeCommitHeadMismatch`). The
destination it was given came from the placement port reading `meta.json`'s `target_branch`
(`main`), which is **stale** for a `consolidate --target <topic>` run. The refusal is correct;
the withheld destination is the defect. Full determination:
`kitty-specs/terminus-retrospective-commit-target-01M6P3E4/research.md` §"Which side is wrong".

**Do not** relax the guard, add `--no-verify`, or make the terminus retry differently.

### Existing mechanism to reuse

`commit_merge_bookkeeping(destination_ref_override=...)`
(`src/specify_cli/git/bookkeeping_commit.py`) exists for exactly this — its docstring calls it
"the RESOLVED merge target, threaded by the merge executor (terminus-merge-integrity C-1 /
#4985/#4991)". Live users: `consolidation/phase_bookkeeping.py:751`,
`consolidation/phase_teardown.py:338`, `:959`, `consolidation/mission_number/bake.py:497`.
`tests/architectural/test_no_write_side_rederivation.py` already sanctions
`CommitTarget(ref=destination_ref_override)` as *not* checkout-derived.

### Constraints

- New parameter: keyword-only, `str | None = None`, additive (C-001). `None` **must** mean
  today's behaviour, byte-for-byte.
- Every destination is caller-resolved; **never** read the current branch (NFR-002).
- Route only through `commit_merge_bookkeeping`; no second `GuardCapability` call site
  (NFR-001).
- Fail-open preserved: the terminus still warns and returns `None` on any commit failure; no
  path may newly raise into `merge`/`close` (C-002).
- No test skipped, xfailed or loosened (C-003).
- Reference docs: `.kittify/charter/charter.md` (ATDD-first, smallest viable diff),
  `docs/context/orchestration.md` (`#target-ref--commit-target`, `#primary-partition`),
  `kitty-specs/terminus-retrospective-commit-target-01M6P3E4/plan.md`.

## Branch Strategy

- **Strategy**: `issue-7201-terminus-retrospective-target` in the repository root checkout;
  this WP is a `code_change` and owns no `kitty-specs/` path.
- **Planning base branch**: `issue-7201-terminus-retrospective-target`
- **Merge target branch**: `issue-7201-terminus-retrospective-target`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Write the red-first test (prove the bug through the real entry point)

- **Purpose**: witness the defect before the fix, and keep a permanent regression net.
- **Steps**:
  1. Create `tests/specify_cli/post_merge/test_retrospective_commit_target.py`.
  2. Build one shared real-git fixture (no mocking of git) with `pytest`'s `tmp_path`:
     `git init -b main`, commit `kitty-specs/<slug>/meta.json` with
     `{"mission_id": "01ABC…", "mid8": "…", "mission_slug": "<slug>", "target_branch": "main"}`,
     then `git checkout -b topic-landing`, then dirty `retrospective.yaml` + append a line to
     `status.events.jsonl`.
  3. `run_retrospective_postcondition(mission_slug=<slug>, repo_root=repo, destination_ref="topic-landing")`
     → assert: returns a SHA; `git status --porcelain` is empty; the commit exists on
     `topic-landing`; `main`'s tip is unchanged (SC-001, SC-002).
  4. **Positive control on the same fixture** (SC-003): with `destination_ref=None`, assert the
     call returns `None`, both files are still uncommitted, and no ref moved — the guard is
     intact and the terminus is still fail-open. Build both assertions from one shared fixture
     builder so they cannot drift (`acceptance-criteria-non-vacuity`).
  5. Add a third case for the warning text: use `caplog` and assert the rendered warning carries
     `--target topic-landing` (SC-004) once T007 lands. Write this assertion first; it will be
     red until T007.
  6. Markers: the file needs `@pytest.mark.integration` and `@pytest.mark.git_repo` (see
     `tests/specify_cli/post_merge/test_retrospective_triggering.py` for the idiom and
     `pytest.ini` for what each gate selector needs — an unselected marker means the file runs in
     no gate).
- **Files**: `tests/specify_cli/post_merge/test_retrospective_commit_target.py` (new).
- **Notes**: the terminus resolves its durable home through
  `specify_cli.retrospective.writer.resolve_retrospective_home`; the existing tests patch it
  (`_patch_resolver`) to the fixture directory. Do the same if real resolution drags in mission
  state you are not modelling. Capture the RED output in your RP progress note.

### Subtask T002 – Accept the destination on the terminus entry point

- **Purpose**: let the caller state which branch this run landed on.
- **Steps**: in `src/specify_cli/post_merge/retrospective_terminus.py`, add keyword-only
  `destination_ref: str | None = None` to `run_retrospective_postcondition`, document it (why it
  exists, that `None` = placement resolution), and forward it to `_commit_captured_retrospective`.
- **Files**: `src/specify_cli/post_merge/retrospective_terminus.py`.
- **Notes**: the module docstring's invariants list should gain one line — "the destination is
  the caller's resolved landing target when supplied" — without rewording the fail-open contract.

### Subtask T003 – Forward it into the sanctioned bookkeeping seam

- **Purpose**: make the resolved target the commit's destination.
- **Steps**: in `_commit_captured_retrospective`, pass
  `destination_ref_override=destination_ref` to `commit_merge_bookkeeping`, keeping
  `branch=degrade_ref` as the existing degrade path (it is consulted only when no override is
  supplied). Update the function docstring's rationale.
- **Files**: `src/specify_cli/post_merge/retrospective_terminus.py`.
- **Notes**: do not add a `get_current_branch` read anywhere; the override is authoritative.

### Subtask T004 – Carry the destination on the teardown persist seam

- **Purpose**: the commit normally happens in the persist leg, *before* the coordination
  worktree is destroyed — fix the seam or the consolidate path stays broken.
- **Steps**: in `src/specify_cli/coordination/teardown.py`, add keyword-only
  `destination_ref: str | None = None` to `teardown_coordination_topology` and to
  `_persist_retrospective`, forward it, and document it in the Args block.
- **Files**: `src/specify_cli/coordination/teardown.py`.
- **Notes**: `mission_creation_rollback.py` and `missions/_create.py` call the seam with
  `persist=False`; leaving their calls untouched is correct.

### Subtask T005 – Consolidate's teardown leg supplies the target

- **Purpose**: the concrete path from the issue.
- **Steps**: in `src/specify_cli/consolidation/phase_teardown.py::_teardown_coord_worktree`, pass
  `destination_ref=run.lanes_manifest.target_branch` to `teardown_coordination_topology`, with a
  one-line comment naming #7201 and why the meta-resolved destination is stale here (mirroring
  the existing `destination_ref_override=lanes_manifest.target_branch` comment at
  `phase_bookkeeping.py:740-751`).
- **Files**: `src/specify_cli/consolidation/phase_teardown.py`.
- **Notes**: `lanes_manifest.target_branch` is already `--target` > persisted state > meta.

### Subtask T006 – Consolidate's second terminus call site supplies the target

- **Purpose**: the second terminus invocation on the same run (the idempotency-heal leg).
- **Steps**: in `src/specify_cli/cli/commands/consolidate.py::_run_real_merge`, pass
  `destination_ref=resolved_target_branch` to `run_retrospective_postcondition`.
- **Files**: `src/specify_cli/cli/commands/consolidate.py`.
- **Notes**: `resolved_target_branch` is already the parameter that was handed to
  `_run_lane_based_consolidation` as `target_override`.

### Subtask T007 – The recovery command names the target

- **Purpose**: an operator who hits the refusal must be able to heal it by copy-paste, including
  for Missions consolidated before this fix.
- **Steps**: thread `destination_ref` through `_rerun_command` / `_recovery_guidance` /
  `_commit_captured_retrospective`'s warning so the printed command is
  `spec-kitty mission close --mission <slug> --target <branch>` when a destination was supplied,
  and unchanged when it was not.
- **Files**: `src/specify_cli/post_merge/retrospective_terminus.py`.
- **Notes**: the legacy-mission branch of `_recovery_guidance` must also keep working; a legacy
  mission plus an explicit `--target` should still print both steps.

### Subtask T008 – `mission close --target`

- **Purpose**: make the printed recovery executable.
- **Steps**: in `src/specify_cli/cli/commands/mission_type.py`, add
  `target: Annotated[str | None, typer.Option("--target", help=...)] = None` to `close_cmd`,
  document it in the command docstring (it aims the retrospective bookkeeping commit at the
  branch the Mission was consolidated into; omitted = resolved from `meta.json`), and forward it
  to `_teardown_coordination_worktree` → `teardown_coordination_topology(destination_ref=target)`
  on **both** the close and the `--discard` legs (the discard leg keeps
  `provenance_kind="runtime_abandoned"` unchanged).
- **Files**: `src/specify_cli/cli/commands/mission_type.py`.
- **Notes**: keep the option name `--target` to match `consolidate --target`; do not add a short
  alias (`-t` is not used elsewhere on this command and aliases here have bitten before — #4724).

### Subtask T009 – Pin the CLI wiring

- **Purpose**: prove the option reaches the seam (helper-only tests cannot see a wiring gap).
- **Steps**: create `tests/specify_cli/cli/commands/test_mission_close_target.py` using
  `typer.testing.CliRunner` against the real `mission` app (see
  `tests/specify_cli/cli/commands/test_mission_close_guard.py` for the app import idiom). Assert
  (a) `mission close --mission <slug> --target topic-landing` reaches the persist leg with
  `destination_ref == "topic-landing"`, and (b) the same invocation without `--target` reaches it
  with `destination_ref is None` — the same-fixture positive/negative pair (FR-007).
- **Files**: `tests/specify_cli/cli/commands/test_mission_close_target.py` (new).
- **Notes**: patch at the seam (`specify_cli.coordination.teardown.teardown_coordination_topology`
  as imported by `mission_type`) rather than mocking git. A minimal project scaffold
  (`.kittify/`, `kitty-specs/<slug>/meta.json` with a merged baseline) is enough; check
  `is_mission_merged`'s precondition before writing the fixture.

### Subtask T010 – Regenerate the CLI reference

- **Purpose**: `docs/api/cli-commands.md` documents `mission close`'s options and a gate checks
  freshness.
- **Steps**: `uv run python -m scripts.docs.check_docs_freshness --ci` → expect the `mission
  close` section to be stale; then `uv run python -m scripts.docs.build_cli_reference`; confirm
  `git diff docs/api/cli-commands.md` is confined to the `mission close` section (add the
  `--target` row, keep every other section byte-identical); re-run the freshness check (errors=0).
- **Files**: `docs/api/cli-commands.md`.
- **Notes**: if the rebuild churns unrelated sections (other agents' concurrent CLI surface,
  shared caches), do not commit the churn — hand-apply the `--target` option row in the exact
  rendered form and verify with the freshness checker, then say so in the PR.

### Subtask T011 – Run the targeted blast radius

- **Purpose**: honest green on the changed surfaces only (no full heavy suites).
- **Steps** (record commands + counts for the PR):
  ```bash
  uv run pytest tests/specify_cli/post_merge/test_retrospective_commit_target.py -q
  uv run pytest tests/specify_cli/post_merge/test_retrospective_triggering.py \
                  tests/specify_cli/retrospective/test_merge_path_lock_timeout.py -q
  uv run pytest tests/specify_cli/coordination/test_teardown_seam_persist_before_destroy.py -q
  uv run pytest tests/consolidation/test_merge_state_authority.py \
                  tests/consolidation/test_coord_teardown_order_3926.py -q
  uv run pytest tests/specify_cli/cli/commands/test_mission_close_target.py \
                  tests/specify_cli/cli/commands/test_mission_close_guard.py -q
  uv run pytest tests/architectural/test_no_write_side_rederivation.py \
                  tests/architectural/test_guard_capability_call_sites.py \
                  tests/architectural/test_no_legacy_terminology.py -q
  uv run ruff check <changed files>
  uv run ruff format --check --force-exclude <changed files>
  uv run mypy <changed files>
  ```
- **Notes**: attribute any red honestly (stale venv → `uv sync --frozen --all-extras`, then
  retry). Never skip/xfail a gate.

## Test Strategy

Mandatory tests, all in this PR:

- `tests/specify_cli/post_merge/test_retrospective_commit_target.py` — the defect and its
  negative control (real git, no mocked commits).
- `tests/specify_cli/cli/commands/test_mission_close_target.py` — the recovery wiring.

Both must fail on the pre-fix tree. Capture the red output in the transcript / progress notes.

## Risks & Mitigations

- **Guard accidentally relaxed**: the same-fixture negative control (no `destination_ref` → still
  refused) turns that into a test failure.
- **A caller missed**: the teardown leg, the second-terminus-call leg and the CLI are each pinned by a
  test; if you find a fourth terminus caller, thread it too and say so in the PR.
- **Unrelated behaviour change in `mission close --discard`**: keep `provenance_kind` untouched
  and prefer adding no other argument plumbing to `_discard_mission` than the destination.
- **Docs churn**: see T010's note; a confined, verified regeneration beats a churning full one.

## Review Guidance

- Confirm `git diff` touches no `safe_commit`, `commit_guard` or capability constant.
- Confirm every new parameter is keyword-only with a `None` default, and that `None` paths are
  byte-identical to the previous behaviour.
- Confirm no new HEAD/branch read was introduced (`test_no_write_side_rederivation.py` green with
  no new allow-list entry).
- Confirm the red-first evidence exists: the new test module fails on `main`'s code and passes on
  the branch.
- Confirm the recovery command in the warning is literally executable and carries `--target` only
  when a destination was supplied.

## Progress & Status

Record subtask completion with:

```bash
spec-kitty agent tasks mark-status T001 --status done --mission terminus-retrospective-commit-target-01M6P3E4
```

and append approach/decisions/tooling-friction notes with
`spec-kitty agent tracer-append --mission terminus-retrospective-commit-target-01M6P3E4 --category <approach|design-decisions|tooling-friction> --entry "<text>"`.
