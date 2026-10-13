---
title: CLI Acceptance Scenarios (Cucumber-JVM nightly)
description: How to write, run and read the Gherkin acceptance scenarios that check the built spec-kitty CLI every night on Linux, macOS and Windows.
doc_status: active
updated: '2026-10-13'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/testing/index.md
- docs/development/testing/testing-flakiness.md
- docs/adr/4.x/2026-10-11-3-acceptance-testing-and-bdd-support.md
---

# CLI Acceptance Scenarios (Cucumber-JVM nightly)

The acceptance scenarios check what the `spec-kitty` CLI promises its users, from the
outside. They run the CLI built from the commit as a separate process and look only at
what a user would see: files, exit codes and git state. A broken promise turns the
nightly red on every supported operating system.

| Part | Location |
|------|----------|
| Scenarios (Gherkin) | `tests/scenarios/<area>/*.feature` |
| Runner, step definitions, driver | `acceptance-jvm/` (Gradle, Cucumber-JVM 7, Java 25) |
| Nightly job | `acceptance-bdd` in `.github/workflows/ci-nightly.yml` |
| Decision record | ADR `2026-10-11-3` (acceptance testing and BDD support) |

## Write a scenario

1. Pick a promise the CLI makes to its users, such as a sentence from a command's
   `--help` text. Name it in the scenario file's maintainer notes.
2. Write the scenario from the user's point of view: what they have, what they run,
   what they get. Leave test mechanics out of the `Feature` and `Scenario` text.
3. Order the steps Arrange, Assume, Act, Assert (see below), and reuse existing steps
   before adding new ones.
4. Give the scenario a same-fixture positive control, so a command that did nothing
   cannot pass it. For example, "the folder `.claude/skills` exists" proves that `init`
   actually ran before "the file `.kittify/config.yaml` is unchanged" can mean anything.

`tests/scenarios/README.md` lists the available steps.

## Step structure: Arrange, Assume, Act, Assert

Each lifecycle group has its own step class in the `kitty.acceptance.steps`
package of the `acceptance-jvm` test sources. They share one
`ScenarioContext` per scenario, injected by Cucumber's PicoContainer integration.

| Group | Gherkin | Class | Does |
|-------|---------|-------|------|
| Arrange | `Given` | `ArrangeSteps` | Builds the starting conditions and fails fast when that did not work. |
| Assume | `Given` / `And` | `AssumeSteps` | Checks that the starting state is what the scenario expects, and records it for later comparison. |
| Act | `When` | `ActSteps` | Runs the command under test. |
| Assert | `Then` / `And` | `AssertSteps` | Checks the post-conditions. |

Steps talk to the CLI only through the `SpecKittyDriver` port and never import Python
code. Assertions use AssertJ.

## Tags

| Tag | Rule |
|-----|------|
| `@promise:<id>` | Names the promise the scenario checks. `<id>` matches `[A-Za-z0-9][A-Za-z0-9._-]*`, for example `PR-CLI-INIT-001`. Not repeated on one scenario. |
| `@wip` | Draft or under repair. Needs `@wip-owner:<handle>` and `@wip-since:<YYYY-MM-DD>`. Runs in a separate non-gating step that never fails the leg. |
| `@wip-owner:<handle>` | Owner of the draft. `<handle>` matches `[A-Za-z0-9][A-Za-z0-9._-]*`. |
| `@wip-since:<YYYY-MM-DD>` | Date the scenario was marked `@wip`. |
| `@manual` | Never runs automatically. |
| `@defect:<issue>` | Links a known defect. `<issue>` is a positive integer. |
| `@qa:<ref>` | Reference for the QA repository. `<ref>` uses the identifier character set. |
| `@<bare>` | Bare tag matching `[A-Za-z0-9][A-Za-z0-9_-]*`, with no `:`. |
| none | Runs in the gating nightly. A failure fails that OS leg. |

Any other tag containing `:` is an error. Tags on a `Feature` or `Rule` apply to every
scenario under it, and tags on an `Examples:` block apply to the rows of that table. Everything except `@wip` and `@manual` gates the nightly.

### Linking a scenario to a promise

A scenario links to a promise by identifier only, with `@promise:<id>`. The scenario
carries no promise wording, rationale or status. This repository checks the shape of the
identifier and nothing more; resolving it to a promise happens in the QA repository.

### Drafted scenarios

A scenario drafted from a promise page lands as `@wip`, with its `@promise:<id>` tag,
`@wip-owner` and `@wip-since`. It may use steps that have no binding yet. An engineer
then binds the steps, adds a positive control and removes `@wip`. Tooling never invents
an identifier.

