---
work_package_id: WP03
title: Pre-Merge Dispatch Evidence + Unconditional Stress-Timeout Re-Derivation
dependencies:
- WP02
requirement_refs:
- FR-002
- FR-009
- NFR-001
- NFR-002
- NFR-006
- C-001
planning_base_branch: issue-4865-ci-nightly-wallclock-budget
merge_target_branch: issue-4865-ci-nightly-wallclock-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4865-ci-nightly-wallclock-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4865-ci-nightly-wallclock-budget unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
- T019
phase: Phase 1 - Dispatch Evidence + Stage B
history:
- at: '2026-09-22T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Pre-Merge Dispatch Evidence + Unconditional Stress-Timeout Re-Derivation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: (unset — select per `spec-kitty agent profile list` if not pre-assigned)

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log.
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*None yet.*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````yaml`, ````bash`

---

## Objectives & Success Criteria

Two things, both mandatory:

1. **FR-009**: Dispatch `ci-nightly.yml` (`mode: full`) on this branch, before merge — the real,
   live evidence path neither #4865's nor #4864's acceptance criteria can be proven by a unit test
   alone.
2. **Stage B (PLAN-ARCH-001)**: UNCONDITIONALLY re-derive `stress`'s tightened, FINAL production
   `timeout-minutes` from a real COMPLETED duration this dispatch measures — Stage A's `90` from
   WP02 is NEVER itself the shipped value, regardless of whether it "happened to be enough."

Success = a recorded dispatch run URL showing three independent job conclusions
(`performance`/`e2e`/`stress`), `stress` completing to a real `success`/`failure` verdict (never
`cancelled`), confirmed xunit artifact existence, and `ci-nightly.yml`'s `stress` job carrying a
Stage-B-derived `timeout-minutes` committed separately from WP02's split commit.

## Context & Constraints

- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md` — FR-009, NFR-002, NFR-006, User
  Story 1's AC2/AC3, "Verification reality" section.
- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/plan.md` — "Real evidence used to size the new
  budgets" (the full widen-retry ladder rationale and the GHA 360-minute per-job ceiling check),
  "Verification path — pre-merge manual workflow_dispatch" (step 1), Phasing § Phase 1 step 1e-1f.
- **GitHub Actions access**: `push: true, maintain: true` is available per the dispatch brief this
  mission was opened under.
