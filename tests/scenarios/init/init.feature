# Maintainer notes (not part of the behaviour description):
# - Each scenario restates a promise from `spec-kitty init --help`
#   (src/specify_cli/cli/commands/init_help.py, INIT_COMMAND_DOC).
# - Steps follow Arrange / Assume / Act / Assert; see tests/scenarios/README.md.
# - The third scenario absorbs tests/integration/test_init_fresh_project_chain.py
#   (test_init_then_next_no_missing_schema_error, #840); see tests/scenarios/absorption-ledger.json.
#   Every non-exempt command passes the project schema gate first, so `next` succeeding is the check.
# - Untagged, so every scenario runs in the gating nightly.

Feature: Set up Spec Kitty in a repository
  As a developer adopting Spec Kitty
  I want `spec-kitty init` to set up my project without touching my git history
  So that I can add Spec Kitty to a new or existing repository, and re-run it to repair a damaged setup

  Scenario: Re-running init repairs a missing agent skill folder and keeps the rest of the project as it was
    Given a project already set up with Spec Kitty for the agents "claude,codex"
    And the folder ".claude/skills" has been deleted
    And the folder ".agents/skills" is present
    And the file ".kittify/config.yaml" is present
    When I run "spec-kitty init --non-interactive --ai claude,codex"
    Then the command succeeds
    And the folder ".claude/skills" exists
    And the folder ".claude/skills" is not empty
    And the folder ".agents/skills" is unchanged
    And the file ".kittify/config.yaml" is unchanged

  Scenario: Setting up a new project inside an existing repository leaves its git history alone
    Given an existing git repository with commit history
    And the repository has at least one commit
    When I run "spec-kitty init app --non-interactive --ai claude"
    Then the command succeeds
    And the folder "app/.kittify" exists
    And the folder "app/.claude" exists
    And no ".git" folder exists in "app"
    And the repository HEAD is unchanged
    And the repository has no new commits

  Scenario: A freshly set up project works with the next command without hand-editing
    Given a project with a mission "demo-mission"
    When I run "spec-kitty next --agent claude --mission demo-mission --json"
    Then the command succeeds
    And the JSON field "kind" of the output is "query"
    And the output does not mention "requires migration"
    And the output does not mention "missing schema"
    And the file ".kittify/metadata.yaml" mentions "schema_version:"
    And the file ".kittify/metadata.yaml" mentions "schema_capabilities:"