### Per-PR check

`tests/architectural/test_scenario_contract.py` validates the feature files, the tags and
the step bindings on every pull request. A feature file with no scenario fails it with
`NO_SCENARIOS`, so a misspelt `Scenario:` keyword cannot hide its steps as description
text. Run it locally with:

```bash
uv run --frozen pytest -q tests/architectural/test_scenario_contract.py
```

The gating run has no retries. A flaky scenario is a defect to fix, not to retry
(see [the flakiness policy](testing-flakiness.md)).

## Run the scenarios locally

You need JDK 25 and the pinned Gradle. Install Gradle with the shared installer, which
checks the download against its pinned sha256:

```bash
python contracts/tools/install_tools.py --pins acceptance-jvm/tools/pins.json --dest "$HOME/.cache/spec-kitty-tools" --only gradle
export PATH="$HOME/.cache/spec-kitty-tools/gradle-8.14.5/bin:$PATH"
gradle -p acceptance-jvm test --no-daemon -Pacceptance.pass=gating
```

`-Pacceptance.pass=gating` runs `not @wip and not @manual`; `-Pacceptance.pass=wip` runs the
`@wip` scenarios. The property selects the tag filter and the output folder together.

The runner builds a wheel from your checkout with `uv build` and installs it into a
throwaway virtual environment, so it tests your working tree as a user would install
it. Each scenario gets its own temporary directory, home directory and git repository.

Each pass writes only under `acceptance-jvm/build/acceptance/<pass>/`, so running `wip`
after `gating` leaves the gating results untouched:

- JUnit XML: `acceptance-jvm/build/acceptance/<pass>/junit/`
- Cucumber JSON: `acceptance-jvm/build/acceptance/<pass>/cucumber.json`
- Allure results: `acceptance-jvm/build/acceptance/<pass>/allure-results/`

The nightly's evidence script also writes `acceptance-jvm/build/acceptance/evidence.json`,
counted from the JUnit XML of both passes.

A gating run fails if no scenario ran, so a mistyped tag filter or a wrong feature path
cannot pass as green. Only the `@wip` run may find none.

Each scenario also checks its own isolation. The CLI must write something under the
redirected home directory, which shows the environment redirection took effect. The real
`~/.spec-kitty` must be left untouched. Lock files are ignored in that comparison,
because another `spec-kitty` process on your machine may touch them.

## View the Allure report

`acceptance-jvm/build/acceptance/gating/allure-results/` holds raw result JSON, not a report you can open in a
browser. Turn it into the HTML report with the Allure command-line tool. If you have it
installed, `serve` builds the report into a temporary directory and opens it:

```bash
allure serve acceptance-jvm/build/acceptance/gating/allure-results
```

Without a local install, run the same tool through `npx` (it needs a JDK on `PATH`):

```bash
npx allure-commandline serve acceptance-jvm/build/acceptance/gating/allure-results
```

To keep the report rather than serve it from a temporary directory, generate it into a
folder and open that folder:

```bash
allure generate acceptance-jvm/build/acceptance/gating/allure-results --clean -o acceptance-jvm/allure-report
allure open acceptance-jvm/allure-report
```

The nightly does not build this report; it uploads the raw Allure results inside the
`acceptance-bdd-results-<os>` artifact. To view a nightly run as a report, download that
artifact and run one of these commands on its `gating/allure-results/` directory.

## Change a dependency

`acceptance-jvm/gradle/verification-metadata.xml` pins every dependency by sha256. It is
generated, never edited by hand. After changing `acceptance-jvm/build.gradle`, regenerate
it and commit the result:

```bash
gradle -p acceptance-jvm --write-verification-metadata sha256 test --no-daemon
```

`acceptance-jvm` declares no Gradle version of its own and commits no wrapper; the
nightly installs Gradle from `acceptance-jvm/tools/pins.json`. The nightly's pin-guard
step runs `contracts/tools/gradle_pin_check.py`, which for `acceptance-jvm` checks only
that the `url` in `pins.json` carries the pinned `version` (and a `gradle-version:` input
of the `acceptance-bdd` job, if one is ever added). It does not check the plugin or
dependency pins; the sha256 `verification-metadata.xml` covers those.

## Read a nightly failure

The `acceptance-bdd` job runs once per OS. Open the failed leg, then download its
`acceptance-bdd-results-<os>` artifact. The Cucumber JSON and JUnit XML name the failed
step and carry its assertion message, including the command's output. The spec-kitty-qa
nightly also collects these results.
