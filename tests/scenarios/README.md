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
| `consolidate/` | `spec-kitty consolidate`: refusing under sparse-checkout, and `--abort` without touching the user's own git merge |
| `doctor/` | `spec-kitty doctor sparse-checkout`: finding and reporting legacy sparse-checkout state |
| `implement/` | `spec-kitty agent action implement`: refusing to start work under sparse-checkout |
| `init/` | `spec-kitty init`: setting up Spec Kitty in a new or existing repository |
| `mission/` | Missions: creating one, refusals without a Mission, looking one up by name, and discarding one |

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
| Arrange | `Given a project set up with Spec Kitty whose files are committed` |
| Arrange | `Given sparse-checkout is turned on in the project for "<pattern>,<pattern>"` |
| Arrange | `Given the project has a linked worktree "<path>" with sparse-checkout turned on` |
| Arrange | `Given I have a git merge in progress with a conflict in "<file>"` |
| Arrange | `Given every change in the project is committed` |
| Assume | `Given the folder "<path>" is present` |
| Assume | `Given the file "<path>" is present` |
| Assume | `Given the repository has at least one commit` |
| Assume | `Given the repository's branches are recorded` |
| Act | `When I run "<command line>"` |
| Assert | `Then the command succeeds` |
| Assert | `Then the command fails` |
| Assert | `Then the command exits with code <n>` |
| Assert | `Then the output mentions "<text>"` |
| Assert | `Then the output does not mention "<text>"` |
| Assert | `Then the output is a single line` |
| Assert | `Then the output names the folder "<path>"` |
| Assert | `Then the JSON field "<field>" of the output is "<value>"` |
| Assert | `Then the new mission's folder has a "<name>" file` |
| Assert | `Then the new mission's folder has a "<name>" folder` |
| Assert | `Then no work package worktree has been created` |
| Assert | `Then the git setting "<key>" is "<value>"` |
| Assert | `Then a git merge is still in progress` |
| Assert | `Then the repository's branches are unchanged` |
| Assert | `Then the working tree has no uncommitted changes` |
| Assert | `Then the file "<path>" mentions "<text>"` |
| Assert | `Then the file "<name>" of the mission "<mission>" mentions "<text>"` |
| Assert | `Then the file "<name>" of the mission "<mission>" does not mention "<text>"` |
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
the state an Assume step recorded. "The output" is stdout and stderr together.

## Ownership

QA (spec-kitty-qa) and core share this folder: a change here asks both for review
(`.github/CODEOWNERS`). The runner, step definitions and driver in `acceptance-jvm/` are
core's. See [ADR 2026-10-15-1](../../docs/adr/4.x/2026-10-15-1-qa-and-core-share-the-acceptance-scenarios-and-absorb-engineering-tests-through-a-ledger.md).

## Absorbed engineering tests

`absorption-ledger.json` records every test retired from `tests/integration` or `tests/e2e`
because a scenario here (or a surviving pytest test) now checks the same thing. Add a row in
the pull request that retires the test; the per-PR check fails otherwise. How to move a test:
[test-pyramid rebalance plan](../../docs/development/testing/test-pyramid-rebalance.md).

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
under it; tags on an `Examples:` block apply to the rows of that table.

The per-PR check in `tests/architectural/test_scenario_contract.py` enforces this
vocabulary, the absorption ledger and the ownership rules.