- **The bounded widen-retry ladder** (plan.md, stated here verbatim for this WP's use): `90`
  (Stage A, WP02) -> `150` (widen attempt 1) -> `300` (widen attempt 2, FINAL ceiling). At most
  TWO widen-and-redispatch attempts total. `300` minutes stays comfortably under GitHub Actions'
  documented 6-hour/360-minute per-job execution ceiling for hosted (`ubuntu-latest`) runners.
- **Each widen-retry timeout bump is its OWN small `chore(ci)` commit** to `ci-nightly.yml`'s
  `stress` `timeout-minutes` value — this workflow's `on.workflow_dispatch.inputs` block exposes
  only `mode` (`full`/`pr`), not a timeout-override input, so a widen retry is necessarily a
  file-edit action, never a dispatch-parameter-only one.
- **Stage B's re-derivation is a SEPARATE commit from WP02's Commit B and from any widen-retry
  commit** — never folded together.

## Branch Strategy

- **Strategy**: `single_branch`.
- **Planning base branch**: `issue-4865-ci-nightly-wallclock-budget`
- **Merge target branch**: `issue-4865-ci-nightly-wallclock-budget`

> Populated automatically by `spec-kitty agent mission tasks`. Do NOT change manually.

## Subtasks & Detailed Guidance

### Subtask T013 – Dispatch `ci-nightly.yml`

- **Purpose**: FR-009 — the mission's first live evidence.
- **Steps**:
  1. Ensure WP02's commit is present on `issue-4865-ci-nightly-wallclock-budget` and pushed to
     origin (`gh workflow run` dispatches against the pushed branch state, not local commits).
  2. Run: `gh workflow run ci-nightly.yml --ref issue-4865-ci-nightly-wallclock-budget -f
     mode=full`
  3. Capture the run URL (`gh run list --workflow=ci-nightly.yml --branch
     issue-4865-ci-nightly-wallclock-budget --limit 1` or the URL `gh workflow run` itself may
     print/return).
- **Files**: None (this is a live dispatch action, not a repo file edit).
- **Parallel?**: No.
- **Notes**: If `gh auth status` shows scope issues, `unset GITHUB_TOKEN && gh auth status` per
  CLAUDE.md's documented keyring-auth pattern.

### Subtask T014 – Capture job conclusions, stress's completed duration, xunit confirmation

- **Purpose**: NFR-001 (independent verdicts), NFR-002 (stress completes), NFR-006 (durable
  evidence, not verbal claim) — and Stage B (T017) depends on the exact duration captured here.
- **Steps**:
  1. Once the run completes (or is cancelled), `gh run view <run-id> --json jobs` to get each of
     `performance`/`e2e`/`stress`'s job conclusion.
  2. From the same JSON, capture `stress`'s step-level start/end timestamps to compute its ACTUAL
     COMPLETED duration (not just "success" — the number itself matters for T017).
  3. Confirm `out/reports/xunit-nightly-stress.xml` exists in the `stress` job's uploaded artifact
     — `gh run download <run-id>` or `gh api` against the artifact list; do not assume existence
     from a bare "success" conclusion.
  4. Record all of the above in this WP's Activity Log immediately — do not defer, the dispatch
     UI's retained data is not indefinite.
- **Files**: None (verification/recording action).
- **Parallel?**: No — depends on T013.

### Subtask T015 – [Conditional] Widen-retry ladder if Stage A truncates

- **Purpose**: If `stress` is STILL truncated inside Stage A's 90-minute ceiling, that is real
  signal the suite needs more room — not evidence to force Stage B from an incomplete duration.
- **Steps** (only if T014 shows `stress` conclusion `cancelled`/truncated):
  1. Edit `.github/workflows/ci-nightly.yml`'s `stress` job `timeout-minutes` to `150` (widen
     attempt 1). Commit as its own `chore(ci)` commit (e.g. `chore(ci): widen stress
     measurement-only ceiling to 150m (attempt 1)`).
  2. Re-dispatch: `gh workflow run ci-nightly.yml --ref
     issue-4865-ci-nightly-wallclock-budget -f mode=full`. Repeat T014's capture for this run.
  3. If STILL truncated at `150`, widen to `300` (widen attempt 2, the FINAL ceiling this ladder
     permits) — same commit-then-dispatch-then-capture pattern. Do not widen a third time.
  4. Record EVERY dispatch this step performs — run URL, conclusion, duration — for WP07's later
     consolidation.
- **Files**: `.github/workflows/ci-nightly.yml`
- **Parallel?**: No.
- **Notes**: Skip entirely if T014 already shows a completed `stress` conclusion within 90
  minutes — this is the EXPECTED case (plan.md: the cited run's `stress` step was already
  observed running >=16m18s before truncation, comfortably inside 90 minutes on a first attempt).

### Subtask T016 – [Conditional] Escalate a genuine hang/deadlock

- **Purpose**: If even the `300`-minute final ceiling is exceeded, this is no longer a sizing
  problem — it is a genuine, unexpected test-suite defect.
