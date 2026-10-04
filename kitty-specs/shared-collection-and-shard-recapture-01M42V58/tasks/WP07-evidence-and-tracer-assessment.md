---
work_package_id: WP07
title: Evidence and tracer assessment
dependencies:
- WP05
requirement_refs:
- FR-022
- SC-001
- SC-002
planning_base_branch: issue-5559-shared-collection-and-shard-recapture
merge_target_branch: issue-5559-shared-collection-and-shard-recapture
branch_strategy: Planning artifacts for this mission were generated on issue-5559-shared-collection-and-shard-recapture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5559-shared-collection-and-shard-recapture unless the human explicitly redirects the landing branch.
subtasks:
- T033
- T034
- T035
phase: Phase 3 - Close-out
history:
- at: '2026-10-04T07:27:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/
create_intent:
- kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/local-measurements.md
- kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/publish-failure-classification.md
- kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/ci-measurements.md
execution_mode: planning_artifact
model: claude-sonnet-5-5
owned_files:
- kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/local-measurements.md
- kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/publish-failure-classification.md
- kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/ci-measurements.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Evidence and tracer assessment

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

The mission's result is stated from measurement, never from expectation. Three evidence files exist; every value in them was observed, and every value not yet observable is marked `pending`.

Requirement: FR-022 (SC-001 and SC-002 are completed after the pull request's first three CI runs).

## Context & Constraints

- Mission documents: `kitty-specs/shared-collection-and-shard-recapture-01M42V58/spec.md`, `plan.md`, `research.md` (decisions D-01..D-15, brownfield findings B-01..B-09), `data-model.md`, `contracts/`, `quickstart.md`.
- Charter: `.kittify/charter/charter.md`. Load action doctrine with `spec-kitty charter context --action implement`.
- **ATDD-first (binding)**: the failing test is committed before the implementation, as its own commit.
- **No heavy suites**: run only the files named under "Test Strategy". Never run `tests/architectural/` or `tests/ci/` as a whole directory, `make test-fast` or `make test-full`.
- Run tools as `uv run --no-sync <cmd>` (a bare `uv run` rewrites `uv.lock` on this machine; if `uv.lock` shows as modified, `git checkout uv.lock`).
- Formatting: check with `uv run --no-sync ruff format --check --force-exclude <files>`; never format a file on the ruff-format exclude list by explicit path without `--force-exclude`.
- Complexity ceiling is 15 per function. No `# noqa`, no `# type: ignore`, no new allowlist or baseline entry (C-006).
- Use `kernel.clock` for timestamps in `scripts/` (clock-door gate); in tests use `monkeypatch`, never direct `os.environ` / `sys.argv` / cwd mutation (global-state gate).
- Terminology: "Mission" (never "feature"), "primary branch (`main`)", "repository root checkout".
- Tracer notes: the mission's tracer files live on the coordination branch, not in your lane. Put any tooling friction or design choice in your final hand-back under a heading `Tracer notes`; the orchestrator records them.
- Write for a maintainer who was not part of the mission. Plain language, tables for numbers, a short conclusion per file.
- Do not invent or estimate a number. A missing measurement is written as `pending`, with what has to happen to obtain it.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; work only in the workspace path that `spec-kitty agent action implement WP07 --agent claude` prints.


## Subtasks & Detailed Guidance

### Subtask T033 – Local measurements

- **File**: `evidence/local-measurements.md`.
- **Content**:
  1. Reuse: on a clean checkout, the output of `collect` twice (outcome, seconds), `check`, and `compare` (difference count), with the interpreter and machine named. Commands are in `quickstart.md`.
  2. Key computation time (NFR-004).
  3. Capture record from WP05: per module, old count, new count, exit status, wall time; total serial capture time; shard-count changes with skew before and after.
  4. Strict-mode agreement result at the capture commit (NFR-006).

### Subtask T034 – Publish-failure classification

- **File**: `evidence/publish-failure-classification.md`.
- **Content**: the failing runs (37182764995, 37097776055), the exact error line, the classification (credential without repository write access; not a code defect), what the mission changed (explicit message naming the permission and the secret), and the operator action still required. Add the time-cap observation (three runs at 30m19–21s against a 30-minute cap) and how the budget addresses it.

### Subtask T035 – Tracer assessment and CI-measurement template

- **Steps**:
  1. Read the three tracer files on the coordination branch. Summarise the most significant friction and decisions in five to ten lines at the end of `evidence/local-measurements.md`, and list any tooling-friction item that should become a tracker issue (for the operator to decide; do not file issues).
  2. Create `evidence/ci-measurements.md` with a table for three per-PR runs: run id, per consuming job the pre-test step outcome and duration, the report lines of each collecting test, the slowest collecting test's setup time, and the `check` verdict. Every cell starts as `pending`. State under the table which requirement each column proves (NFR-001, NFR-002, NFR-003).

## Risks & Mitigations

- Writing the CI table before the runs exist invites filling it from expectation. The template says `pending` and the orchestrator fills it from the job summaries after the pull request is open.

## Review Guidance

- Spot-check three numbers against their source output.
- Confirm no cell holds an estimate presented as a measurement.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T07:27:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
