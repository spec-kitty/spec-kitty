---
title: 'ADR: acceptance scenarios link to product promises by identifier only; core checks the scenario contract per pull request and hands on versioned evidence'
description: 'Scenarios cite promises only by @promise identifier; a JDK-free per-PR check validates feature files, tags and step bindings; nightly legs upload versioned evidence.'
status: Accepted
date: '2026-10-13'
---

**Status:** Accepted, accepted by the owner on 2026-10-13

**Date:** 2026-10-13

**Deciders:** Stijn Dejongh (owner), with the spec-kitty-qa maintainers for the evidence contract.

**Technical Story:** follows [ADR 2026-10-11-3](2026-10-11-3-acceptance-testing-and-bdd-support.md) and its 2026-10-11 amendment. The QA half is spec-kitty-qa ADR-0001 and ADR-0002. Design: [the acceptance scenario contract](../../architecture/acceptance-scenario-contract.md).

**Reader:** a maintainer deciding what this repository owns about acceptance scenarios, and what it hands to spec-kitty-qa.

---

## Context and Problem Statement

ADR 2026-10-11-3 put Gherkin scenarios in `tests/scenarios/` and a Cucumber-JVM nightly in
`acceptance-jvm/`. Its amendment moved the promise index, the per-PR promise-tag check and the
index sync to spec-kitty-qa, which left `@promise` inert here and the `scenarios` router group
gating nothing.

Four problems remain:

1. **No stated boundary.** Nothing says what a scenario may carry about a promise. Scenarios are
   about to be drafted from promise pages, with AI help, so wording, rationale or status could
   leak into this public repository.
2. **No per-PR check at all.** A malformed feature file, a bad tag or a step with no binding is
   found only by the next nightly.
3. **Evidence cannot be traced to a build.** The `@wip` pass runs after the gating pass with
   `--rerun-tasks` into the same folders, so it overwrites the gating Cucumber JSON and JUnit XML,
   and mixes both passes' Allure results, before the upload.
   No result records the CLI version, commit, OS or pass, the Allure folder is not set, and the
   artifact has no explicit retention.
4. **Fixtures stop at `init`.** Arrange steps cannot reach a project with a mission in it, so the
   next promises cannot be checked.

## Decision Drivers

* Promise content stays out of the open-core repository.
* Each repository keeps the scenario tooling that suits its stack; no shared format is forced
  across the promise and scenario layers.
* A contributor gets scenario feedback on the pull request, without a JDK.
* Every result names the exact build, OS and pass it came from.
* Scenarios stay black-box: steps drive the CLI as a process.

## Considered Options

1. **Identifier-only link, syntax checked here, evidence bundle per leg** (chosen).
2. **Sync a public promise index into core and check identifiers against it.** This was ADR
   2026-10-11-3's original plan. Rejected by its amendment, and still rejected: it couples core to
   the promise store's lifecycle, and needs a cross-repository token.
3. **Carry the promise slug or title in the tag.** Rejected: slugs are renamed, and titles leak
   promise wording.
4. **Run the JVM suite per pull request.** Rejected: every contributor would pay for a JDK and a
   wheel build on every change, while the per-PR question is only "does this parse, and is every
   step bound?".
5. **Leave evidence as it is, and let spec-kitty-qa infer context from the run.** Rejected: the
   gating results are overwritten before the upload, and the run alone does not say which CLI
   version was built.

## Decision Outcome

**Chosen option:** option 1.

1. **The link is the persistent promise identifier.** A scenario cites a promise only as
   `@promise:<id>`. `<id>` is opaque here and matches `[A-Za-z0-9][A-Za-z0-9._-]*`. No promise
   wording, slug, status or rationale goes into this repository. Resolving identifiers, computing
   coverage and reporting gaps stay in spec-kitty-qa.
2. **Tag vocabulary.** `@promise:<id>`; `@wip` with `@wip-owner:<handle>` and
   `@wip-since:<YYYY-MM-DD>`; `@manual`; `@defect:<issue>`; `@qa:<ref>`; free-form bare tags. A
   drafted scenario lands as `@wip`. Only a person adds a `@promise` tag.
3. **Per-PR scenario check.** `tests/architectural/test_scenario_contract.py`, standard library
   plus first-party `kernel.clock` (no third-party dependency), checks that every feature file parses, every tag follows the vocabulary, and every step
   of a scenario without `@wip` matches exactly one step definition read from the
   `acceptance-jvm` step annotations. It has one broken fixture per rule. The `scenarios` and
   `acceptance_jvm` router groups gate the job that runs it. This narrows the 2026-10-11-3
   amendment's "the `scenarios` group gates no per-PR job"; it does not bring back the promise
   index.
4. **Evidence bundle.** Each pass (gating, `@wip`) writes its own folder under
   `acceptance-jvm/build/acceptance/<pass>/`, with the Allure results folder set explicitly. The
   runner writes Allure `environment.properties` (CLI version, commit, OS, JDK, pass) and
   `executor.json`. The job writes `evidence.json` (`schema_version` 1) per leg. The upload keeps
   the name `acceptance-bdd-results-<os>`, fails when the gating results are missing, and keeps
   them for 30 days. The job's dead `pull_request` condition is removed.
5. **Black-box fixture builders.** Builders that reach a mission state do so only by running the
   CLI through the driver, never by writing project files directly.

### Consequences

#### Positive

* Scenarios can be drafted from promises and published without exposing promise content.
* Broken scenarios and unbound steps are caught on the pull request.
* spec-kitty-qa can attribute every result to a build, an OS and a pass, and the gating evidence
  is no longer overwritten.

#### Negative

* A second, partial Gherkin reader and Cucumber expression matcher exist beside the JVM runner.
  They must follow the runner: an unsupported parameter type fails the check rather than passing.
* The `scenarios` router group now runs a job on scenario-only pull requests.

#### Neutral

* `@promise` identifiers are still not checked for existence here; a typo'd identifier is found by
  spec-kitty-qa's trace lint, not on the pull request.
* The Allure report, its history and the trace lint stay in spec-kitty-qa.

### Confirmation

* `tests/architectural/test_scenario_contract.py` passes on the real tree, and each broken fixture
  fails its rule.
* A nightly leg's artifact holds `gating/` and `wip/` folders, an `evidence.json` with the commit
  and CLI version, and Allure results with `environment.properties`.
* `grep -r "promise" tests/scenarios` finds only `@promise:<id>` tags and guide text, no promise
  wording.

## More Information

* [The acceptance scenario contract](../../architecture/acceptance-scenario-contract.md): the
  design, including the fixture builders.
* [CLI acceptance scenarios](../../development/testing/acceptance-scenarios.md): how to write and
  run scenarios today.
