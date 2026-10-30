---
work_package_id: WP01
title: Bound the preserved failures in the staging lifecycle
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- C-005
planning_base_branch: issue-6723-bound-failed-staging-retention
merge_target_branch: issue-6723-bound-failed-staging-retention
branch_strategy: Planning artifacts for this mission were generated on issue-6723-bound-failed-staging-retention. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6723-bound-failed-staging-retention unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-bound-failed-staging-retention-01M66YPB
base_commit: 6f18be7624d243b9d98a4d000ae820ec5bea2af1
created_at: '2026-10-30T17:51:07.801594+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Retention bound
history:
- at: '2026-10-30T17:49:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent:
- tests/charter/synthesizer/test_staging_retention_6723.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/staging.py
- src/specify_cli/cli/commands/charter/synthesize.py
- tests/charter/synthesizer/test_staging_retention_6723.py
- docs/context/governance-files.md
- docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Bound the preserved failures in the staging lifecycle

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
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."` (stored in the status event log).

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

A refused `spec-kitty charter synthesize` (or `charter resynthesize`) preserves
its staging directory as `.kittify/charter/.staging/<run_id>.failed/` for
diagnosis. Today nothing prunes those directories, so a repeatedly-refused
project accumulates one per attempt (#6723: #4226 counted 15, then 16, on one
repository). This work package bounds them.

Done when:

- After any refusal, at most **3** `.failed` directories remain under
  `.kittify/charter/.staging/` (`DEFAULT_KEEP_FAILED_RUNS`).
- The directory the current command just preserved is never removed and its
  `cause.yaml` is intact after the command exits.
- A tree that already holds more than 3 is reduced to 3 by the next refusal.
- A live (non-`.failed`) staging directory, and any other entry under
  `.staging/`, is never removed.
- Removal goes through `PathGuard.rmtree`; no allowlist change, no unguarded
  deletion.
- Listing/removal errors never replace the synthesis failure; the command still
  reports the real refusal and exits non-zero.
- The refusal hint and the docs state the bound, sourced from the same constant.

## Context & Constraints

- Spec: `kitty-specs/bound-failed-staging-retention-01M66YPB/spec.md`
  (FR-001..FR-009, NFR-001..NFR-004, SC-001..SC-007).
- Plan: `kitty-specs/bound-failed-staging-retention-01M66YPB/plan.md`;
  model: `kitty-specs/bound-failed-staging-retention-01M66YPB/data-model.md`;
  validation steps: `kitty-specs/bound-failed-staging-retention-01M66YPB/quickstart.md`.
- Research: `kitty-specs/bound-failed-staging-retention-01M66YPB/research.md`
  records the reproduction and the decision to use a count bound of 3.
- Existing seam: `StagingDir` in `src/charter/activation/synthesizer/staging.py`
  owns the staging lifecycle; `PathGuard` is the declared single write seam
  (ADR `docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md`).
- Existing signal and text: `src/charter/bundle.py::_check_stale_failed_dirs`
  warns on stale `.failed` dirs (leave it as is); the refusal hint lives in
  `src/specify_cli/cli/commands/charter/synthesize.py`.
- Do not change synthesis, validation, promotion, the `cause.yaml` shape, the
  #6510 collision remedy, or `PathGuard`'s allowlist.
- No new dependency, config key, environment toggle or command.

## Branch Strategy

- **Strategy**: `issue-6723-bound-failed-staging-retention` is both the planning
  base branch and the merge target branch for this mission; execution workspaces
  are allocated per computed lane from `lanes.json`.
- **Planning base branch**: issue-6723-bound-failed-staging-retention
- **Merge target branch**: issue-6723-bound-failed-staging-retention

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Failing-first retention tests in the staging lifecycle

