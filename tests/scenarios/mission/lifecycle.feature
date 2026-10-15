# Maintainer notes (not part of the behaviour description):
# - Restates the planning-to-review flow of `spec-kitty agent mission setup-plan`, `finalize-tasks`,
#   `agent action implement` and `agent tasks move-task`, and the coordination placement of status (#5440).
# - Builders run the CLI and plain git only, plus the planning files an agent authors (spec, plan,
#   tasks, work package prompts) and the work package's own code (ADR 2026-10-15-1, decision 6).
#   Planning happens on the topic branch "work", the Mission's target branch.
# - Absorbs tests/e2e/test_cli_smoke.py (test_setup_plan, test_full_workflow_sequence) and
#   tests/e2e/test_coord_status_off_target_lifecycle.py; see tests/scenarios/absorption-ledger.json.
# - Untagged apart from @lifecycle (a selection tag), so every scenario runs in the gating nightly.

@lifecycle
Feature: Take a Mission from its spec to review
  As a developer running a Mission with an agent
  I want planning, implementation and the hand-off to review to work as one flow
  So that a reviewer receives committed work and the Mission's history is kept

  Scenario: Setting up the plan of a committed spec writes the plan
    Given a mission "demo" on a topic branch whose spec is written and committed
    When I run "spec-kitty agent mission setup-plan --mission demo --json"
    Then the command succeeds
    And the JSON field "result" of the output is "success"
    And the folder of mission "demo" has a non-empty "plan.md" file

  Scenario: Committed work of a work package is handed to review
    Given a mission "demo" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "demo" has been moved to lane "in_progress"
    And the work package "WP01" of mission "demo" has committed its work
    When I run "spec-kitty agent tasks move-task WP01 --to for_review --mission demo --agent claude"
    Then the command succeeds
    And the work package "WP01" of mission "demo" is in lane "for_review"
    And the folder of mission "demo" has a non-empty "spec.md" file
    And the folder of mission "demo" has a non-empty "plan.md" file
    And the folder of mission "demo" has a non-empty "tasks.md" file
    And the history of branch "work" mentions "spec"
    And the history of branch "work" mentions "plan"
    And the history of branch "work" mentions "tasks"

  Scenario: A coordination Mission keeps its status off the target branch through to review
    Given a mission "demo" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "demo" has been moved to lane "in_progress"
    And the work package "WP01" of mission "demo" has committed its work
    When I run "spec-kitty agent tasks move-task WP01 --to for_review --mission demo --agent claude"
    Then the command succeeds
    And the branch "work" holds no status file of mission "demo"
    And the folder of mission "demo" has no "status.events.jsonl" file
    And the folder of mission "demo" has no "status.json" file
    And the status log on the coordination branch of mission "demo" mentions "MissionCreated"
    And the status log on the coordination branch of mission "demo" mentions "TasksStarted"
    And the status log on the coordination branch of mission "demo" mentions "WPCreated"
    And the status log on the coordination branch of mission "demo" mentions "TasksCompleted"
    And the status log on the coordination branch of mission "demo" records a move of "WP01" to "for_review"

  Scenario: Planning a coordination Mission keeps its status off the target branch
    Given a mission "demo" planned on a topic branch with the work packages "WP01"
    When I run "spec-kitty agent tasks status --mission demo --json"
    Then the command succeeds
    And the branch "work" holds no status file of mission "demo"
    And the folder of mission "demo" has no "status.events.jsonl" file
