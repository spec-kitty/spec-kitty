---
work_package_id: WP01
title: Retire the consumed draft at the durable-write seam
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6632-review-feedback-draft-retirement
merge_target_branch: issue-6632-review-feedback-draft-retirement
branch_strategy: Planning artifacts for this mission were generated on issue-6632-review-feedback-draft-retirement. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6632-review-feedback-draft-retirement unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-review-feedback-draft-retirement-01M66YR3
base_commit: c8fb16dc250a1029f1b25c4e51d65b804f311104
created_at: '2026-10-30T17:53:46.927640+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Retirement seam
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/specify_cli/cli/commands/agent/test_review_feedback_draft_retirement.py
- tests/specify_cli/review/test_cycle_feedback_draft_retirement.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/cycle.py
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- tests/specify_cli/cli/commands/agent/test_review_feedback_draft_retirement.py
- tests/specify_cli/review/test_cycle_feedback_draft_retirement.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6632'
---

# Work Package Prompt: WP01 – Retire the consumed draft at the durable-write seam

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting, and
address every item before declaring the work done.

## Objectives & Success Criteria

Fix spec-kitty/spec-kitty#6632: a review rejection currently writes `review-cycle-N.md`, commits that
one file, and leaves the reviewer's advertised `review-feedback-N.md` untracked in the mission
directory, so the work package's next `move-task --to for_review` refuses on the tool's own output.

Deliver, in this commit order (ATDD-First Discipline, C-011):

1. **First commit — the red regression.** A test module that drives the real CLI: rejection →
   `move-task --to for_review`, with the planning-artifact gate **not** stubbed. It fails on the
   planning base naming the leftover file.
2. **Then the fix** — retire the draft after the record's commit is verified durable, under the five
   predicates.
3. **Then the unit tests** for the predicates, and the half-by-half revert proof.

Success criteria:

- **SC-001**: both commands exit 0 and `git status --porcelain kitty-specs/<mission>/` is empty after
  the rejection.
- **SC-002**: each kept-draft case (non-durable record, tracked draft, out-of-mission draft, draft
  edited after it was recorded) keeps the file, on the same fixture.
- **SC-003**: `review-cycle-1.md` still contains the reviewer's text verbatim.

## Context & Constraints

- Spec: `kitty-specs/review-feedback-draft-retirement-01M66YR3/spec.md` (US1, US2, edge cases)
- Plan: `.../plan.md` — IC-01 and "Design: the retirement predicate"
- Data model: `.../data-model.md` — the transition table **is** the specification of this code
- Reproduction: `.../research/repro-6632.py` + `.txt` — the exact fixture shape and refusal text
- Existing code:
  - `src/specify_cli/review/cycle.py` — `create_rejected_review_cycle`, `_resolve_review_body`,
    `_commit_review_cycle_artifact` (the durability proof), `CreatedRejectedReviewCycle`,
    `review_feedback_source_path`
  - `src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py` —
    `persist_rejected_review_cycle_for_rollback`, `_warn_feedback_file_not_recorded` (stderr idiom)
  - `src/kernel/git/listing.py` — `is_tracked(cwd, path)`
- Constraints: `mypy --strict` clean; no new dependency; **never** `git add`/commit the draft (C-001);
  the recorded artifact bytes must not change (C-002); the typed feedback-file errors keep their
  wording (C-003).

**Do not stub the gate under test.** `tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py`
stubs `_validate_ready_for_review`, which is precisely why this defect was invisible to the suite.

## Branch Strategy

- **Strategy**: branch strategy is set by `finalize-tasks` from `lanes.json`; this WP runs in its
  allocated lane worktree.
- **Planning base branch**: `issue-6632-review-feedback-draft-retirement`
- **Merge target branch**: `issue-6632-review-feedback-draft-retirement`

## Subtasks & Detailed Guidance

### Subtask T001 – End-to-end fixture harness