- **Purpose**: Prove the defect at the pre-existing lifecycle seam before the fix.
- **Steps**: Create `tests/charter/synthesizer/test_staging_retention_6723.py`
  with unit cases using the existing `_make_repo_root` pattern (a temporary root
  with `.kittify/charter/` and `.kittify/charter-packs/`):
  1. six `StagingDir.create` + `commit_to_failed` calls leave exactly 3
     `.failed` directories;
  2. the newest one exists, its `cause.yaml` decodes to the reason that run
     passed, and the six run ids are not all present;
  3. a hand-built overflow of 6 `.failed` directories is reduced to 3 by one
     more refusal;
  4. a live `.staging/<run_id>/` directory holding a file survives unchanged
     (byte content and file list) while the bound is enforced;
  5. equal modification times resolve deterministically (set the same mtime on
     several failed dirs and assert the same survivors across two passes);
  6. a removal failure (monkeypatch `PathGuard.rmtree` to raise `OSError` for one
     directory) neither raises out of `commit_to_failed` nor removes that
     directory.
- **Files**: `tests/charter/synthesizer/test_staging_retention_6723.py`
- **Parallel?**: no (must land red first).
- **Notes**: mark the module `pytest.mark.unit` like its sibling
  `test_staging_atomicity.py`. Run the file and record the RED output in the
  commit message or PR notes before touching production code.

### Subtask T002 – The real CLI refusal path is bounded too

- **Purpose**: The user-visible contract is `spec-kitty charter synthesize`
  refusing, not only the internal helper.
- **Steps**: Extend the same test file with one `pytest.mark.integration` +
  `pytest.mark.git_repo` case that reuses the "synthesized once" fixture pattern
  from `tests/charter/synthesizer/test_collision_refusal_6510.py` (module-scoped
  template + `copytree`, `charter_cwd_isolation`), loses the ownership record so
  synthesis is refused, invokes `synthesize` five times, then asserts:
  `len(list(staging.glob("*.failed"))) == 3`; the directory named in the last
  refusal output exists; its `cause.yaml` reason is the last failure's.
  If the fixture cost is unreasonable, keep the five invocations but reuse a
  single template — do not weaken the assertion to a unit-only check.
- **Files**: `tests/charter/synthesizer/test_staging_retention_6723.py`
- **Parallel?**: no.
- **Notes**: if a CLI invocation unexpectedly succeeds, fail loudly rather than
  skipping; the refusal is the scenario under test.

### Subtask T003 – Implement the bound in `StagingDir.commit_to_failed`

- **Purpose**: Make the tests green in the one place every refusing caller
  passes through.
- **Steps**:
  1. Add `DEFAULT_KEEP_FAILED_RUNS = 3` (public module constant, docstring
     explaining "latest + two prior, enough to compare a repeated refusal").
  2. Add a module-level helper, e.g.
     `retain_failed_staging_dirs(guard, staging_root, *, keep, preserve) -> tuple[Path, ...]`
     returning the removed paths: list `staging_root.iterdir()` (suppress
     `OSError`), keep directories whose name ends in `.failed`, order by
     `(st_mtime, name)` descending (suppress per-entry `OSError`), never include
     `preserve`, then `guard.rmtree(...)` each surplus (suppress `OSError`).
     No recursion into directory contents.
  3. Call it at the end of `commit_to_failed`, after the `cause.yaml` write,
     passing `self.run_id` as `preserve` and `DEFAULT_KEEP_FAILED_RUNS` as `keep`.
  4. Keep `commit_to_failed`'s "never mask the original error" contract.
- **Files**: `src/charter/activation/synthesizer/staging.py`
- **Parallel?**: no.
- **Notes**: keep complexity ≤ 15 and extract small helpers rather than nesting;
  `ruff`/`mypy` clean, no blanket suppressions. A module-level function is
  preferred over a method so the tests can call it directly for the ordering
  cases.

### Subtask T004 – State the bound in the refusal hint

- **Purpose**: The operator who just got the refusal is the person who needs to
  know earlier copies are pruned and how many are kept.
- **Steps**: In `src/specify_cli/cli/commands/charter/synthesize.py` import
  `DEFAULT_KEEP_FAILED_RUNS` from the staging module and extend the existing
  "Staging directory preserved at:" message with one short clause, e.g.
  "Older failed staging directories are pruned; the newest
  {DEFAULT_KEEP_FAILED_RUNS} are kept." Keep the message ASCII where the
  surrounding text is, and do not change exit codes or the `--json` envelope.
