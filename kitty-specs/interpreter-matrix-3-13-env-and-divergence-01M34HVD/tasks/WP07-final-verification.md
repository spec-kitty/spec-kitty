---
work_package_id: WP07
title: 'Final verification: local repro + operator-authorized manual dispatch'
dependencies:
- WP02
- WP03
- WP04
- WP05
- WP06
requirement_refs:
- FR-001
- C-003
planning_base_branch: issue-4866-interpreter-matrix-3-13
merge_target_branch: issue-4866-interpreter-matrix-3-13
branch_strategy: Planning artifacts for this mission were generated on issue-4866-interpreter-matrix-3-13. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4866-interpreter-matrix-3-13 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: python-pedro
authoritative_surface: kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/
create_intent:
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-final-verification.md
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-final-verification.md
role: implementer
tags: []
tracker_refs: []
---

# WP07 — Final verification: local repro + operator-authorized manual dispatch

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select
the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Validate the whole mission's diff against the real `interpreter-matrix` job
by (1) a final local reproduction of the exact `uv sync` + `uv run` step
pair, and (2) an **operator-authorized** manual `workflow_dispatch` of the
real workflow — since no PR check exercises `ci-nightly.yml` at all
(`schedule`/`workflow_dispatch`-only trigger, C-003).

## Context — read completely before starting, especially the STOP instruction

**This WP is a genuine chokepoint.** It depends on **every other WP in this
mission** (WP02, WP03, WP04, WP05, WP06) — not just the three underlying
fixes (WP02/WP03/WP04), but also WP05's re-measurement and WP06's
disposition, because a single dispatch should validate the mission's *final*
state end-to-end, not an intermediate one. This is stated explicitly here,
in addition to the dependency edges in `wps.yaml`, because a shared-CI-
dispatch-surface chokepoint like this one is easy to under-communicate by
dependency graph alone — do not start this WP while any of its five
dependencies is still in progress, and do not interpret "dependencies
approved" as license to dispatch early against a partial mission state.

**⚠️ THE MANUAL DISPATCH REQUIRES EXPLICIT OPERATOR AUTHORIZATION BEFORE IT
RUNS.** This is an outward-facing action on a **public** repository
(`spec-kitty/spec-kitty`) and is **never self-authorized** by the
implementing agent, no matter how routine it seems or how explicitly the
spec/plan names the exact command. T002 below is a hard STOP: do not proceed
past it without an explicit operator go-ahead recorded in this WP's
completion trail. This is not a formality — running `gh workflow run` is a
real, visible action against the public repo's Actions history.

**Why no CI safety net exists for this change** (C-003): `ci-nightly.yml`
triggers on `schedule` + `workflow_dispatch` only — never `pull_request` or
`push` (confirmed by direct read of the file's `on:` block during spec/plan
authoring; re-confirm live if you have any doubt). A PR that edits this
workflow file gets **zero** automatic CI signal from the very workflow it
changes. This WP's two steps (local repro, then operator-gated manual
dispatch) are the *only* verification this mission's core fix (WP03) gets
against the real job.

## Subtask T001: Final local reproduction

**Purpose**: One more confirmation of the exact command pair, against the
mission's *final* branch state (all WPs landed), before requesting the
operator go-ahead for the real dispatch.