- **Purpose**: one fixture that builds the mission shape the reproduction used, shared by every case.
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/agent/test_review_feedback_draft_retirement.py` with
     `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.
  2. Fixture: `git init -b main`; `.kittify/config.yaml` with `auto_commit: true` and
     `protection: {protected_branches: []}`; `kitty-specs/<mission>/meta.json` with a ULID
     `mission_id`/`mid8`; `lanes.json` via `write_lanes_json` **with** `planning_commit_sha` set to
     the seed commit; a `WP01-core.md` task file with `owned_files: ["src/**"]`; a seed commit; then
     `tests.lane_test_utils.commit_lane_implementation(repo, feature_dir)` so the evidence window is
     computable.
  3. Seed the event log with `tests._support.status_seed.seed_status_event`:
     genesis → planned → claimed → in_progress → for_review → in_review.
  4. Return `(repo, feature_dir, sub_artifact_dir)`; `monkeypatch.chdir(repo)`; patch
     `tasks_module.locate_project_root` and `tasks_module.get_mission_type` only (environment shims,
     **not** the gate under test).
- **Notes**: run the rejection with `--agent reviewer` and the later `--to for_review` with the same
  `--agent` — an agent mismatch refuses before the gate and would make the test vacuous.

### Subtask T002 – Red: clean tree, next move passes

- **Purpose**: SC-001, the reported defect. First commit of the lane.
- **Steps**:
  1. Write the draft at the path `specify_cli.review.cycle.review_feedback_source_path` advertises
     (call the helper; do not hand-join a string).
  2. `CliRunner().invoke(tasks_app, ["move-task", "WP01", "--to", "planned", "--review-feedback-file",
     str(draft), "--mission", MISSION, "--agent", "reviewer"])` → assert exit 0.
  3. Assert `review-cycle-1.md` exists and its text contains the reviewer's body (SC-003).
  4. Assert no `git status --porcelain kitty-specs/<mission>/` line names `review-feedback-1.md`
     (status files may appear; filter by filename).
  5. Seed `planned → claimed → in_progress`, invoke `move-task --to for_review --agent reviewer`,
     assert exit 0, and assert the output does not contain `Blocking: 1 uncommitted file(s)`.

### Subtask T003 – Red: the draft is kept when it must be

- **Purpose**: SC-002, FR-002–FR-005. Separate test functions on the shared fixture.
- **Cases**:
  1. **Not durable**: the same run with `auto_commit: false`; the draft still exists after exit 0.
  2. **Tracked**: commit the draft before the rejection; it still exists and is still tracked
     (`git ls-files --error-unmatch`), i.e. the rejection created no deletion.
  3. **Outside the mission directory**: draft at `tmp_path / "feedback.md"`; still there after a
     *durable* rejection (the same-fixture positive control is T002, where an inside draft is removed).
  4. **Edited after it was recorded**: the draft keeps its new bytes, and the run reports it.
- **Notes**: each assertion message must name the file and the predicate it guards, so a
  half-reverted fix fails readably.

### Subtask T004 – `_resolve_review_body` returns the raw source text

- **Purpose**: the retirement compares the draft's current bytes with the bytes the record was built
  from (FR-005); today only the composed body survives.
- **Steps**: return `(body, source_text)` — `source_text` is `None` on the `body=` leg; update the
  single caller in `create_rejected_review_cycle`. The docstring's behaviour contract is unchanged.
- **Notes**: `body_header` is *prepended*, so compare against the file's own text, never the composed
  body.

### Subtask T005 – The retirement seam

- **Purpose**: one owner (NFR-003) for the removal, in the module that writes the record.
- **Steps**:
  1. `_retire_consumed_feedback_source(*, feedback_source, recorded_source_text, mission_dirs) -> tuple[Path | None, str | None]`
     returning `(retired_path, warning)`.
  2. Predicates in order: exists → `resolve()`; inside one of `mission_dirs`; not tracked
     (`is_tracked`, `GitCommandError` ⇒ keep); current text == `recorded_source_text`; `unlink()` in
     `try/except OSError`.
  3. `mission_dirs`: `kitty-specs/<mission_slug>` under `main_repo_root`, under the already-computed
     `surface_root`, and under `owned.owned_root` when `owned is not None`; deduplicate.
  4. Call it only when `feedback_source is not None and persistence.verdict_durably_persisted` —
     after the `local_only` / `already_committed` / `_commit_review_cycle_artifact` branches settle
     `persistence`, before building `review_result`.
  5. Add `retired_feedback_source: Path | None = None` to `CreatedRejectedReviewCycle`; append any
     warning to its existing `warnings` tuple.
