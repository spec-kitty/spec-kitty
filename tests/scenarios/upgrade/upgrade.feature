# Maintainer notes (not part of the behaviour description):
# - Each scenario restates a promise from `spec-kitty upgrade --help`
#   (src/specify_cli/cli/commands/upgrade.py, the module docstring's flag surface).
# - Steps follow Arrange / Assume / Act / Assert; see tests/scenarios/README.md.
# - Tagging: all five scenarios pass on Linux, macOS and Windows today, so they
#   gate the nightly. They describe refreshing, previewing, converging and
#   repairing an already-set-up project. None of them exercises defect #6228
#   (a read-only in-place overwrite via atomic_write): the restore scenario
#   deletes a managed folder and upgrade re-creates it fresh (no read-only
#   destination to replace), and the repeat-upgrade scenario is idempotent
#   (write-if-changed), so neither reaches the os.replace-over-read-only path.
#   #6228 is fixed in atomic_write (it restores the destination write bit before
#   the replace, then re-applies the mode); its regression guard is the
#   win32-only pytest tests/core/test_windows_readonly_overwrite_6228.py plus
#   the cross-platform write-bit assertions in tests/specify_cli/test_atomic_write.py
#   and tests/kernel/test_atomic.py. These black-box scenarios are not that guard.

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
