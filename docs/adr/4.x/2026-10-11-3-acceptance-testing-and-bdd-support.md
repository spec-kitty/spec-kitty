---
title: 'ADR: acceptance testing and BDD support with Gherkin scenarios and a black-box Cucumber-JVM runner'
description: 'Promise-tagged Gherkin scenarios live in tests/scenarios, a per-PR Python check guards their tags, and a nightly Cucumber-JVM job drives the built CLI as a black box.'
status: Accepted
date: '2026-10-11'
---

**Status:** Accepted — Amended 2026-10-11 — see [Amendment](#amendment-2026-10-11-owner-ruling); the promise-machinery paragraphs below are narrowed by it (never built in core).

**Date:** 2026-10-11

**Deciders:** Stijn Dejongh (owner), accepted 2026-10-11.

**Technical Story:** the QA promise train (spec-kitty-planning `qa-promise-train/`). Its QA half is spec-kitty-qa ADR-0001 (QA owns the acceptance nightly and the Allure report, amended 2026-10-11) and ADR-0002 (a promise index joins the promise pages to core's scenarios). This ADR is the core half.

**Reader:** a maintainer who needs to know where acceptance scenarios live, what checks them on a pull request, how the nightly runs them, and why the runner is Java while the CLI stays Python.

---

## Context and Problem Statement

Spec Kitty promises behaviour to its users (for example "re-running `init` keeps project state", from `init --help`), but nothing ties a promise to a test that checks it. Core has about 230 Python acceptance and e2e tests (`tests/acceptance`, `tests/e2e`), and the nightly runs them, but none of them names the promise it protects, so a release cannot say which promises it verified. The CLI's own spec template already asks for Given/When/Then, yet core has no `.feature` files and no BDD runner.

The product owner decided on 2026-10-11, after a four-lens design review:

1. Promise pages stay private in spec-kitty-qa; Gherkin scenarios live in this repository; a synced promise index joins them.
2. The runner is Cucumber-JVM, chosen for cross-OS stability and because parts of core (the Mission API, the charter offering and activation) are planned to move to Java modules.
3. A scenario whose steps are not yet bound lands as `@wip` with an owner and an age limit, and does not gate a release.

## Considered Options

1. **pytest-bdd inside the existing Python suite.** Rejected by the product owner in favour of a JVM runner; recorded as rejected in spec-kitty-qa ADR-0001.
2. **Scenarios in spec-kitty-qa.** Rejected: an operator could not open a scenario pull request against the code it describes, and a bug reproduction would not share history with its fix.
3. **Promise pages in this repository too.** Rejected: candidate promise wording would be public.
4. **Java steps that call core's Python or future Java classes directly.** Rejected: ADR 2026-10-01-2 keeps the CLI native and ADR 2026-10-03-1 keeps writes in Python during the strangler, so steps drive the CLI as a process and stay valid on either side.

## Decision

**Scenarios.** Gherkin files live under `tests/scenarios/<area>/`. A scenario cites the promises it checks with `@promise:<id>`. Other tags: `@wip` with `@wip-owner:<handle>` and `@wip-since:<YYYY-MM-DD>` for unbound steps, `@defect:<issue>` for a bug reproduction, `@qa:SC-A-NNN` for a scenario converted from the QA corpus. `tests/scenarios/promise-index.json` is the public slice of spec-kitty-qa's promise index (ratified and retired ids with titles, `schema_version: 1`). It arrives only through a pull request opened by an org-owned token and is never edited by hand.

**Per pull request.** `tests/architectural/test_scenario_promise_tags.py`, stdlib only, asserts:

- a scenario without `@wip` cites at least one `@promise:<id>`, and each id is `ratified` in the index;
- a `@wip` scenario may cite an id the index does not have yet (a candidate);
- no scenario cites a `retired` id;
- `@wip` carries its owner and since tags, and `@defect` carries an issue number.

The test carries one broken fixture per rule. `.github/workflows/ci-router.yml` gains a `scenarios` group (`tests/scenarios/**`) that gates the architectural job, and an `acceptance_jvm` group (`acceptance-jvm/**`) that gates no per-PR job, like the `ci` group. Contributors need no JDK.

**Nightly runner.** A Gradle subproject at `acceptance-jvm/` (the JDK core's Java modules use, Java 25 per the 2026-10-03 amendment of ADR 2026-10-01-2; pinned Gradle distribution, no committed wrapper jar, dependency verification metadata, following `contracts/`) runs the scenarios in place from `../tests/scenarios` with Cucumber-JVM 7 on the JUnit Platform and `allure-cucumber7-jvm`.

- A `SpecKittyDriver` port runs a command and returns exit code, output, parsed `--json` and the working tree. `CliProcessDriver` implements it with `ProcessBuilder`: drained streams, a timeout, descendant processes killed, line endings normalised, real paths compared.
- Each scenario gets a temporary git repository and an isolated environment: `SPEC_KITTY_HOME`, `HOME`, `USERPROFILE`, the XDG directories and `LOCALAPPDATA` inside it, UTF-8, `NO_COLOR` and a fixed `COLUMNS`.
- The CLI under test is a wheel built from the commit (`uv build`) and installed into a temporary venv; never PyPI, never an editable install.
- Steps call only the driver. They never import Python and never use internal Java classes; published contracts (for example `contracts/mission-status/openapi.yaml`) are allowed.

A new `acceptance-bdd` job in `ci-nightly.yml` runs on Linux, macOS and Windows. The gating run filters `not @wip and not @manual`; a separate non-gating run executes bound `@wip` scenarios. No retries. Results (Allure, Cucumber JSON, JUnit XML) are uploaded for the spec-kitty-qa acceptance nightly, which runs the promise trace lint and builds the Allure 3 report.

**Packaging.** The wheel ships only the `src/` packages and is unaffected. The sdist `exclude` gains `acceptance-jvm/**` and `tests/scenarios/**`, asserted in `tests/cross_cutting/packaging/test_packaging_safety.py`.

**One source of promise coverage.** Only `@promise`-tagged scenarios count as promise coverage. `tests/acceptance`, `tests/e2e`, performance, stress and `p0_repro` stay engineering tests. A Python test that already checks a promise either becomes a scenario or stays untagged, never both.

## Consequences

- The release robot needs the core nightly and the spec-kitty-qa acceptance nightly green on the same commit (spec-kitty-qa ADR-0001).
- A breaking CLI change to a promised behaviour turns the next nightly red on three operating systems, not only Linux.
- Until spec-kitty-qa decides who ratifies a promise (QAD-0009), the index has no rows and only `@wip` scenarios can land.
- The same scenarios can later run against a Java implementation by pointing the driver port at it.

## Open Questions

1. The org-owned sync secret (`PROMISE_INDEX_SYNC_TOKEN`) still has to be created, scoped like `CHARTER_SHARD_RECAPTURE_TOKEN` to pull requests on this repository. *(Narrowed out of core — see the Amendment below; this open question is now closed for core and owned by spec-kitty-qa.)*
2. The `@wip` age limit (30 days is a placeholder) is set in the trace lint, not here.

## Amendment (2026-10-11 owner ruling)

**Author:** Stijn Dejongh (owner). **Date:** 2026-10-11.

After acceptance, the owner ruled that the promise-tracking machinery this ADR
specified belongs to **spec-kitty-qa**, not to core. The ruling does not rewrite the
decision above — the Context, Considered Options, Decision and Consequences stay as the
record of what was accepted — it **narrows** the parts that were specified for core but
**never built here**. The following four items are owned by spec-kitty-qa (its ADR-0001
and ADR-0002 are the owning home) and were never added to this repository:

1. **`tests/scenarios/promise-index.json`** — the public promise-index slice (ratified and
   retired ids with titles, `schema_version: 1`). It does not exist in this tree and will not
   be added here.
2. **The per-PR check `tests/architectural/test_scenario_promise_tags.py`** — the stdlib
   check that asserted each `@promise:<id>` is `ratified` in the index (with one broken
   fixture per rule). It was never written in core.
3. **The `PROMISE_INDEX_SYNC_TOKEN` org sync** — the org-owned sync secret of Open Question 1
   above, which would have opened the index-update pull requests. It is not created or scoped
   in core.
4. **Turning a promise into a scenario** (the promise→scenario mapping) — the act of deriving
   a Gherkin scenario from a ratified promise. That mapping lives with the promise pages in
   spec-kitty-qa.

Because none of the four was ever built, this amendment records a **narrowing of a
never-built plan**, not the deletion of code.

### Consequences of the narrowing

- **The `scenarios` ci-router group now gates NO per-PR job.** The accepted Decision had the
  `scenarios` group (`tests/scenarios/**`) gate the architectural job — and that architectural
  job was precisely the dropped promise-tag check (item 2). With the check gone, the group
  gates nothing; it is a deliberately-ungated filter group, like `ci`. The `acceptance_jvm`
  group (`acceptance-jvm/**`) still gates no per-PR job, unchanged.
- **Core keeps the scenarios, the Cucumber-JVM runner and the nightly.** Gherkin files under
  `tests/scenarios/<area>/`, the `acceptance-jvm/` Gradle subproject, the `SpecKittyDriver`
  port and the nightly `acceptance-bdd` job all stay in core as the Decision describes.
- **Tag semantics in core.** `@promise:<id>`, `@defect:<issue>` and `@qa:SC-A-NNN` are
  **inert in core** — there is no index to check them against and no per-PR check reads them.
  Only `@wip` and `@manual` carry meaning: each excludes a scenario from the gating nightly
  run (`not @wip and not @manual`). `@manual` is an allowed tag, reserved for heavy or
  on-demand scenarios.