- **Notes**:
  - `sub_artifact_dir` is **not** the boundary: the reviewer may have written the draft under another
    WP's directory (spec edge case), so the boundary is the mission directory.
  - Symlinks: `resolve()` follows the link, so a link pointing outside the mission dir is kept.
  - No new git call when the path is outside the mission directories (NFR-001): check the path first.

### Subtask T006 – stderr notice for a kept draft

- **Purpose**: FR-008 — an operator must learn the file is still there.
- **Steps**: in `persist_rejected_review_cycle_for_rollback`, echo each `review_cycle.warnings` entry to
  stderr with the `typer.echo(..., err=True)` idiom `_warn_feedback_file_not_recorded` uses. JSON
  stdout is unchanged.
- **Parallel?**: yes with T007.

### Subtask T007 – Unit tests for the predicates

- **Purpose**: one test per predicate, plus the "no git repository" degradation.
- **Steps**: create `tests/specify_cli/review/test_cycle_feedback_draft_retirement.py`; call
  `_retire_consumed_feedback_source` against a `tmp_path` mission tree with a real `git init` for the
  tracked/untracked arms. Cover: removed; tracked ⇒ kept; outside ⇒ kept **and** `is_tracked` never
  called; changed bytes ⇒ kept + warning; `OSError` on unlink ⇒ kept + warning; not a git repo ⇒ kept,
  no exception.
- **Parallel?**: yes with T006.

### Subtask T008 – Half-by-half proof and tracer

- **Purpose**: prove the fix is load-bearing (acceptance-criteria-non-vacuity).
- **Steps**: revert one at a time — (a) the `verdict_durably_persisted` gate, (b) the tracked guard,
  (c) the mission-directory guard, (d) the bytes comparison — confirm a named test goes red for each,
  restore. Append the result to the mission's `design-decisions` tracer with
  `spec-kitty agent tracer-append --mission review-feedback-draft-retirement-01M66YR3 --category design-decisions --entry "<text>" --actor python-pedro`.

## Test Strategy

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_review_feedback_draft_retirement.py \
  tests/specify_cli/review/test_cycle_feedback_draft_retirement.py -q
uv run pytest tests/specify_cli/review/ -q -k "cycle or feedback"
uv run pytest tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py \
  tests/specify_cli/cli/commands/agent/test_move_task_durability.py \
  tests/integration/test_review_cycle_rejection_only.py -q
uv run mypy src/specify_cli/review/cycle.py src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
```

## Risks & Mitigations

- **Deleting the only copy** → predicates 1–4, each with a unit test; the record's body is read back
  from git before anything is removed.
- **A rejection now fails because the unlink raised** → caught, becomes a warning (NFR-002), tested.
- **Coord topology** → `surface_root` and `main_repo_root` both contribute candidates, so the draft in
  the repository root checkout is found even though the record lives in the coordination worktree.
- **Fixture fights the evidence-window gate** → copy the fixture recipe from
  `research/repro-6632.py`, which is known to reach the gate.
- **`mypy --strict`** → annotate the helper and the new dataclass field.

## Review Guidance

- Re-derive the five predicates from `data-model.md` and check each has a test.
- Confirm the retirement happens **after** the durability branch, never before.
- Confirm no `git add`/commit of the draft anywhere in the diff, and that the recorded artifact bytes
  are untouched (the `_resolve_review_body` change is return-shape only).
- Confirm the end-to-end test does not stub the planning-artifact gate.

## Progress & Status

- Record progress with `spec-kitty agent tasks add-history WP01 --note "<what you did>"`.
- Change status with `spec-kitty agent tasks move-task WP01 --to <lane>`.
