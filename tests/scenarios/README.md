# CLI acceptance scenarios

Gherkin scenarios that check what the `spec-kitty` CLI promises its users. They run
every night against the CLI built from the commit, on Linux, macOS and Windows, through
the Cucumber-JVM runner in [`acceptance-jvm/`](../../acceptance-jvm/README.md).

How to write, run and debug them:
[CLI acceptance scenarios](../../docs/development/testing/acceptance-scenarios.md).

## Layout

One folder per CLI area, one or more `.feature` files per folder:

| Folder | Covers |
|--------|--------|
| `init/` | `spec-kitty init`: setting up Spec Kitty in a new or existing repository |
| `mission/` | Mission status: looking up a Mission by name |

## Available steps

Steps follow Arrange, Assume, Act, Assert. Reuse these before adding new ones.

| Group | Step |
|-------|------|
| Arrange | `Given a project already set up with Spec Kitty for the agents "<agents>"` |
| Arrange | `Given an existing git repository with commit history` |
| Arrange | `Given the folder "<path>" has been deleted` |
| Arrange | `Given a project with a mission "<name>"` |
| Arrange | `Given the project also has a mission "<name>"` |
| Arrange | `Given the status of the mission "<name>" can be read` |
| Assume | `Given the folder "<path>" is present` |
| Assume | `Given the file "<path>" is present` |
| Assume | `Given the repository has at least one commit` |
| Act | `When I run "<command line>"` |
| Assert | `Then the command succeeds` |
| Assert | `Then the command fails` |
| Assert | `Then the mission "<name>" is listed` |
| Assert | `Then the mission "<name>" is not listed` |
| Assert | `Then the folder "<path>" exists` |
| Assert | `Then the folder "<path>" is not empty` |
| Assert | `Then the folder "<path>" is unchanged` |
| Assert | `Then the file "<path>" is unchanged` |
| Assert | `Then no "<name>" folder exists in "<path>"` |
| Assert | `Then the repository HEAD is unchanged` |
| Assert | `Then the repository has no new commits` |

Paths are relative to the scenario's working directory. "Unchanged" compares against
the state an Assume step recorded.

## Tags

| Tag | Rule |
|-----|------|
| `@promise:<id>` | Names the product promise the scenario checks. `<id>` matches `[A-Za-z0-9][A-Za-z0-9._-]*`, for example `PR-CLI-INIT-001`. Not repeated on one scenario. This repository checks the shape only. |
| `@wip` | Scenario is being drafted or fixed. Needs `@wip-owner:<handle>` and `@wip-since:<YYYY-MM-DD>` (a valid date). |
| `@wip-owner:<handle>` | Who owns the draft. `<handle>` matches `[A-Za-z0-9][A-Za-z0-9._-]*`. |
| `@wip-since:<YYYY-MM-DD>` | Date the scenario was marked `@wip`. |
| `@manual` | Never runs automatically. |
| `@defect:<issue>` | Links a known defect. `<issue>` is a positive integer. |
| `@qa:<ref>` | Reference for the QA repository. `<ref>` uses the identifier character set above. |
| `@<bare>` | Any bare tag matching `[A-Za-z0-9][A-Za-z0-9_-]*`, with no `:`. |

Any other tag containing `:` is an unknown prefixed tag and is an error.

Every scenario except those tagged `@wip` or `@manual` gates the nightly. `@wip`
scenarios run without failing it. Tags on a `Feature` or `Rule` apply to all scenarios
under it.

The per-PR check in `tests/architectural/test_scenario_contract.py` enforces this
vocabulary.