- **Steps** (only if T015's `300`-minute dispatch ALSO fails to let `stress` complete):
  1. Do NOT widen further.
  2. Apply the charter's Pre-existing Failure Reporting Rule: file a GitHub issue with the
     command run, the failure summary (stress still not completing at 300 minutes), and the
     specific confirmation-method caveat plan.md names for this exact case — the standard
     "confirmed still red on `upstream/main`" method does not transfer here, because `stress` is
     never isolated long enough to hang or complete on `upstream/main` today (it is always
     truncated early by the OLD shared 60-minute job cap this mission is fixing). Describe the
     situation honestly as "a suite that could not be shown to complete within a generous,
     newly-isolated budget" rather than claiming a pre-existing-on-main confirmation that cannot
     actually be performed.
  3. Escalate to the operator. STOP — do not proceed to T017/T018 until the operator resolves
     this.
- **Files**: None (issue filing only).
- **Parallel?**: No.
- **Notes**: This is expected to be rare — plan.md frames it as the pathological case, not the
  typical one.

### Subtask T017 – Unconditional Stage B re-derivation

- **Purpose**: PLAN-ARCH-001 — regardless of whether Stage A's `90` (or a widened ceiling) merely
  "happened to be sufficient," this step ALWAYS runs once a real completed duration exists.
- **Steps**:
  1. Take `stress`'s real COMPLETED job duration from T014 (or the successful widen attempt in
     T015).
  2. Apply the SAME ~1.5x-headroom method already used for `performance` (23m41s -> 35) and `e2e`
     (24m44s -> 40) to derive `stress`'s tightened, FINAL production `timeout-minutes`.
  3. Edit `.github/workflows/ci-nightly.yml`'s `stress` job `timeout-minutes` to this derived
     value.
- **Files**: `.github/workflows/ci-nightly.yml`
- **Parallel?**: No — depends on T014 (or T015's successful widen attempt).
- **Notes**: The shipped value must differ from `60` unless a genuine re-derivation independently
  lands on that same number, and must differ from Stage A's `90` (or whatever widened ceiling
  succeeded) unless the re-derivation independently lands there too — coincidence is possible,
  assumption is not.

### Subtask T018 – Commit Stage B as its own `fix(ci)` commit

- **Purpose**: Keep Stage B strictly separate from WP02's Commit B and any T015 widen-retry
  commit, per plan.md's explicit "SEPARATE, subsequent commit" discipline.
- **Steps**: Stage, commit with a message like `fix(ci): re-derive stress timeout from measured
  dispatch duration (Stage B)`.
- **Files**: `.github/workflows/ci-nightly.yml`
- **Parallel?**: No.

### Subtask T019 – Re-confirm the pull_request-trigger tests still pass

- **Purpose**: Close the loop that T015/T017's edits (both touching only a `timeout-minutes`
  scalar) did not somehow introduce a trigger-shape regression.
- **Steps**: `uv run --frozen pytest
  tests/architectural/test_performance_marker_guard.py::test_nightly_workflow_never_triggers_on_pull_request
  tests/architectural/test_performance_marker_guard.py::test_no_pull_request_workflow_selects_performance_or_interpreter_jobs
  -q` — confirm both pass.
- **Files**: None (verification only).
- **Parallel?**: No.

## Red-first / revert discipline (concrete, for this WP)

This WP carries two distinct claims, and only one of them has a WP-scoped red/green gate this WP
can itself close against.

**Job-topology claim (inherited from WP02) — WP-scoped gate exists.** Already covered by WP02's
own red-first section: the cited run `35683539593`'s single blended `performance-and-e2e` verdict
IS the topology "red"; this WP's dispatch, T013/T014, is the "green".

**T017's Stage B sufficiency sub-claim — NO WP-scoped red/green gate.** This WP additionally
introduces its own sub-claim via T017: that Stage B's re-derived `stress` `timeout-minutes` is
actually sufficient. Unlike the topology claim above, this sub-claim has no red/green condition
this WP's own T013/T014/T017 cycle can observe or close against — by construction that cycle only
ever sees ONE completed `stress` duration. The only real falsification event — a SUBSEQUENT
`stress` run on `ci-nightly.yml`'s nightly (scheduled) trigger being cancelled/truncated against
the newly-derived `timeout-minutes` — can only occur on a future nightly run, after this WP has
already closed. This section therefore does **not** present a WP-closeable verifiable gate for
T017's sufficiency claim, because none exists: it is accepted instead as a documented,
forward-looking risk — see the "T017's headroom sufficiency is unverifiable at WP-close" entry in
this WP's own "Risks & Mitigations" section below, which this paragraph cross-references rather
than duplicates.

