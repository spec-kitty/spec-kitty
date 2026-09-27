---
work_package_id: WP02
title: Render recorded feedback into the regenerated prompt — loudly, on both topologies
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
planning_base_branch: issue-4899-review-feedback-to-implementer
merge_target_branch: issue-4899-review-feedback-to-implementer
branch_strategy: Planning artifacts for this mission were generated on issue-4899-review-feedback-to-implementer. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4899-review-feedback-to-implementer unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-review-feedback-to-implementer-01M3GKZ8
base_commit: 886acce5efbec8bfcdea6d1d8fa64b5250cfd5b1
created_at: '2026-09-27T07:47:57.588856+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 2 - Render side
history:
- at: '2026-09-27T05:48:09Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: src/specify_cli/cli/commands/agent/workflow_executor.py
create_intent:
- tests/agent/test_build_implement_prompt_lines.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/agent/workflow_cores.py
- tests/agent/test_workflow_review_cycle_pointer.py
- tests/agent/test_build_implement_prompt_lines.py
role: ''
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Render recorded feedback into the regenerated prompt — loudly, on both topologies

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any
user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `{{agent_profile}}`
- **Role**: `{{role}}`
- **Agent/tool**: `{{agent}}`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` (`implement`) and `authoritative_surface`
(`src/specify_cli/cli/commands/agent/workflow_executor.py`).

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks: ```python`, ```bash`.

---

## Objectives & Success Criteria

This WP fixes the **render side (#5024)** of the broken loop. Once feedback is durably recorded (WP01),
the implementer must actually see it. Two independent render defects exist: (a) a fix-mode
prompt-generation failure falls through to a feedback-less full prompt with only a `logger.warning` the
implementer never sees; and (b) on a coordination topology the render reads the event log from the
wrong partition, so the resolvable reference is never found.

**Done when:**

- **SC-003 / FR-006** — A fix-mode prompt-generation failure surfaces a visible warning (on the surface
  the implementer reads) in 100% of failure cases and NEVER silently substitutes a feedback-less prompt.
  Paired with a success-path positive control that renders feedback.
- **SC-004 / FR-007** — Recorded rejection feedback renders into the regenerated fix-mode prompt on BOTH
  single-branch AND coordination-topology missions.
- **SC-005 / FR-005** — One continuous end-to-end flow (reviewer's specific feedback → reject onto the
  re-implement edge with **no pre-seeding** → same text present in the regenerated prompt) passes on
  both topologies. It must NOT be satisfiable by a fixture that pre-seeds the record and bypasses the
  write edge.
- **NFR-001** — The synthetic-marker / resolvable-pointer grammar (`review/cycle.py`) is reused
  UNCHANGED.
- **NFR-002** — Every defect scenario is committed RED before its fix and green after.
- Complexity: no touched function exceeds C901/S3776 ≤15; `ruff`, `ruff format --check`, `mypy` clean
  with zero new suppressions.

## Context & Constraints

- Charter: `.kittify/charter/charter.md`. Mission docs: `plan.md` (§"Architecture: the render-guard
  change" + §"F4 finding"), `spec.md` (US2), `data-model.md` (read-path partition model),
  `contracts/render-feedback-contract.md` (**FROZEN**).
- **FROZEN dependencies consumed (do NOT modify — NFR-001)**:
  `is_review_rejection_edge(old_lane, target_lane) -> bool` (from WP01), the emitted resolvable
  `review-cycle://…` pointer shape, and the grammar predicates in `review/cycle.py`
  (`is_non_resolvable_review_ref`, `is_synthetic_review_ref`, `SYNTHETIC_REVIEW_REF_PREFIXES`,
  `synthetic_review_ref`) + `ReviewCycleArtifact` (`review/artifacts.py`) + `generate_fix_prompt`
  (`review/fix_prompt.py`). These are NOT in this WP's `owned_files`.
- **F4 = INDEPENDENT-RED**: the coord render defect is NOT a downstream consequence of the write-side
  loss; given a resolvable record already present, the render still fails on coord because the event-log
  read is mis-partitioned. T008 must PROVE this red on a real coord fixture. (If — contrary to the plan
  — that fixture comes back green given a record present, reclassify the coord half to a
  parity/non-regression assertion and note it.)
