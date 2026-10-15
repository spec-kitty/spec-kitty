# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty agent mission create --help` and the refusals of `setup-plan`, `implement`
#   and `agent tasks status` when they are given no usable Mission.
# - Mission state is built only through the CLI (`spec-kitty init`, `spec-kitty agent mission create`).
# - Absorbs tests/e2e/test_cli_smoke.py (create, documentation create, bad slug, setup-plan and
#   implement without a Mission) and tests/e2e/test_feature_alias_smoke.py; see tests/scenarios/absorption-ledger.json.
# - The last scenario is new coverage (no Python test checked the refusal through the CLI).
# - Untagged, so every scenario runs in the gating nightly.

Feature: Create a Mission
  As a developer starting a piece of work
  I want `spec-kitty agent mission create` to set up a Mission folder I can specify into
  So that planning starts from a known place, and commands refuse to run without a Mission

  Scenario: A new Mission gets a folder with a spec and a tasks folder, and no work package worktree
    Given a project set up with Spec Kitty whose files are committed
    When I run "spec-kitty agent mission create smoke-test --json"
    Then the command succeeds
    And the JSON field "result" of the output is "success"
    And the mission "smoke-test" is listed
    And the new mission's folder has a "spec.md" file
    And the new mission's folder has a "tasks" folder
    And no work package worktree has been created

  Scenario: A documentation Mission can be created
    Given a project set up with Spec Kitty whose files are committed
    When I run "spec-kitty agent mission create docs-smoke --mission-type documentation --json"
    Then the command succeeds
    And the mission "docs-smoke" is listed
    And the new mission's folder has a "spec.md" file

  Scenario: A Mission name that is not kebab-case is refused
    Given a project set up with Spec Kitty whose files are committed
    When I run "spec-kitty agent mission create Bad_Slug --json"
    Then the command fails
    And the output mentions "Invalid mission slug"
    And the output mentions "kebab-case"
    And no "kitty-specs" folder exists in "."

  Scenario: Setting up a plan without any Mission is refused
    Given a project set up with Spec Kitty whose files are committed
    When I run "spec-kitty agent mission setup-plan --json"
    Then the command fails
    And the output mentions "No missions found"

  Scenario: Implementing a work package without naming a Mission is refused
    Given a project set up with Spec Kitty whose files are committed
    When I run "spec-kitty implement WP99"
    Then the command fails
    And the output mentions "--mission"
    And no work package worktree has been created

  Scenario: The retired --feature option is refused in favour of --mission
    Given a project with a mission "demo-mission"
    And the status of the mission "demo-mission" can be read
    When I run "spec-kitty agent tasks status --feature demo-mission --json"
    Then the command exits with code 2
    And the output mentions "No such option: --feature"

  Scenario: Specifying a Mission in a repository that is not a Spec Kitty project is refused
    Given an existing git repository with commit history
    When I run "spec-kitty specify demo --json"
    Then the command fails
    And the JSON field "error_code" of the output is "SPEC_KITTY_REPO_NOT_INITIALIZED"
    And the output mentions "spec-kitty init"
    And no "kitty-specs" folder exists in "."
