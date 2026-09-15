---
work_package_id: WP05
title: The reporting job
dependencies:
- WP04
requirement_refs:
- FR-002
- FR-004
- FR-005
- FR-007
- FR-008
- FR-011
- FR-012
- FR-014
- NFR-003
- NFR-004
- NFR-005
- NFR-006
- NFR-008
planning_base_branch: issue-4334-sonar-reuse-shard-coverage
merge_target_branch: issue-4334-sonar-reuse-shard-coverage
branch_strategy: Planning artifacts for this mission were generated on issue-4334-sonar-reuse-shard-coverage. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4334-sonar-reuse-shard-coverage unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
- T027
history:
- date: '2026-09-14'
  note: Created by /spec-kitty.tasks. Source-tree mechanism corrected after the post-plan squad refuted the subdirectory design.
agent_profile: python-pedro
authoritative_surface: .github/workflows/ci-aggregate.yml
create_intent:
- scripts/ci/sonar_pr_analysis.py
- tests/ci/test_sonar_pr_analysis.py
- tests/release/test_sonar_workflow.py
execution_mode: code_change
owned_files:
- .github/workflows/ci-aggregate.yml
- scripts/ci/sonar_pr_analysis.py
- tests/ci/test_sonar_pr_analysis.py
- tests/release/test_sonar_workflow.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

Apply the resolved initialization, boundaries, directives and tactics, and state which you applied.
`governance unresolved` is a known pre-existing condition — reconstruct from
`.kittify/charter/charter.md` and say so. Retry the `Global asset input changed` race.

## Objective

Add the per-change reporting job to the aggregation workflow so it consumes the measurement the
matrix already produced, under an execution condition whose **every conjunct is independently
asserted**.

This is the mission's functional core. Read `contracts/reporting-job-contract.md` in full before
writing anything.

## Two mechanisms that were corrected — do not revert them

**1. Source-tree delivery.** An earlier design placed the change's sources in a subdirectory and
pointed the analysis base directory at it. That was **refuted**: the analysis configuration file is
located *relative to the base directory*, so the scanner would have loaded the **change's own**
configuration — the exact breach the subdirectory was chosen to prevent. It also traded a
file-enumeration problem for a key-enumeration problem.

Use instead: keep the base directory at the trusted checkout root and replace **only the two analysed
trees** in place, after binding the fetched revision to the validated one and failing loudly on
mismatch. Trust becomes an allowlist of two replaced paths. Delete before checkout, so deletions in
the change are honoured rather than leaving stale files behind.

**2. The verdict job is for declarability, not enforcement.** Live evidence: 10 sampled runs of the
current reporting workflow show 7 failed jobs and 10 green run conclusions — the job-level
non-blocking declaration already holds the run green. A terminal job **cannot** rescue a run
conclusion. What it buys is a seam a test can assert the reporting job is excluded from. Model it on
the **router gate** pattern (skipped-tolerant, always-evaluating), **not** the quality-gate pattern —
both sibling jobs in this workflow are legitimately skippable, and a verbatim port would fail the
verdict on every such run.

## Subtasks

### T023 — Red-first: behavioural tests for each execution-condition conjunct

**Purpose**: C-006 requires the red-first check to exercise behaviour where behaviour is extractable.
For this job it is — provided you author the condition as an extractable evaluator rather than
inlining it into a workflow expression.

**Steps**:
1. Author the execution condition as a heredoc-style evaluator reading its inputs from the
   environment, mirroring the existing extraction-and-execute harness used elsewhere in this repo's
   architectural tests.
2. Write tests that extract that evaluator and drive it with synthetic payloads, asserting
   **independently** that the job does not run when:
   - the triggering run's event is not a pull request (FR-014, C-001);
   - the triggering run's head repository is not this repository (FR-011, NFR-004);
   - the assembly job did not succeed (FR-004);
   - the assembly reported an incomplete set (FR-007, NFR-006);
   - the credential is absent — skip with an advisory notice, never fail (FR-008).
3. Assert each conjunct **separately**, never as one condition string. Dropping one clause must be
   caught; a whole-string assertion makes every future edit a churn.

**Validation**: five reds before the job exists.

### T024 — Extract source delivery and identity resolution into a tested script

**Steps**:
1. Create `scripts/ci/sonar_pr_analysis.py` handling: resolving the change identity from the
   **validated source record** (never a mutable event projection); reading the head/base branch names
   and origin repository from a trusted authenticated lookup keyed on that validated identity; binding
   the fetched revision to the recorded tested revision and failing loudly on mismatch; and assembling
   the explicit analysis arguments from trusted content.