**Steps**:
1. On a real Python 3.13 interpreter, with the mission branch's final state
   checked out (all of WP02/WP03/WP04/WP05/WP06 landed), run the exact `uv
   sync` + fixed `uv run` step pair, mirroring `ci-nightly.yml`'s own
   commands byte-for-byte (same command as WP03's T005, repeated here
   against the final state rather than WP03's own intermediate state):
   ```bash
   uv sync --frozen --all-extras --python 3.13
   uv run --frozen --python 3.13 --all-extras pytest -m "fast or unit" -q \
     --junitxml=out/reports/xunit-nightly-interpreter-3.13.xml
   ```
   Note the flag order: `--python 3.13 --all-extras` sit **between** `uv run
   --frozen` and `pytest` — once the `pytest` command word appears, `uv
   run` passes everything after it straight through to `pytest`, so flags
   placed after `pytest` would be parsed (and rejected) as pytest arguments,
   not consumed by `uv run` (see WP03's T003/T005, which fix the same class
   of defect in the workflow file and its own worked reproduction command).
   Apply an explicit bounded timeout (≥600s) and run in the foreground.
2. Confirm 3.13 site-packages in use, zero `ModuleNotFoundError` for
   `pytestarch`/`respx`/`pytest_benchmark` (SC-001's signature), and that the
   pass/fail/error counts are consistent with WP05's re-measurement (they
   should match closely, modulo any drift from WP06's own changes, which are
   documentation/issue-filing only and should not change test outcomes).

**Files**: create
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-final-verification.md`
and record the repro command + outcome.

**Validation**: 3.13 site-packages confirmed; zero `ModuleNotFoundError`;
counts consistent with WP05.

## Subtask T002: STOP — request operator authorization

**Purpose**: Satisfy the binding requirement that the manual dispatch is
never self-authorized.

**Steps**:
1. Stop here. Do not run `gh workflow run` in this subtask or any earlier
   one.
2. Present to the operator: T001's local repro result, a summary of WP05's
   re-measurement, and WP06's disposition statement (residual is zero /
   small-fixable / large-out-of-scope, filed against #3189 if applicable).
3. Explicitly ask: "May I dispatch `ci-nightly.yml` against
   `issue-4866-interpreter-matrix-3-13` now?" — do not proceed to T003
   without an explicit, recorded yes.

**Files**: append the go-ahead record to `evidence-final-verification.md`
(same file as T001).

**Validation**: An explicit operator go-ahead is recorded before T003
proceeds. If the operator declines or defers, this WP pauses here — it does
not silently skip the dispatch and report the mission complete without it;
SC-001's acceptance criterion is not satisfied without a real dispatch
result.

## Subtask T003: Dispatch and watch the real job

**Purpose**: Execute the only check that exercises the real
`interpreter-matrix` job end-to-end.

**Steps** (only after T002's explicit go-ahead):
1. ```bash
   gh workflow run ci-nightly.yml --ref issue-4866-interpreter-matrix-3-13
   ```
2. Watch it: `gh run watch` (or `gh run list --workflow=ci-nightly.yml`
   followed by `gh run view --log <run-id>` once it appears).
3. This may take up to the job's own 45-minute `timeout-minutes` budget
   (`interpreter-matrix` job in `ci-nightly.yml`) — do not assume it
   completes quickly; if watching via a foreground command, apply a
   correspondingly generous bounded timeout or poll rather than blocking
   indefinitely on a single unbounded `gh run watch` invocation (SK-99
   discipline applies here too, even though this isn't a `pytest` command).

**Files**: append the run URL/ID to `evidence-final-verification.md`.

**Validation**: The real `interpreter-matrix` job run completes (or reaches
a stable state worth reporting on).

## Subtask T004: Confirm SC-001 against the real job log

**Purpose**: Close the loop — confirm the real job, not just the local
repro, shows the fixed behavior.

**Steps**:
1. Inspect the `interpreter-matrix` job's log for the `pytest` invocation
   line: confirm it shows the 3.13 interpreter's site-packages path and
   zero `ModuleNotFoundError` for `pytestarch`/`respx`/`pytest_benchmark`
   (`gh run view --log <run-id>` or the Actions web UI).
2. Note the job's overall pass/fail outcome (per WP06's disposition, this
   leg may legitimately still report red from genuine, tracked, out-of-scope
   3.13 divergence — that is expected and acceptable, not a failure of this
   WP). What matters for SC-001 specifically is the *environment* being
   correct (right interpreter, right extras), not the leg's overall
   pass/fail color.
3. Record the run URL/ID and the observed log evidence for the mission's PR
   body.

**Files**: append the log evidence to `evidence-final-verification.md` (same
file as T001-T003) — PR-prep copies this into the PR body.

**Validation**: The real job's log confirms SC-001 (3.13 site-packages, zero
`ModuleNotFoundError`), and the run URL/ID is recorded.

## Definition of Done

- [ ] T001: final local repro against the mission's fully-landed branch
      state confirms SC-001's signature and counts consistent with WP05
      (`spec-kitty agent tasks mark-status T001 --status done`).
- [ ] T002: explicit operator go-ahead requested and recorded before any
      dispatch is executed
      (`spec-kitty agent tasks mark-status T002 --status done`).
- [ ] T003: real `workflow_dispatch` run executed and watched to completion
      or a stable reportable state
      (`spec-kitty agent tasks mark-status T003 --status done`).
- [ ] T004: the real job's log confirms SC-001; run URL/ID recorded for the
      PR body
      (`spec-kitty agent tasks mark-status T004 --status done`).

## Risks

- **The single greatest risk in this WP is self-authorizing the dispatch.**
  Re-read T002 if there is any temptation to treat "the spec/plan names this
  exact command" as authorization — it names the command for *planning*
  purposes; it does not pre-authorize *this specific execution* of it.
- The job can take up to 45 minutes; do not assume a quick turnaround, and
  do not abandon watching it partway through and report an unconfirmed
  outcome.
- If T001's final repro or the T003 dispatch reveals something materially
  different from WP05's re-measurement (e.g. a new failure that wasn't
  present in WP05's local run), stop and flag it rather than silently
  reconciling the discrepancy — it may indicate an environment difference
  between local and Actions runners worth recording.

## Reviewer Guidance

- Confirm T002's operator go-ahead is genuinely recorded (not inferred or
  assumed) before treating T003 as legitimately executed.
- Confirm the dispatch actually targeted
  `issue-4866-interpreter-matrix-3-13` (not `main` or another branch).
- Confirm T004's SC-001 evidence comes from the real job's log, not
  re-asserted from T001's local repro.
- Confirm this WP's only file change is its own
  `evidence-final-verification.md` (verification-only otherwise).

Implementation command: `spec-kitty agent action implement WP07 --agent claude`