- **Files**: `src/specify_cli/cli/commands/charter/synthesize.py`
- **Parallel?**: after T003 (the constant must exist).
- **Notes**: if the same hint text exists in the resynthesize path, update it
  from the same constant; do not introduce a second literal.

### Subtask T005 – Update the reference docs

- **Purpose**: The docs currently imply failed directories are kept forever.
- **Steps**: In `docs/context/governance-files.md` extend the
  `.kittify/charter/.staging/` row to state the retention bound (newest 3 kept,
  older removed after the next refusal). In
  `docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md` update the
  statements that say failed dirs are "not deleted"/"preserved" so they say the
  directory is preserved and the newest 3 are retained. Do not rewrite the ADR's
  decision — annotate the retention bound where retention is described.
- **Files**: `docs/context/governance-files.md`,
  `docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md`
- **Parallel?**: yes (with T006).
- **Notes**: no new doc page, so no docs-index regeneration is required; if you
  do add a page, run `uv run python -m scripts.docs.docs_index --write` and
  `uv run python -m scripts.docs.freshen_adr_inventory` then
  `check_docs_freshness --ci`.

### Subtask T006 – Changelog entry

- **Purpose**: User-facing behaviour change under `[Unreleased]`.
- **Steps**: Add one entry to `docs/changelog/CHANGELOG.md` under `[Unreleased]`:
  bold impact-first lead with `(#6723)`, then before/after. Example shape:
  "**Refused `charter synthesize` runs no longer accumulate staging
  directories without bound** (#6723). **Before:** every refusal left a
  `.kittify/charter/.staging/<run_id>.failed/` directory and nothing pruned
  them. **After:** the newest 3 are kept …, older ones are removed …".
  Keep it under 1,200 characters; no machine-local paths.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: yes (with T005).
- **Notes**: place it with the other `[Unreleased]` entries, matching their voice.

### Subtask T007 – Run the targeted validation

- **Purpose**: Evidence for the PR's *Tests run* section.
- **Steps**: Run and record counts for:
  `uv run --frozen pytest tests/charter/synthesizer/ -q`;
  `uv run --frozen pytest tests/charter/synthesizer/test_staging_retention_6723.py -q`;
  `make test-fast`; `uv run --frozen ruff check .`;
  `uv run --frozen ruff format --check --force-exclude <changed files>`;
  `uv run --frozen mypy src/charter/activation/synthesizer/staging.py`;
  `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`.
  Classify any red against `origin/main` before touching it (AGENTS.md
  baseline-red gotcha); do not run `make test-full`.
- **Files**: none (evidence only).
- **Parallel?**: no.
- **Notes**: new-code coverage ≥ 90 % on the changed lines — the tests above must
  execute every branch of the new helper (empty list, under bound, at bound,
  over bound, unreadable entry, removal failure).

## Test Strategy

- Unit: the six cases in T001 against a temporary repo root.
- Integration: the CLI refusal case in T002 on a real "synthesized once" project.
- Positive controls: a successful synthesis (`StagingDir.wipe`) still removes its
  staging dir; `tests/charter/synthesizer/test_staging_atomicity.py` keeps
  passing unchanged.
- Commands as in T007.

## Risks & Mitigations

- **Removing the current run's directory**: impossible by construction
  (`preserve`), guarded by a test.
- **Removing a live staging directory**: filtered by the `.failed` suffix, tested.
- **Raising over the synthesis error**: all listing/removal calls suppressed,
  tested.
- **Nondeterministic survivor selection on equal mtimes**: name tiebreak, tested.
- **Doc/number drift**: docs and hint import the one constant.

## Review Guidance

- Confirm the tests were RED before the production change (commit order).
- Confirm the removal seam is `PathGuard.rmtree` and the allowlist is untouched.
- Confirm no synthesis/validation/promotion behaviour changed beyond the
  retention call, and `cause.yaml` is still `{reason, traceback, timestamp}`.
- Check the CLI hint reads from the constant, and docs state the same number.
- Check the new tests actually assert retention (not just "a directory exists")
  and that the live-directory case asserts byte content.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
