---
work_package_id: WP06
title: Workflow rename, documentation and changelog
dependencies:
- WP03
- WP04
requirement_refs:
- FR-023
planning_base_branch: issue-5559-shared-collection-and-shard-recapture
merge_target_branch: issue-5559-shared-collection-and-shard-recapture
branch_strategy: Planning artifacts for this mission were generated on issue-5559-shared-collection-and-shard-recapture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5559-shared-collection-and-shard-recapture unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-shared-collection-and-shard-recapture-01M42V58
base_commit: bf9c12748747dc88011495b633d0d7e11798e613
created_at: '2026-10-04T09:06:16.408649+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
phase: Phase 3 - Close-out
history:
- at: '2026-10-04T07:27:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/development/
create_intent:
- .github/workflows/ci-shard-recapture.yml
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-shard-recapture.yml
- docs/development/reference/ci-gate-mechanics.md
- docs/development/testing/testing-parallel.md
- docs/development/how-to/pr-landing.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Workflow rename, documentation and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
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

The recapture workflow's file name says what it does, every live reference follows it, and the references describe the shipped behaviour of the stored collection and the all-module recapture.

Done when the gate files under "Test Strategy" pass. Requirement: FR-023.

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
- This package runs after WP03 and WP04 are approved and **before WP05**, so that WP05's measured capture is the last thing to change test counts. One-line edits in files other packages own are expected (WP05 has not started on its files yet). Record each in the Activity Log with a one-line rationale.
- References to the old workflow name outside mission archives (research B-08): `tests/architectural/_gate_coverage.py:138` (`WORKFLOW_FILES`), `tests/architectural/test_no_duplicate_suite_execution.py:176` (`NON_CHANGE_TRIGGERED_WORKFLOWS`; `:852` pins the set), `tests/architectural/test_module_length_agreement.py:53,169` (names the workflow file), `tests/ci/test_recapture_shard_timings.py` (job key and path pins), `docs/development/how-to/pr-landing.md:618-625`, `docs/changelog/CHANGELOG.md:348` (a past entry: leave past entries as written), the workflow's own header comments.
- **Never edit** `tests/docs/fixtures/changelog_unreleased_{pre,post}_rewrite.md` or anything under `kitty-specs/` other than this mission's directory.
- The changelog's canonical file is `docs/changelog/CHANGELOG.md` (the root file is a symlink).
- Documentation rules: one Divio quadrant per page, an `updated:` date in front matter, plain language, no "feature" for a Mission, "primary branch (`main`)".

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; work only in the workspace path that `spec-kitty agent action implement WP06 --agent claude` prints.


## Subtasks & Detailed Guidance

### Subtask T028 – Rename the workflow and update references

- **Steps**:
  1. `git mv .github/workflows/ci-charter-shard-recapture.yml .github/workflows/ci-shard-recapture.yml`. Update its `name:`, the job key (`recapture-charter-shard-timings` → `recapture-shard-timings`), the concurrency group and the header comments. Keep the secret name and the primary-branch gate.
  2. Update `WORKFLOW_FILES` and `NON_CHANGE_TRIGGERED_WORKFLOWS` and the pinned set at `test_no_duplicate_suite_execution.py:852`.
  3. Update the job-key and path pins in `tests/ci/test_recapture_shard_timings.py`, and the proposal branch name if the script still says `ci/recapture-charter-shard-timings` (rename to `ci/recapture-shard-timings` in script, test and workflow together).
  4. `git grep -n "ci-charter-shard-recapture\|recapture-charter-shard-timings\|recapture_charter_shard_timings" -- . ':!kitty-specs' ':!tests/docs/fixtures' ':!docs/changelog'` must return nothing.
- **Notes**: if an open recapture pull request exists on the old branch name it is orphaned by the rename; say so in your hand-back so the operator can close it.

### Subtask T029 – Pinning inventory and workflow-set gates

- **Steps**: run `uv run --no-sync pytest tests/release/test_pinning_inventory_fresh.py -q`; if stale, regenerate with `scripts/ci/derive_pinning_inventory.py` using the command the test's failure message gives, and commit the regenerated file with the rename. Then run the gate files under "Test Strategy".

### Subtask T030 – CI references

- **Steps**:
  1. `docs/development/reference/ci-gate-mechanics.md`: add a section on the stored test-universe collection: what it is, the key (committed tree plus environment), when it is bypassed (dirty checkout, patched root), the reuse report line and the post-test check that fails on a silent fallback, the nightly equivalence job, and how to run each command locally. State plainly that a first run still collects once per consuming job.
  2. `docs/development/testing/testing-parallel.md`: where it describes collection cost or the battery, link to that section and correct any statement the mission made false.
  3. Describe the all-module scheduled recapture: drift detection by count, per-module isolation, time budget and deferral, proposal refresh, the valid-capture rule, and the accepted red window between drift and merge of the proposal.
  4. Bump `updated:` in each edited page.

### Subtask T031 – PR-landing how-to and changelog

- **Steps**:
  1. `docs/development/how-to/pr-landing.md:618-625`: replace the charter-only recapture guidance with the all-module behaviour and the new names.
  2. `docs/changelog/CHANGELOG.md`, under `[Unreleased]`: one entry per user-visible change, bold impact-first lead with the issue reference, then before → after. Three entries: the stored collection and pre-test step (#5559); every module on measured shard timings with the allowlist removed (#5561); the scheduled recapture covering all modules, including the explicit rejected-push message (#5536). The second entry describes work WP05 completes after this package; write it as the mission's outcome and the orchestrator confirms the wording once WP05 is approved. Use US spelling (the docs spelling gate flags UK spellings in changelog-touching changes).

### Subtask T032 – Docs gates

- **Steps**: run the commands under "Test Strategy". If a page was added (none is planned), regenerate the retrieval index with `scripts/docs/docs_index.py --write`.

## Test Strategy

```bash
uv run --no-sync pytest tests/architectural/test_no_duplicate_suite_execution.py tests/ci/test_recapture_shard_timings.py tests/release/test_pinning_inventory_fresh.py tests/ci/test_fork_guard.py -q
uv run --no-sync pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --no-sync python scripts/docs/check_docs_freshness.py --ci
uv run --no-sync python -m scripts.docs.check_spelling
uv run --no-sync ruff format --check --force-exclude tests/ci/test_recapture_shard_timings.py tests/architectural/test_no_duplicate_suite_execution.py
```

## Risks & Mitigations

- `_gate_coverage.py` is on the ruff-format exclude ratchet: edit the one line by hand, never reformat.
- A scheduled workflow renamed on a topic branch does not run until merged; its cron history starts fresh. Acceptable.

## Review Guidance

- Run the `git grep` in T028 and confirm it is empty.
- Read the new documentation section against the code: every stated behaviour must exist.
- Confirm past changelog entries and test fixtures are untouched.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T07:27:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
