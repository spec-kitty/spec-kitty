# Tasks: Per-PR Sonar reuses CI Modules coverage

**Mission**: `sonar-per-pr-coverage-reuse-01M2FR32` · **Issue**: [#4334](https://github.com/spec-kitty/spec-kitty/issues/4334)
**Branch**: `issue-4334-sonar-reuse-shard-coverage` · **Created**: 2026-09-14
**Inputs**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
**Squad evidence**: `work/4334-sonar-coverage-reuse/squad-post-spec.md`, `work/4334-sonar-coverage-reuse/squad-post-plan.md`

## Lanes

| Lane | Work packages | Character |
|---|---|---|
| **A — measurement** | WP01 → WP02 | Changes *what is measured*. Touches the matrix runner and the test inventory. |
| **B — topology & enforcement** | WP03 → WP04 → WP05 → WP06 | Changes *who reads the measurement*. Touches the gate model, the reporting workflow, and the retirement. |

The two lanes own disjoint file sets and can run concurrently. Within a lane the order is strict —
each WP consumes its predecessor's observable output.

**The one ordering that is not negotiable**: WP04 (the regression battery) must land **before** WP06
(the retirement), so the battery's strongest mutation — "reintroduce the retiring step" — is proven
red against **live source** rather than a synthetic fixture. Retiring first would leave only a
fixture, reproducing the exact blindness the battery exists to close.

## Preconditions (outside this mission's control)

- **#4350** — SonarCloud Automatic Analysis must be disabled before FR-015/SC-010 can be satisfied.
  Verified live: the project currently holds **no coverage metric at all**. This blocks the mission's
  *publication* claims only; every other requirement is independently verifiable.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first gate: every slice measures the full top-level package set | WP01 | |
| T002 | Broaden the coverage-target derivation in the matrix runner | WP01 | |
| T003 | Measure and record aggregate cost: runner-minutes, artefact bytes, parse duration | WP01 | |
| T004 | Record the per-file coverage baseline artefact | WP01 | |
| T005 | Derive and commit the marker-mismatch exception set (FR-016) | WP01 | |
| T006 | Prove no per-file coverage regression outside the declared exception set | WP01 | |
| T007 | Commit a reproducible shard-timings capture script | WP02 | |
| T008 | Measure durations for the two new directories; record the producing run | WP02 | |
| T009 | Add the two inventory rows plus matching recognised-group entries | WP02 | |
| T010 | Wire the router filter groups for the two new rows | WP02 | |
| T011 | Re-freeze the non-vacuity floor and run the inventory gate battery | WP02 | |
| T012 | Prove both directories collect >0 tests and balancing uses fresh data | WP02 | |
| T013 | Red-first: the gate model cannot see indirect suite invocations | WP03 | |
| T014 | Resolve `run:` steps transitively to a suite invocation | WP03 | |
| T015 | Reconcile the workflow allowlist with the widened detection | WP03 | |
| T016 | Rewrite the non-blocking rationale to describe what is actually detected | WP03 | |
| T017 | Register any new architectural test file in the shard map | WP03 | |
| T018 | Battery scaffold with a non-vacuity floor over discovered workflows | WP04 | |
| T019 | Mutations 1-3 proven RED against the live retiring step | WP04 | |
| T020 | Mutation 4: a net-new workflow file forces directory enumeration | WP04 | |
| T021 | Mutations 5-6: removal of the non-blocking and same-origin declarations | WP04 | |
| T022 | Assert the unmutated live tree is clean | WP04 | |
| T023 | Red-first: behavioural tests for each execution-condition conjunct | WP05 | |
| T024 | Extract source-tree delivery and identity resolution into a tested script | WP05 | |
| T025 | Add the reporting job to the aggregation workflow | WP05 | |
| T026 | Add the skipped-tolerant terminal verdict job and widen permissions | WP05 | |
| T027 | Re-check the downstream parse timeout against the enlarged artefact set | WP05 | |
| T028 | Commit the pinning-rule derivation, its artefact, and a re-derive gate | WP06 | |
| T029 | Retire the duplicate-measurement job | WP06 | |
| T030 | Execute every disposition in the derived inventory | WP06 | |
| T031 | Update the governance documents in lockstep | WP06 | |
| T032 | Record issue-matrix verdicts and the post-integration observation | WP06 | |

---

## WP01 — Broaden coverage measurement

**Lane**: A · **Dependencies**: none · **Prompt**: [tasks/WP01-broaden-coverage-measurement.md](./tasks/WP01-broaden-coverage-measurement.md) · **236 lines**

**Goal**: Make each matrix slice measure the full top-level package set, so a test that exercises
another module's code stops having its measurement silently dropped. Establish the baselines every
later acceptance claim reads.

**Priority**: P1 — everything downstream measures against this.

**Independent test**: Run one slice before and after; covered statements outside that slice's own
module go from zero to substantial, and no file's covered set shrinks.

**Why this is not a tidy-first step**: broadening changes which files appear in coverage reports,
which changes the blocking change-coverage gate's *absent* set and its denominator. This WP changes
merge-blocking behaviour for every pull request in the repository. Treat it as the riskiest package,
not the safest.

**Included subtasks**: T001 T002 T003 T004 T005 T006

**Risks**: the aggregate cost could exceed the saving (measured +9.9% on one slice — must be
confirmed across the matrix); artefact size grows ~6×, and the set is downloaded twice.

---

## WP02 — Declare the undeclared test directories

**Lane**: A · **Dependencies**: WP01 · **Prompt**: [tasks/WP02-declare-test-directories.md](./tasks/WP02-declare-test-directories.md) · **174 lines**

**Goal**: Give `tests/unit` and `tests/specify_cli/runtime` a declared home in the test inventory, so
retiring the duplicate step does not remove their per-change execution.

**Priority**: P2 — they retain scheduled coverage, so nothing becomes wholly unrun.

**Independent test**: the inventory names both directories; a pull request runs their tests; the
balancing guard passes against freshly measured data.

**Included subtasks**: T007 T008 T009 T010 T011 T012

**Risks**: a length mismatch between measured durations and collected tests silently degrades
balancing to a test-count split and **no gate notices**; the original capture tooling no longer
exists in-tree, so it must be re-authored rather than re-run.

---

## WP03 — Teach the gate model to see indirect suite invocations

**Lane**: B · **Dependencies**: none · **Prompt**: [tasks/WP03-detector-substrate.md](./tasks/WP03-detector-substrate.md) · **150 lines**

**Goal**: The duplicate-detection substrate is documented as structurally blind to the retiring
step's invocation form. Close that blindness **while the step still exists**, so the regression
battery can be proven against reality.

**Priority**: P1 — a battery built on the blind substrate is vacuous by construction.

**Independent test**: the model resolves a suite invocation reached through a make target or a
script, and the workflow that carries the retiring step enters the detected set.

**Included subtasks**: T013 T014 T015 T016 T017

**Risks**: widening detection pulls a new workflow into a set-equality invariant, cascading into the
coherence model — that cascade is the point, but it must be landed deliberately.

---

## WP04 — Permanent regression battery

**Lane**: B · **Dependencies**: WP03 · **Prompt**: [tasks/WP04-regression-battery.md](./tasks/WP04-regression-battery.md) · **168 lines**

**Goal**: A permanent in-tree fault-injection battery that fails on every way the duplicate could
return, and on removal of the two declarations that keep the report advisory.

**Priority**: P1 — this is the mission's close-the-defect-class-by-construction obligation.

**Independent test**: each mutation is demonstrated red; the unmutated live tree is clean; the rule's
workflow set is asserted non-empty.

**Included subtasks**: T018 T019 T020 T021 T022

**Risks**: a battery fed only synthetic fixtures reproduces the blindness it was written to close —
mutations 1-3 must run against the live tree while the retiring step is still present.

---

## WP05 — The reporting job

**Lane**: B · **Dependencies**: WP04 · **Prompt**: [tasks/WP05-reporting-job.md](./tasks/WP05-reporting-job.md) · **201 lines**

**Goal**: Add the per-change reporting job to the aggregation workflow, consuming the measurement the
matrix already produced, under an execution condition whose every conjunct is independently asserted.

**Priority**: P1 — the mission's functional core.

**Independent test**: the extracted condition evaluator refuses each of the five ways the job must
not run, driven by synthetic payloads, before the job exists.

**Included subtasks**: T023 T024 T025 T026 T027

**Risks**: the analysis configuration must resolve from trusted content — an earlier design that
placed sources in a subdirectory was refuted because the configuration file is located relative to
the analysis base directory. The production trigger cannot execute before integration; that limit is
declared, and the first post-integration run is observed, not assumed.

---

## WP06 — Retire the duplicate, execute dispositions, move the documents

**Lane**: B · **Dependencies**: WP05 · **Prompt**: [tasks/WP06-retire-and-disposition.md](./tasks/WP06-retire-and-disposition.md) · **181 lines**

**Goal**: Remove the duplicate-measurement job, and relocate, rewrite or deliberately retire every
rule that pinned the old arrangement — via a derived inventory, never a transcribed one.

**Priority**: P1 — this is where the cost saving is realised.

**Independent test**: re-running the derivation reproduces the committed inventory; every rule
carries a disposition; the duplicate no longer runs.

**Included subtasks**: T028 T029 T030 T031 T032

**Risks**: rules that go **red** are found by CI; rules that go **greener by deletion** are found by
nobody. The earlier hand-built inventory was ~4× understated with four false positives — which is
exactly why this WP derives rather than transcribes.

---

## Parallelisation

- **Lane A and Lane B run concurrently.** Disjoint file sets; neither reads the other's surfaces.
- Within lanes the order is strict. The mission is genuinely mostly sequential and the plan does not
  manufacture parallelism that does not exist.
- **MVP scope**: WP01 alone delivers the measurement-accuracy half and is independently valuable.
  WP03 + WP04 alone deliver the regression guard. The cost saving needs the full Lane B chain.

## Recording progress

Subtask completion is event-sourced. Use:

```bash
spec-kitty agent tasks mark-status T001 T002 --status done
```

There are no checkboxes to tick; the reduced event log is the authority.