- **Terminology**: "Mission" not "feature"; no `feature*` aliases.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated automatically by finalize-tasks. Do NOT change manually. Prepare the execution workspace
> with `spec-kitty implement WP02` (allocates the per-lane worktree from `lanes.json`); consume the
> resolved workspace path, do NOT reconstruct it. **WP02 depends on WP01** — its dependencies must be
> `approved`/`done` before it can be claimed.

## Subtasks & Detailed Guidance

### Subtask T008 – Red-first: coord SC-004 + end-to-end SC-005 anti-mask scenarios

- **Purpose**: ATDD safety net (NFR-002) proving both the coord render defect and the end-to-end
  coupling. Commit RED before implementation.
- **Steps**:
  1. In `tests/agent/test_workflow_review_cycle_pointer.py` add **SC-004 (coord half)** — a real
     coordination-topology fixture with a durable resolvable feedback record ALREADY present on the
     COORD partition; assert on the RESOLVED FEEDBACK FILE CONTENTS (the actual feedback text rendered
     into the prompt), NOT merely that a `review_ref` string was found — otherwise the T010 split-read
     collision (pointer resolved against the wrong tree → file `None`) would pass the test vacuously.
     Prove it currently FAILS to surface the feedback text (independent-red), and passes after T010.
  2. Add **SC-005** — a no-pre-seed end-to-end flow: a reviewer enters a specific feedback text and
     rejects an in-review WP onto the `in_review → in_progress` edge (exercising the WP01 write path),
     then regenerate the fix-mode prompt and assert that exact text appears — on BOTH single-branch and
     coordination topologies. Must NOT pre-seed the record.
- **Files**: `tests/agent/test_workflow_review_cycle_pointer.py`.
- **Notes**: SC-005 is the anti-mask control — it fails if any write-side gate (WP01) or the render path
  is left unfixed. Because it depends on WP01's resolvable record, run it after WP01 lands.

### Subtask T009 – Visible fall-through warning on fix-mode generation failure

- **Purpose**: FR-006 — a generation failure must be visible, not silent.
- **Steps**: In `implement_try_render_fix_mode_prompt` (`workflow_executor.py:1084`), the `except` at
  `:1161-1162` currently emits only `logger.warning(...)` then `return None`. Change it to emit an
  operator-VISIBLE warning on the surface the implementer reads (e.g.
  `console.print("[bold red]⚠️ …[/bold red]")`) naming the WP and the cause, then `return None`. The
  full prompt remains a legitimate — now announced — fallback; it must NOT silently substitute a
  feedback-less prompt. Keep concrete recovery logic in the block (no effect-free handler — Sonar).
- **Files**: `src/specify_cli/cli/commands/agent/workflow_executor.py`.

### Subtask T010 – STATUS_STATE render event-log re-route — SPLIT read (dual-topology)

- **Purpose**: FR-007 / SC-004 — make coord and single-branch render identically **without** masking the
  coord defect by mis-resolving the feedback artifact.
- **⚠️ CRITICAL — this is a SPLIT, not a whole-function feature_dir swap.** `latest_review_feedback_reference`
  (`workflow_cores.py:311`) and `has_prior_rejection` (`workflow_cores.py:394`) each do TWO reads off the
  same `feature_dir`:
  1. the **event-log read** — `read_wp_events(feature_dir, wp_id)` (`workflow_cores.py:328`) → `status.events.jsonl`
     → this is a `STATUS_STATE` kind → **MUST move to the coord partition**; and
  2. the **review-cycle ARTIFACT pointer resolution** — `review_feedback_root(feature_dir)`
     (`workflow_cores.py:327`, = `feature_dir.parent.parent`) + `resolve_review_feedback_pointer(feedback_root, review_ref)`
     (`workflow_cores.py:336`), and `_review_cycle_wp_dir` in `has_prior_rejection` → this is a
     `WORK_PACKAGE_TASK` kind → **MUST stay on PRIMARY**.

  Naively swapping the function's single `feature_dir` to the coord dir would move BOTH reads and resolve
  the pointer against the coord tree → the feedback file comes back `None` → **SC-004 silently still-broken**
  (coord-mask regression). Only the event-log read moves.
