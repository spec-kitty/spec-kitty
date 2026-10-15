# Maintainer notes (not part of the behaviour description):
# - Restates the commit boundary of `spec-kitty agent mission create` and `setup-plan` (#846): create
#   scaffolds a spec for the author to fill in and does not commit it; setup-plan starts only from a
#   spec that is committed AND substantive, and commits a real plan to the target branch.
# - Builders run the CLI and plain git only, plus the authored spec and plan (ADR 2026-10-15-1,
#   decision 6). The Mission targets the topic branch "work".
# - Absorbs tests/integration/test_specify_plan_commit_boundary.py (the create and setup-plan gate
#   cases); see tests/scenarios/absorption-ledger.json.

@lifecycle
Feature: Start planning only from a real, committed spec
  As a developer writing a Mission's spec with an agent
  I want planning to wait until the spec is real and committed
  So that a plan is never built on a placeholder or on work that is not saved

  Scenario: Creating a Mission scaffolds its spec without committing it
    Given a project set up with Spec Kitty on the topic branch "work"
    When I run "spec-kitty agent mission create demo --json"
    Then the command succeeds
    And the new mission's folder has a "spec.md" file
    And the new mission's folder has a "meta.json" file
    And the file "spec.md" of mission "demo" is not committed

  Scenario: Setting up the plan of a spec that is not committed is refused
    Given a mission "demo" created on a topic branch
    And the spec of mission "demo" is written but not committed
    When I run "spec-kitty agent mission setup-plan --mission demo --json"
    Then the JSON field "result" of the output is "blocked"
    And the JSON flag "phase_complete" of the output is false
    And the output mentions "committed AND substantive"
    And the file "plan.md" of mission "demo" is not committed

  Scenario: Setting up the plan of a committed placeholder spec is refused
    Given a mission "demo" created on a topic branch
    And the spec of mission "demo" is committed as it was scaffolded
    When I run "spec-kitty agent mission setup-plan --mission demo --json"
    Then the JSON field "result" of the output is "blocked"
    And the JSON flag "phase_complete" of the output is false
    And the JSON flag "spec_committed" of the output is true
    And the JSON flag "spec_substantive" of the output is false
    And the file "plan.md" of mission "demo" is not committed

  Scenario: Setting up the plan of a real, committed spec commits the plan to the target branch
    Given a mission "demo" on a topic branch whose spec is written and committed
    And the plan of mission "demo" is written
    When I run "spec-kitty agent mission setup-plan --mission demo --json"
    Then the command succeeds
    And the JSON field "result" of the output is "success"
    And the JSON flag "phase_complete" of the output is true
    And the file "plan.md" of mission "demo" is committed on the current branch
    And the coordination branch of mission "demo" has no file "plan.md"
