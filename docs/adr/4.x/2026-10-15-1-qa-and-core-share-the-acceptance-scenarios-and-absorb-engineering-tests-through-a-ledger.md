---
title: 'ADR: QA and core share ownership of the acceptance scenarios, and engineering tests move into them only through a checked ledger'
description: 'QA and core co-own tests/scenarios and core owns the runner; integration and e2e tests retire into gating scenarios via a checked ledger, and red nights escalate.'
status: Proposed
date: '2026-10-15'
---

**Status:** Proposed, 2026-10-15. Needs the owner's acceptance. Decision 5 also needs the agreement of the spec-kitty-qa lead, because it settles open item 3 of spec-kitty-qa ADR-0001.

**Date:** 2026-10-15

**Deciders:** Stijn Dejongh (owner), with the spec-kitty-qa maintainers.

**Technical Story:** epic [#6101](https://github.com/spec-kitty/spec-kitty/issues/6101). Follows [ADR 2026-10-11-3](2026-10-11-3-acceptance-testing-and-bdd-support.md) and [ADR 2026-10-13-1](2026-10-13-1-acceptance-scenarios-link-to-promises-by-identifier-only.md). The plan it governs is the [test-pyramid rebalance plan](../../development/testing/test-pyramid-rebalance.md).

**Reader:** a maintainer or QA engineer who needs to know who owns an acceptance scenario, how a scenario reaches `main`, and when an engineering test may be deleted because a scenario now checks the same thing.

---

## Context and Problem Statement

The acceptance system exists: Gherkin scenarios in `tests/scenarios/`, the Cucumber-JVM runner in `acceptance-jvm/`, a per-pull-request contract check and the nightly `acceptance-bdd` job on Linux, macOS and Windows. Next to it, `tests/integration` (177 files, 64,552 lines) and `tests/e2e` (7 files, 3,264 lines) carry most of the end-to-end coverage, run only in the nightly (`integration-next`, `e2e`) and name no promise.

Four questions were unanswered:

1. **Ownership.** spec-kitty-qa ADR-0001 says QA owns scenarios and engineers own step code, but nothing in this repository says so. `.github/CODEOWNERS` gives every path to one maintainer.
2. **Absorption.** Nothing defines when an integration or e2e test may be deleted because a scenario covers it. Without a rule, a deleted test is coverage lost without trace, and a duplicated one is cost paid twice.
3. **Signal.** A red `integration-next` or `e2e` night opens a deduplicated P0 issue (`scripts/ci/nightly_escalation.py`). A red `acceptance-bdd` night fails the run, but files nothing, so coverage moved into a scenario would lose its escalation.
4. **Pyramid.** No document says which layer a test belongs in.

The audit behind this ADR classified all 184 files (the [inventory](../../development/testing/integration-e2e-inventory.md)). Most need internals (monkeypatching, fault injection, hand-made internal state) and stay pytest. A minority can be checked black-box today. Much of the rest needs a Mission with finalized work packages, which needs authored content (spec, tasks and work-package files), which ADR 2026-10-13-1 decision 5 does not allow in a builder.

## Decision Drivers

* No net loss of coverage: every retired test is accounted for, and the account is checked by a machine on every pull request.
* No feedback moves later: only tests whose signal already arrives nightly may move into the nightly scenarios.
* One owner per kind of artefact, and a review flow that asks the right people.
* Scenarios stay black-box (ADR 2026-10-13-1): steps drive the built CLI as a process.
* Gates that can fail: every new rule has a planted case that must fail it (charter Standing Order 5).

## Considered Options

1. **Shared ownership, a checked absorption ledger, nightly-only eligibility, one escalation** (chosen).
2. **Move all end-to-end coverage to spec-kitty-qa.** Rejected: a core change could no longer fix its own failing test in the same pull request (spec-kitty-qa ADR-0001 rejected the same move for the nightly).
3. **Delete integration tests on review judgement alone, without a ledger.** Rejected: nothing would show that a deleted file was absorbed rather than dropped.
4. **Tag Python tests with the scenario that absorbs them, and keep both.** Rejected: ADR 2026-10-11-3 says a test is either a scenario or an engineering test, never both, and keeping both pays for the coverage twice.
5. **Escalate once per operating system.** Rejected: a product break usually turns every leg red and would file three P0 issues; the escalation script also needs a bare `python3`, which the Windows leg does not have.

## Decision Outcome

**Chosen option:** option 1.

1. **Ownership boundary.**
   - **Shared by QA and core:** the scenarios (`tests/scenarios/**`, including the absorption ledger), the [scenario-writing guide](../../development/testing/acceptance-scenarios.md) and the [rebalance plan](../../development/testing/test-pyramid-rebalance.md). `.github/CODEOWNERS` names `@stijn-dejongh`, `@kentonium3` and `@Ivan-Melck` for them.
   - **Core engineers:** the runner, step definitions, driver and fixture builders (`acceptance-jvm/**`), named `@stijn-dejongh`.
   - **spec-kitty-qa:** promise pages, the promise index, the trace lint and the Allure report (ADR 2026-10-13-1).

   `tests/architectural/test_scenario_contract.py` checks these CODEOWNERS rules with the last-matching-rule semantics of `contracts/tools/codeowners_check.py`, so a later rule cannot silently take a path away. GitHub review through CODEOWNERS stays advisory; making code-owner review required is a repository setting the operator decides.
2. **Authoring and review flow.**
   - QA drafts a scenario from a promise, by hand or with AI help, and opens a pull request here. A drafted scenario lands as `@wip` with `@wip-owner` and `@wip-since`.
   - An engineer binds its steps and adds a positive control.
   - The `@wip` tag is removed in a pull request that both a QA owner and a core owner reviewed.
   - An engineer who absorbs an engineering test writes the scenario untagged, and asks QA to review its wording.
   - The `When` wording question (#6098) is not decided here; scenarios keep the generic `When I run "<command line>"` step until it is.
3. **Absorption rule.** An engineering test from `tests/integration` or `tests/e2e` is retired only in the pull request that adds its replacement, and only with a row in `tests/scenarios/absorption-ledger.json`. The replacement is either a gating scenario that asserts at least what the test asserted, on an equal or stronger arrange, or, for a duplicate, the surviving pytest tests that already do.
   - The row's `note` says what changed in the arrange and what the replacement does not cover.
   - The ledger freezes a baseline: the 184 test files of the two trees on 2026-10-15.
   - `scripts/ci/absorption_ledger.py` runs on every pull request through `test_scenario_contract.py`. It fails when:
     - a retired test still exists;
     - a replacement scenario is missing, `@wip` or `@manual`;
     - a replacement pytest test is missing;
     - a row is duplicated, or names a file outside the baseline;
     - a baseline file disappears without a whole-file row.
   - Reviewers check that the assertions carried over; the machine cannot.
   - Removing one test function from a kept file without a row is not detected. That gap is accepted, and reviewers check it.
4. **Eligibility.** Only tests whose feedback already arrives nightly may be absorbed:
   - `tests/integration`, which runs only in `integration-next`;
   - `tests/e2e`, which runs on a pull request only when its own files change.

   A test that runs on every pull request is not absorbed: moving it would delay its signal to the next morning. It may still gain a scenario next to it when the scenario checks a promise.
5. **Signal parity.** The new `acceptance-bdd-escalation` job in `ci-nightly.yml` turns a red `acceptance-bdd` run on `main` into one deduplicated P0 issue under the suite key `acceptance-bdd`. It closes the issue on the next green run. Both jobs are in `nightly-summary.needs`.

   This **amends ADR 2026-10-11-3**, which treated the core job as an artefact producer only. It also **proposes an answer to open item 3 of spec-kitty-qa ADR-0001** (issue routing): a red acceptance run files into this repository under that one key, and the spec-kitty-qa acceptance nightly reuses the key rather than opening a second issue for the same red. If spec-kitty-qa disagrees, only the key and the owner of the filing change; the escalation stays.
6. **Authored content in Arrange (decided, operator ruling 2026-10-15).** A scenario builder may write
   the files an agent authors during `specify`, `plan` and `tasks` (`spec.md`, `plan.md`, `tasks.md`,
   `tasks/WP*.md`), the code a work package's implementer writes in its checkout, a reviewer's
   feedback file outside the repository, and plain files a user edits in git (a tracked file, an
   untracked stray file). It still never writes CLI-managed state: `meta.json`, the status log,
   `lanes.json`, review-cycle records, or anything under `.kittify/`. This **amends decision 5 of
   ADR 2026-10-13-1**, which allowed no file writes at all; its purpose (a builder breaks when the
   CLI's own path breaks) holds, because every state change still goes through the CLI. Planning
   happens on a topic branch, because Spec Kitty refuses planning commits on the protected primary
   branch, which is also what a user does.

### Consequences

#### Positive

* Every retired test has a checked row; a deletion without one fails the pull request.
* Absorbed coverage runs against the built wheel on three operating systems instead of one, and escalates like the suite it left.
* A scenario change asks QA and core for review, and the ownership rule cannot drift silently.

#### Negative

* Contributors deleting or renaming a baseline file must add a ledger row.
* The ledger only grows; it is the history of the move.
* Lifecycle tests that need an owned checkout, a mergeable or approved Mission, or crafted older-version state are still to move or stay; the waves so far took `tests/integration` from 177 to 151 files and 64,552 to 58,874 lines, and `tests/e2e` from 7 to 4 files.

#### Neutral

* New tests added to `tests/integration` or `tests/e2e` after the baseline are not tracked by it.
* The release gate already read the whole nightly run, so a red acceptance run already blocked a release; only the escalation is new.

### Confirmation

* `tests/architectural/test_scenario_contract.py` passes on the real tree, and each planted ledger fails its own rule.
* The same file fails when a planted CODEOWNERS line takes `tests/scenarios/` away from the shared owners.
* `tests/ci/test_acceptance_bdd_job.py` pins one escalation job with one key, fail-closed, mainline-only, aggregated by `nightly-summary`.
* For every absorbing scenario, putting the guarded defect back turned it red and left the others green: the #4754 abort, sparse-checkout detection, the sparse-checkout preflight of `implement` and `consolidate`, the #4863 no-state abort, the #3716 discard provenance, the #840 schema stamp, the not-initialised gate, the single-branch review commit gate, the empty-feedback refusal (both layers), the declared reviewer, the occupied and dirty write checkout, and the kept ref of a discarded Mission branch.
* `acceptance-jvm/build.gradle` declares the test task never up to date, because the wheel under test is built at run time from a checkout Gradle does not track; without that, a re-run after a source change reported the previous results.

## More Information

* [Test-pyramid rebalance plan](../../development/testing/test-pyramid-rebalance.md): layers, decision rules, waves and metrics.
* [Integration and e2e inventory](../../development/testing/integration-e2e-inventory.md): the per-file audit of 2026-10-15.
* [CLI acceptance scenarios](../../development/testing/acceptance-scenarios.md): how to write, run and absorb.