## Test Strategy

- `uv run --frozen pytest tests/architectural/test_performance_marker_guard.py -q` (T019, the two
  trigger-detection tests specifically) — the only pytest-observable claim available for this WP;
  everything else (job topology, verdicts, durations) is live-dispatch evidence, not
  pytest-provable.

## Risks & Mitigations

- **Risk**: treating Stage A's success as license to skip Stage B ("it worked, ship it").
  **Mitigation**: T017 is explicitly unconditional; do not gate it on T015 having been needed.
- **Risk**: losing track of which dispatch (90/150/300) actually produced the duration used for
  Stage B. **Mitigation**: T014/T015 both require recording the duration inline as it happens.
- **Risk**: the widen ladder runs past two attempts. **Mitigation**: T015 is hard-capped at two
  widen attempts (150, then 300); T016 is the mandatory stop condition beyond that.
- **Risk (T017's headroom sufficiency is unverifiable at WP-close)**: T017's Stage B
  `timeout-minutes` re-derivation may turn out insufficient for `stress`'s real run-to-run
  variance, but this WP has no way to observe that before it closes — the only falsification
  event (a SUBSEQUENT nightly/scheduled `ci-nightly.yml` run's `stress` job being
  cancelled/truncated against the newly-derived value) can only occur on a future nightly run, and
  this WP's own T013/T014/T017 cycle only ever sees ONE completed duration. **Mitigation**: none
  available within this WP's own execution — accepted as a documented, forward-looking risk (see
  the "Red-first / revert discipline" section above, which cross-references this entry instead of
  claiming a WP-scoped gate). If a subsequent nightly run does truncate, that truncation is itself
  the real-world falsification signal, and re-derivation must happen then, from a fresh completed
  duration, following T017's same ~1.5x-headroom method.

## Review Guidance

- Confirm the dispatch run URL, all three job conclusions, and `stress`'s captured duration are
  present in this WP's Activity Log — not merely asserted as "done."
- Confirm the xunit artifact existence check (T014.3) was actually performed, not assumed.
- Confirm Stage B's commit (T018) is separate from WP02's commit and from any T015 widen commit.
- If T016's escalation path was taken, confirm the filed issue uses the case-specific confirmation
  wording (not a false "confirmed on upstream/main" claim).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Initial entry**:

- 2026-09-22T14:15:00Z – system – Prompt created.

- 2026-09-22T17:35:19Z – claude (implementer, rejection-fix pass) – Claimed WP03 via
  `.venv/bin/spec-kitty agent action implement WP03 --mission ci-nightly-wallclock-budget-01M34HNZ
  --agent claude`, retroactively closing the SK-175 gap this WP's own tracer entry recorded
  (T013-T018's code/commit had already landed on `issue-4865-ci-nightly-wallclock-budget` via
  `154a6c6e6` while the lane was still `planned`). First attempt hit a transient global-asset-sync
  `RuntimeError: Global asset input changed: ...` (same defect family as this WP's tracer entry
  "`agent status emit` leaks a raw RuntimeError"); a retry succeeded cleanly (lane: `planned` ->
  `claimed` -> `in_progress`), confirming the failure was a transient race on a global,
  mission-external asset rather than anything in this WP's own state. Resolved workspace path
  returned: `/home/jeroennouws/dev/SK-missions/4865/.worktrees/ci-nightly-wallclock-budget-01M34HNZ-lane-a`
  (`kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a`, tip `d1e7d5177`, unchanged) — per
  the already-documented SK-91/SK-199 reproduction, WP03's actual code lives directly on
  `issue-4865-ci-nightly-wallclock-budget`, not on this lane worktree.

