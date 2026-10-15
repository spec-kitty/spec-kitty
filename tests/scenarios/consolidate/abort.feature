# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty consolidate --help` for `--abort` (src/specify_cli/cli/commands/consolidate.py):
#   it abandons Spec Kitty's own consolidation, never a git merge the user started (#4754).
# - The user's merge is built with plain git: two branches change one file, then one is merged.
# - Absorbs tests/integration/test_merge_abort_scope.py
#   (test_abort_preserves_users_in_progress_merge_when_no_spec_kitty_state) and
#   tests/integration/test_issue_4863_merge_abort_no_state.py (the no-state no-op); see
#   tests/scenarios/absorption-ledger.json.
# - Untagged, so the scenario runs in the gating nightly.

Feature: Abandon a consolidation without touching my own git work
  As a developer who uses git directly next to Spec Kitty
  I want `spec-kitty consolidate --abort` to abandon only Spec Kitty's own consolidation
  So that a merge I am resolving by hand is never thrown away

  Scenario: Aborting when no consolidation is running keeps my in-progress git merge
    Given a project set up with Spec Kitty whose files are committed
    And I have a git merge in progress with a conflict in "file.txt"
    And the file ".git/MERGE_HEAD" is present
    And the file "file.txt" is present
    When I run "spec-kitty consolidate --abort"
    Then the command succeeds
    And the output mentions "No active merge state to abort"
    And the output does not mention "Aborted in-progress git merge"
    And a git merge is still in progress
    And the file ".git/MERGE_HEAD" is unchanged
    And the file "file.txt" is unchanged

  Scenario: Aborting a Mission that has no consolidation running changes nothing
    Given a project with a mission "abort-demo"
    And the repository has at least one commit
    And the repository's branches are recorded
    And the folder ".worktrees" is present
    And the folder "kitty-specs" is present
    When I run "spec-kitty consolidate --abort --mission abort-demo"
    Then the command succeeds
    And the output mentions "No active merge state found"
    And the output does not mention "Workspace cleaned up"
    And the repository HEAD is unchanged
    And the repository's branches are unchanged
    And the folder ".worktrees" is unchanged
    And the folder "kitty-specs" is unchanged
