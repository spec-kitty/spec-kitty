# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty mission close --help` for `--discard` (#3716): discarding a Mission tears down
#   its coordination worktree, records the Mission as abandoned (never as completed) and commits that
#   record, so the working tree is left clean.
# - Mission state is built only through the CLI; the user's own files are committed with plain git.
# - Absorbs tests/integration/test_issue_3716_discard_transactional_close_guard.py (the clean-tree and
#   provenance cases); see tests/scenarios/absorption-ledger.json.
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
