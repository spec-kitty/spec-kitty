# Maintainer notes (not part of the behaviour description):
# - Each scenario restates a promise from `spec-kitty upgrade --help`
#   (src/specify_cli/cli/commands/upgrade.py, the module docstring's flag surface).
# - Steps follow Arrange / Assume / Act / Assert; see tests/scenarios/README.md.
# - Tagging: the three untagged scenarios (git history untouched, dry-run preview,
#   settings preserved) pass on Linux, macOS and Windows today, so they gate the
#   nightly. The two `@wip` scenarios describe re-running upgrade to converge or
#   repair a project that was already set up; that convergence is not green on
#   Windows yet (defect #6228), so they run without gating until it is fixed.

Feature: Keep a Spec Kitty project up to date
  As a developer who already adopted Spec Kitty
  I want `spec-kitty upgrade` to refresh my project without touching my git history or my own settings
  So that I can stay current, re-run it safely, and have it repair a damaged setup

  Scenario: Upgrading an already-set-up project leaves its git history alone
    Given an existing git repository with commit history
    And a project already set up with Spec Kitty for the agents "claude"
    And the repository has at least one commit
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the repository HEAD is unchanged
    And the repository has no new commits

  Scenario: A dry-run upgrade reports what it would change without touching the project
    Given an existing git repository with commit history
    And a project already set up with Spec Kitty for the agents "claude"
    And the file ".kittify/config.yaml" is present
    And the repository has at least one commit
    When I run "spec-kitty upgrade --dry-run"
    Then the command succeeds
    And the file ".kittify/config.yaml" is unchanged
    And the repository HEAD is unchanged
    And the repository has no new commits

  Scenario: Upgrading keeps my own project settings exactly as I left them
    Given a project already set up with Spec Kitty for the agents "claude,codex"
    And the file ".kittify/config.yaml" is present
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the folder ".claude/skills" exists
    And the folder ".claude/skills" is not empty
    And the file ".kittify/config.yaml" is unchanged

  @wip @wip-owner:spec-kitty @wip-since:2026-10-16 @defect:6228
  Scenario: Re-running upgrade restores a missing managed folder and keeps the rest of the project as it was
    Given a project already set up with Spec Kitty for the agents "claude,codex"
    And the folder ".claude/skills" has been deleted
    And the folder ".agents/skills" is present
    And the file ".kittify/config.yaml" is present
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the folder ".claude/skills" exists
    And the folder ".claude/skills" is not empty
    And the folder ".agents/skills" is unchanged
    And the file ".kittify/config.yaml" is unchanged

  @wip @wip-owner:spec-kitty @wip-since:2026-10-16 @defect:6228
  Scenario: Running upgrade again on an already-upgraded project changes nothing further
    Given a project already set up with Spec Kitty for the agents "claude,codex"
    And the folder ".claude/skills" is present
    And the file ".kittify/config.yaml" is present
    When I run "spec-kitty upgrade --yes"
    And I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the folder ".claude/skills" is unchanged
    And the folder ".claude/skills" is not empty
    And the file ".kittify/config.yaml" is unchanged
