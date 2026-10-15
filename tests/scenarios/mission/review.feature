# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty agent tasks move-task --to planned --review-feedback-file` (a reviewer's
#   rejection) and the review-cycle record it writes (#676): only a real rejection opens a new cycle.
# - Builders run the CLI and plain git only, plus the authored planning files and the work package's
#   code (ADR 2026-10-15-1, decision 6). Review feedback lives outside the repository ("../...").
# - On a coordination Mission the review-cycle record is committed to the coordination branch, so the
#   assertions read it there with git.
# - Absorbs tests/integration/review/test_reject_from_in_review.py (the canonical rejection, the empty
#   feedback refusal, the declared reviewer) and tests/integration/test_review_cycle_rejection_only.py
#   (the counter and the two-rejection cases); see tests/scenarios/absorption-ledger.json.

@lifecycle
Feature: Reject a work package in review
  As a reviewer
  I want my rejection and its feedback recorded as one review cycle
  So that the implementer knows what to fix and the history counts only real rejections

  Background:
    Given a mission "demo" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "demo" has been moved to lane "in_review"

  Scenario: Rejecting with written feedback sends the work package back and records the review cycle
    Given the review feedback file "../feedback.md" says "Please add a test for the greeting."
    When I run "spec-kitty agent tasks move-task WP01 --to planned --mission demo --review-feedback-file ../feedback.md --agent reviewer --reviewer reviewer-renata --json"
    Then the command succeeds
    And the JSON field "to_lane" of the output is "planned"
    And the output mentions "review-cycle-1.md"
    And the work package "WP01" of mission "demo" is in lane "planned"
    And the file "tasks/WP01-wp01/review-cycle-1.md" of mission "demo" on the coordination branch mentions "Please add a test for the greeting."
    And the file "tasks/WP01-wp01/review-cycle-1.md" of mission "demo" on the coordination branch mentions "reviewer_agent: reviewer-renata"

  Scenario: Rejecting with an empty feedback file is refused and changes nothing
    Given an empty review feedback file "../empty.md"
    When I run "spec-kitty agent tasks move-task WP01 --to planned --mission demo --review-feedback-file ../empty.md --agent reviewer --json"
    Then the command exits with code 1
    And the output mentions "Review feedback file is empty"
    And the work package "WP01" of mission "demo" is in lane "in_review"
    And the coordination branch of mission "demo" has no file "tasks/WP01-wp01/review-cycle-1.md"

  Scenario: Re-running implement on a work package in review opens no review cycle
    When I run "spec-kitty agent action implement WP01 --mission demo --agent claude"
    Then the coordination branch of mission "demo" has no file "tasks/WP01-wp01/review-cycle-1.md"

  Scenario: Re-running implement after a rejection keeps the one review cycle as it was
    Given the work package "WP01" of mission "demo" has been rejected with the feedback "Rename the greeting."
    And the file "tasks/WP01-wp01/review-cycle-1.md" of mission "demo" on the coordination branch is recorded
    When I run "spec-kitty agent action implement WP01 --mission demo --agent claude"
    Then the command succeeds
    And the file "tasks/WP01-wp01/review-cycle-1.md" of mission "demo" on the coordination branch is unchanged
    And the coordination branch of mission "demo" has no file "tasks/WP01-wp01/review-cycle-2.md"

  Scenario: A second rejection opens a second review cycle and keeps the first
    Given the work package "WP01" of mission "demo" has been rejected with the feedback "First round: rename the greeting."
    And the file "tasks/WP01-wp01/review-cycle-1.md" of mission "demo" on the coordination branch is recorded
    And the work package "WP01" of mission "demo" has been moved to lane "in_review"
    And the review feedback file "../second.md" says "Second round: add a docstring."
    When I run "spec-kitty agent tasks move-task WP01 --to planned --mission demo --review-feedback-file ../second.md --agent reviewer --json"
    Then the command succeeds
    And the file "tasks/WP01-wp01/review-cycle-2.md" of mission "demo" on the coordination branch mentions "Second round: add a docstring."
    And the file "tasks/WP01-wp01/review-cycle-1.md" of mission "demo" on the coordination branch is unchanged
