# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty mission close --help` for `--discard` (#3716): discarding a Mission tears down
#   its coordination worktree, records the Mission as abandoned (never as completed) and commits that
#   record, so the working tree is left clean.
# - Mission state is built only through the CLI; the user's own files are committed with plain git.
# - Absorbs tests/integration/test_issue_3716_discard_transactional_close_guard.py (the clean-tree and
#   provenance cases) and tests/integration/test_mission_close_discard_single_branch.py (the discard from
#   the minted mission branch, #5100, and the dirty-checkout refusal); see
#   tests/scenarios/absorption-ledger.json. The single-branch Missions are planned with the authored
#   planning files ADR 2026-10-15-1 decision 6 allows.
# - Untagged, so the scenario runs in the gating nightly.

Feature: Discard a Mission
  As a developer who decides not to finish a Mission
  I want `spec-kitty mission close --discard` to put the Mission away honestly
  So that it is recorded as abandoned, not completed, and nothing is left uncommitted

  Scenario: Discarding a Mission records it as abandoned and leaves a clean working tree
    Given a project with a mission "discard-demo"
    And every change in the project is committed
    When I run "spec-kitty mission close --mission discard-demo --discard --force"
    Then the command succeeds
    And the output mentions "discarded"
    And the working tree has no uncommitted changes
    And the file "retrospective.yaml" of the mission "discard-demo" mentions "kind: runtime_abandoned"
    And the file "retrospective.yaml" of the mission "discard-demo" does not mention "kind: runtime_post_completion"

  @lifecycle
  Scenario: Discarding a single-branch Mission returns me to the primary branch and keeps a way back
    Given a single-branch mission "discard-demo" planned for the primary branch with the work packages "WP01"
    And the tip of the mission branch of mission "discard-demo" is recorded
    When I run "spec-kitty mission close --mission discard-demo --discard --force"
    Then the command succeeds
    And the output mentions "commit(s) that exist on no other branch will be deleted"
    And the output mentions "Deleted mission/coordination branch"
    And the output does not mention "lane branch(es)"
    And the current branch is "main"
    And the mission branch of mission "discard-demo" no longer exists
    And the old tip of the mission branch of mission "discard-demo" can be restored from its kept ref
    And the working tree has no uncommitted changes to tracked files
    And the branch "main" has no folder of mission "discard-demo"

  @lifecycle
  Scenario: Discarding a single-branch Mission from a checkout that cannot leave its branch deletes nothing
    Given a single-branch mission "discard-demo" planned for the primary branch with the work packages "WP01"
    And the file "README.md" is committed with the text "an edit on the mission branch"
    And the file "README.md" has the uncommitted text "an edit I have not committed"
    And the file "README.md" is present
    When I run "spec-kitty mission close --mission discard-demo --discard --force"
    Then the command fails
    And the output mentions "cannot discard"
    And the mission branch of mission "discard-demo" still exists
    And the current branch is the mission branch of mission "discard-demo"
    And the file "README.md" is unchanged
