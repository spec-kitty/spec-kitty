# Maintainer notes (not part of the behaviour description):
# - Restates the lane-membership rule of a re-run of `spec-kitty agent mission finalize-tasks` (#5573):
#   when a re-plan makes a planned work package build on a started one, the planned work package joins
#   the started one's lane, never the other way round, and the started lane keeps its worktree and work.
# - Builders run the CLI and plain git only, plus the authored planning files and the work package's
#   code (ADR 2026-10-15-1, decision 6). The amendment edits the authored prompt and tasks.md.
# - Absorbs tests/integration/test_refinalize_keeps_started_lanes.py (the started-lane cases in both
#   lane orders); see tests/scenarios/absorption-ledger.json.

@lifecycle
Feature: Re-plan a Mission without moving started work
  As a developer re-planning a Mission after work has started
  I want a re-run of finalize-tasks to fit new dependencies around the work already in progress
  So that a started work package never loses its lane, its worktree or its commits

  Scenario: A planned work package that now builds on a started one joins the started one's lane
    Given a lanes mission "rl" planned on a topic branch with the work packages "WP01,WP02"
    And the work package "WP02" of mission "rl" has been moved to lane "in_progress"
    And the work package "WP02" of mission "rl" has committed its work
    And the work package "WP01" of mission "rl" is amended to build on "WP02"
    When I run "spec-kitty agent mission finalize-tasks --mission rl --json"
    Then the command succeeds
    And the output mentions "write_scope_overlap"
    And the lanes of mission "rl" are "lane-b: WP02, WP01"
    And the lane worktree of the work package "WP02" of mission "rl" still holds its committed work

  Scenario: The joined lane is the started work package's lane, whatever its name
    Given a lanes mission "rl" planned on a topic branch with the work packages "WP01,WP02"
    And the work package "WP01" of mission "rl" has been moved to lane "in_progress"
    And the work package "WP01" of mission "rl" has committed its work
    And the work package "WP02" of mission "rl" is amended to build on "WP01"
    When I run "spec-kitty agent mission finalize-tasks --mission rl --json"
    Then the command succeeds
    And the lanes of mission "rl" are "lane-a: WP01, WP02"
    And the lane worktree of the work package "WP01" of mission "rl" still holds its committed work
