---
title: CLI Acceptance Scenarios (Cucumber-JVM nightly)
description: How to write, run and read the Gherkin acceptance scenarios that check the built spec-kitty CLI every night on Linux, macOS and Windows.
doc_status: active
updated: '2026-10-12'
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

Each lifecycle group has its own step class in
`acceptance-jvm/src/test/java/kitty/acceptance/steps/`. They share one
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

| Tag | Effect |
|-----|--------|
| none | Runs in the gating nightly. A failure fails that OS leg. |
| `@wip` | Runs in a separate non-gating step that never fails the leg. |
| `@manual` | Never runs automatically. |

The gating run has no retries. A flaky scenario is a defect to fix, not to retry
(see [the flakiness policy](testing-flakiness.md)).

## Run the scenarios locally

You need JDK 25 and the pinned Gradle. Install Gradle with the shared installer, which
checks the download against its pinned sha256:

```bash
python contracts/tools/install_tools.py --pins acceptance-jvm/tools/pins.json --dest "$HOME/.cache/spec-kitty-tools" --only gradle
export PATH="$HOME/.cache/spec-kitty-tools/gradle-8.14.5/bin:$PATH"
gradle -p acceptance-jvm test --no-daemon -Dcucumber.filter.tags="not @wip and not @manual"
```

The runner builds a wheel from your checkout with `uv build` and installs it into a
throwaway virtual environment, so it tests your working tree as a user would install
it. Each scenario gets its own temporary directory, home directory and git repository.

Reports land in `acceptance-jvm/build/`: JUnit XML under `test-results/`, Cucumber JSON
under `cucumber-report/`, and Allure results in `acceptance-jvm/allure-results/`.

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
