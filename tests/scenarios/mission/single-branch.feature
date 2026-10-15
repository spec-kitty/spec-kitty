# Maintainer notes (not part of the behaviour description):
# - Restates the write-checkout gates of a single_branch Mission (#5100, #5459, #5680): its work packages
#   run one after another in the write checkout, review needs committed work, stray files are never
#   committed for the user, and implement refuses a checkout that is busy or dirty.
# - Builders run the CLI and plain git only, plus the authored planning files and the work package's
#   code (ADR 2026-10-15-1, decision 6). The Mission is planned on the topic branch "work".
# - Absorbs tests/integration/test_single_branch_write_checkout_e2e.py (the for_review commit gate,
#   the claim commit that is not work, stray files, the occupied and the dirty checkout); see
#   tests/scenarios/absorption-ledger.json.

@lifecycle
Feature: Work on a single-branch Mission in its write checkout
  As a developer whose Mission runs in one checkout without lane worktrees
  I want Spec Kitty to accept only real, committed work for review and to protect my checkout
  So that review never starts on nothing, and my own files are never committed or overwritten for me

  Scenario: A work package with no committed work cannot go to review
    Given a single-branch mission "sb" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "sb" has been moved to lane "in_progress"
    And the subtasks of the work package "WP01" of mission "sb" are marked done
    When I run "spec-kitty agent tasks move-task WP01 --to for_review --mission sb --agent claude --json"
    Then the command fails
    And the output mentions "no implementation commit"
    And the work package "WP01" of mission "sb" is in lane "in_progress"

  Scenario: Committed work of a work package goes to review without forcing
    Given a single-branch mission "sb" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "sb" has been moved to lane "in_progress"
    And the work package "WP01" of mission "sb" has committed its work
    When I run "spec-kitty agent tasks move-task WP01 --to for_review --mission sb --agent claude --json"
    Then the command succeeds
    And the work package "WP01" of mission "sb" is in lane "for_review"

  Scenario: Claiming a work package is not work that review can accept
    Given a single-branch mission "sb" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "sb" has been moved to lane "in_progress"
    And the subtasks of the work package "WP01" of mission "sb" are marked done
    When I run "spec-kitty agent status emit WP01 --to for_review --actor claude --mission sb --json"
    Then the command fails
    And the output mentions "no implementation commit"
    And the work package "WP01" of mission "sb" is in lane "in_progress"

  Scenario: A stray file in the checkout is never committed when asking for review
    Given a single-branch mission "sb" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "sb" has been moved to lane "in_progress"
    And the subtasks of the work package "WP01" of mission "sb" are marked done
    And the file ".env.local" has the uncommitted text "SECRET=1"
    And the repository has at least one commit
    When I run "spec-kitty agent tasks move-task WP01 --to for_review --mission sb --agent claude --json"
    Then the command fails
    And the repository HEAD is unchanged
    And the file ".env.local" is not tracked by git
    And the work package "WP01" of mission "sb" is in lane "in_progress"

  Scenario: Starting a second work package while one is in progress in the same checkout is refused
    Given a single-branch mission "sb" planned on a topic branch with the work packages "WP01,WP02"
    And the work package "WP01" of mission "sb" has been moved to lane "in_progress"
    When I run "spec-kitty agent action implement WP02 --mission sb --agent claude"
    Then the command fails
    And the output mentions "WRITE_CHECKOUT_OCCUPIED"
    And the work package "WP02" of mission "sb" is in lane "planned"

  Scenario: Starting a work package in a checkout with uncommitted changes is refused
    Given a single-branch mission "sb" planned on a topic branch with the work packages "WP01"
    And the file "README.md" has the uncommitted text "an edit I have not committed"
    When I run "spec-kitty agent action implement WP01 --mission sb --agent claude"
    Then the command fails
    And the output mentions "WRITE_CHECKOUT_DIRTY"
    And the work package "WP01" of mission "sb" is in lane "planned"