- 2026-09-22T17:40:00Z – claude (implementer, rejection-fix pass) – Fixed the reviewer's
  severity-4 finding (coupling risk undocumented in the workflow): added two forward-warning
  comments to `.github/workflows/ci-nightly.yml` naming #4865 explicitly and stating what NOT to
  do plus the consequence:
  - `performance` job's `env:` block, above `SPEC_KITTY_RUN_PERFORMANCE: "1"` (now line 100,
    was line 100 pre-edit) — warns against adding this env var to any other job (`stress` named
    explicitly), because doing so re-duplicates the ~20 performance-marked tests and reproduces
    #4865's truncation defect.
  - `stress` job, immediately above `timeout-minutes: 10` (now line ~250) — warns against setting
    `SPEC_KITTY_RUN_PERFORMANCE` on this job, states the 10-minute budget assumes the ~20
    performance-marked tests stay skipped here, and names the consequence (reintroduces
    duplication, blows the budget, reproduces #4865's ~16m18s+ truncation).
  `yaml.safe_load` confirmed 7 jobs and `nightly-summary.needs ==
  [performance, e2e, stress, interpreter-matrix, full-module-matrix]` after the edit — unchanged
  from before. `grep -niE 'do not add|never add|must not add|reintroduc|blow this|will exceed|do
  not set' .github/workflows/ci-nightly.yml` now returns 3 hits (both new comment blocks), where
  it previously returned none.

- 2026-09-22T17:42:00Z – claude (implementer, rejection-fix pass) – Addressed the reviewer's
  severity-1 finding (unreproducible "107 passed/1 skipped across four architectural test files"
  claim). Searched this checkout for the literal string `107 passed` across
  `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/` (spec.md, plan.md, tasks.md, this WP's own
  prompt file, `status.events.jsonl`, and `reviews/*.yaml`) and across the WP03 implementation
  commit (`154a6c6e6`)'s message — **no match anywhere**. The figure's original source could not
  be located in any committed artifact, so it cannot be honestly reproduced or attributed; this WP
  is not claiming it. In its place, the following IS reproducible, run directly against this WP's
  own change:
  - `.venv/bin/python -m pytest
    tests/architectural/test_performance_marker_guard.py::test_nightly_workflow_never_triggers_on_pull_request
    tests/architectural/test_performance_marker_guard.py::test_no_pull_request_workflow_selects_performance_or_interpreter_jobs
    -q` (T019, re-run after the comment edit) → `2 passed in 0.31s`.
  - `.venv/bin/python -m pytest tests/architectural/test_performance_marker_guard.py
    tests/architectural/test_marker_job_completeness.py tests/architectural/test_workflow_coherence.py
    tests/architectural/test_ci_corpus_trigger_completeness.py -q` (four architectural test files
    directly covering `ci-nightly.yml`'s job/marker/trigger shape, the closest honest match to
    "four architectural test files" this WP could construct) → `40 passed in 1.36s`, 0 skipped.
    This number (40 passed / 0 skipped) is offered as the corrected, reproducible figure in place
    of the unreproducible 107/1 claim — it does not match it, and no attempt is made to reconcile
    the two.

- 2026-09-22T17:48:00Z – claude (implementer, rejection-fix pass) – `move-task WP03 --to
  for_review` refused with `Cannot move WP03 to for_review - unchecked subtasks: T015, T016`. Both
  are this WP's CONDITIONAL subtasks (widen-retry ladder / hang escalation), gated on T014 showing
  a truncated `stress` conclusion. T014's actual result — `stress` completed in 4m44s, well inside
  the 90-minute Stage A ceiling (see `154a6c6e6`'s commit message and the `stress` job's own
  comment block in `ci-nightly.yml`) — is exactly the documented "Skip entirely" case this WP's own
  T015 Notes describe as "the EXPECTED case." Marked T015/T016 `done` via the canonical
  `.venv/bin/spec-kitty agent tasks mark-status T015 T016 --status done --mission
  ci-nightly-wallclock-budget-01M34HNZ` (not `--force` on the lane transition, and no file
  hand-edited) to record that their skip-condition was correctly evaluated and satisfied, not that
  either ladder step or the escalation was performed.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP03 --to
<status>` to change WP status.
