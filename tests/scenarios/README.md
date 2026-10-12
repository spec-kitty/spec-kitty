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

## Available steps

Steps follow Arrange, Assume, Act, Assert. Reuse these before adding new ones.

| Group | Step |
|-------|------|
| Arrange | `Given a project already set up with Spec Kitty for the agents "<agents>"` |
| Arrange | `Given an existing git repository with commit history` |
| Arrange | `Given the folder "<path>" has been deleted` |
| Assume | `Given the folder "<path>" is present` |
| Assume | `Given the file "<path>" is present` |
| Assume | `Given the repository has at least one commit` |
| Act | `When I run "<command line>"` |
| Assert | `Then the command succeeds` |
| Assert | `Then the folder "<path>" exists` |
| Assert | `Then the folder "<path>" is unchanged` |
| Assert | `Then the file "<path>" is unchanged` |
| Assert | `Then no "<name>" folder exists in "<path>"` |
| Assert | `Then the repository HEAD is unchanged` |
| Assert | `Then the repository has no new commits` |

Paths are relative to the scenario's working directory. "Unchanged" compares against
the state an Assume step recorded.

## Tags

Untagged scenarios gate the nightly. `@wip` runs without failing it. `@manual` never
runs automatically.