- **Steps**:
  - `implement_resolve_feedback_and_gate` (`workflow_executor.py:667`) currently passes a
    `read_dir(WORK_PACKAGE_TASK)` dir (PRIMARY) to `resolve_review_feedback_context`, but
    `status.events.jsonl` is a `STATUS_STATE` kind (COORD on coord topologies).
  - Route ONLY the event-log read (`read_wp_events` inside `latest_review_feedback_reference` and
    `has_prior_rejection`, and the event read behind `resolve_review_feedback_context` `workflow_cores.py:340`)
    through `placement_seam(repo_root, mission_slug).read_dir(STATUS_STATE)`, mirroring the write-side
    `_resolve_verdict_read_feature_dir` (`tasks_verdict_persistence.py:694`). Thread the STATUS_STATE dir in
    as a distinct argument; do NOT replace the whole `feature_dir`.
  - Keep `review_feedback_root` / `resolve_review_feedback_pointer` (`workflow_cores.py:327,336`) and
    `_review_cycle_wp_dir` reading from the PRIMARY `WORK_PACKAGE_TASK` `feature_dir` — **unchanged**.
- **Files**: `src/specify_cli/cli/commands/agent/workflow_executor.py`,
  `src/specify_cli/cli/commands/agent/workflow_cores.py`.
- **Notes**: Single-branch collapses PRIMARY == COORD == `repo_root`, so the re-route is a no-op there.
  T008's coord fixture must assert the RESOLVED FEEDBACK FILE CONTENTS (not just a `review_ref` string) so
  a pointer-mis-resolution cannot pass the test vacuously.

### Subtask T011 [P] – New `build_implement_prompt_lines` test

- **Purpose**: FR-005 positive control (SC-003 success path + SC-005 render assertion).
  `build_implement_prompt_lines` (`workflow_executor.py:1302`) currently has NO test.
- **Steps**: Create `tests/agent/test_build_implement_prompt_lines.py` covering: (a) feedback-present →
  the feedback text appears in the produced lines; (b) feedback-absent → no crash, no spurious feedback.
- **Files**: `tests/agent/test_build_implement_prompt_lines.py` (**NEW** — see `create_intent`).
- **Parallel?**: Yes — an isolated pure-function test independent of T009/T010.

### Subtask T012 – Single-branch non-regression assertion

- **Purpose**: Prove the `STATUS_STATE` re-route does not break single-branch rendering.
- **Steps**: Assert that on a single-branch mission (PRIMARY == COORD == `repo_root`) the re-route is a
  no-op and feedback still renders — part of SC-004/SC-005's dual-topology coverage.
- **Files**: `tests/agent/test_workflow_review_cycle_pointer.py`.

### Subtask T013 – Run the WP02 validation surface, record counts

- **Purpose**: Charter Testing Requirements — run your blast radius and record it.
- **Steps**: Run the Test Strategy commands below; record exact commands + passed/failed counts in the
  PR *Tests run* section. Classify any pre-existing baseline reds per the CLAUDE.md gotcha.

## Test Strategy (required)

```bash
make test-fast
.venv/bin/python -m pytest tests/agent/test_workflow_review_cycle_pointer.py -q
.venv/bin/python -m pytest tests/agent/test_build_implement_prompt_lines.py -q
# blast radius for the two owned workflow modules:
.venv/bin/python -m pytest tests/agent/ -q
```

Also run `ruff check .`, `uv run --frozen ruff format --check .` (whole-repo format gate, #3952), and
`mypy` over the changed files. Do NOT run `make test-full` / whole-repo suites — the CI agent owns that.

## Risks & Mitigations

- **`STATUS_STATE` re-route breaking single-branch** → single-branch collapses both partitions to
  `repo_root`; T012 asserts the no-op.
- **Reading the wrong partition for the ARTIFACT** → keep the review-cycle artifact read on
  `WORK_PACKAGE_TASK`; only the event-log read moves to `STATUS_STATE`.
- **Silent handler regressions** → keep the `except` block's concrete recovery; do not reduce it to a
  bare log-only or effect-free handler.

## Review Guidance

- Verify the fall-through warning is genuinely visible on the implementer's surface (console), not
  log-only, and that no feedback-less prompt is silently substituted.
- Verify SC-005 is a real no-pre-seed end-to-end flow exercising WP01's write edge — not a pre-seeded
  fixture that bypasses it.
- Verify the coord render passes AND single-branch is unregressed (both topologies).
- Confirm `review/cycle.py` grammar is unchanged (NFR-001).
- Confirm the #5024 issue-matrix row exists (approval gate).

## Activity Log

> **CRITICAL**: entries MUST be in chronological order (oldest first, newest last). Append at the END.

- 2026-09-27T05:48:09Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP02 --to <status>`
to change WP status.