2. Unit-test it in `tests/ci/test_sonar_pr_analysis.py` against fixture payloads — including the
   mismatch path, which must raise.

**Validation**: unit tests cover the happy path and every refusal path.

### T025 — Add the reporting job

**Steps**:
1. Add the job with `needs:` on the assembly job and the T023 condition. **No always-evaluating
   modifier** — the reconciled artefact is uploaded even when the assembly fails, and the failure
   verdict is written before the assembly exits, so artefact presence is not evidence of completeness.
2. Consume the already-published reconciled coverage and source artefacts.
3. Replace the two analysed trees per the corrected mechanism; pass every analysis setting explicitly
   from trusted content.
4. **SHA-pin every action you add**, and extend `tests/release/test_sonar_workflow.py` to assert the
   new job's actions are pinned. A verbatim relocation would carry two floating tags into a file whose
   every other step is pinned. (WP06 later re-points the cross-surface parity operand in the same file.)
5. **Do not carry over the dependency-sync step.** This job runs no tests, and syncing executes
   change-authored build configuration — a security regression.
6. Add an in-tree comment naming the publication blocker (**#4350**) and why the report may not
   publish, so a future reader is not misled by a green pipeline.

**Validation**: workflow parses; the gate battery passes.

### T026 — Terminal verdict job and permissions

**Steps**:
1. Add a skipped-tolerant terminal verdict job modelled on the router gate, explicitly excluding the
   reporting job, so "excluded" is **declared** and therefore assertable.
2. Widen permissions for the pull-request metadata read — **job-scoped**, so the blast radius on the
   sibling jobs is unchanged.

**Validation**: the verdict job tolerates skipped siblings; permissions are job-scoped.

### T027 — Re-check the downstream parse timeout

**Purpose**: after WP01's broadening the reconciled artefact set grows roughly six-fold, and it is
downloaded twice and parsed inside a time-boxed job.

**Steps**: measure the downstream parse step against the enlarged set and confirm it fits the budget,
or raise the budget with recorded evidence.

**Validation**: recorded measurement.

## Branch Strategy

- **Planning base branch**: `issue-4334-sonar-reuse-shard-coverage`
- **Final merge target**: `issue-4334-sonar-reuse-shard-coverage`
- Worktrees are allocated per computed lane from `lanes.json`; `spec-kitty implement WP05` resolves it.

## Declared limit (C-006)

A change-triggered handler of this kind executes only the **default-branch copy** of its workflow
file, so this job **cannot run on the pull request that introduces it**. That is why T023's proof is
behavioural over an extracted evaluator rather than an observed run. The first post-integration run
must be **observed and recorded** (WP06/T032) — never claimed.

**Test scope (operator ruling):** run **targeted tests only** — your own new tests plus the specific gate files your diff touches (locate them with `grep -rl "<symbol>" tests/ --include="*.py"`). **Do not run the full `tests/architectural/` battery** — it is heavy, has been observed killing dispatched agent processes, and belongs to CI. Record the exact commands and counts in your handoff; "targeted tests pass, full arch suite deferred to CI" is the honest statement.

## Definition of Done

- [ ] Five conjuncts each independently asserted, each RED before the job existed
- [ ] Source delivery replaces only the two analysed trees; base directory stays at the trusted root
- [ ] Revision binding fails loudly on mismatch
- [ ] Every analysis setting passed explicitly from trusted content
- [ ] No always-evaluating modifier on the reporting job
- [ ] Every added action SHA-pinned; no dependency-sync step carried over
- [ ] Verdict job is skipped-tolerant and excludes the reporting job
- [ ] Permissions widened job-scoped only
- [ ] In-tree comment names #4350
- [ ] `ruff check .` and `ruff format --check .` clean

## Reviewer Guidance

- **The single most important check**: can the change under review influence the analysis? Read the
  diff asking "which of these values could a contributor change?" If the configuration file comes from
  the replaced trees, the mechanism regressed to the refuted design.
- **Check each conjunct is asserted separately.** A whole-condition-string assertion means dropping
  the same-origin clause would not be caught — and that clause is the mission's principal security
  change.
- **Check there is no always-evaluating modifier.** Copying the sibling gate's shape without its
  internal re-check publishes partial coverage that reads as a regression.
- **Reviewer ≠ implementer** (C-007).
