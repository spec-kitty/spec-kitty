# Maintainer notes (not part of the behaviour description):
# - Mission state is built only through the CLI (`spec-kitty init`, `spec-kitty agent mission create`).
# - A work package in a given lane needs the specify/plan/tasks chain, which an agent authors
#   interactively, so it is not built here; these scenarios cover Mission-level status only.
# - Untagged, so every scenario runs in the gating nightly.

Feature: See the status of a Mission
  As a developer running a Mission
  I want to ask Spec Kitty for the status of a Mission by name
  So that I can see which Mission I am looking at and trust that I am not shown another one

  Scenario: A newly created Mission can be looked up by its name
    Given a project with a mission "demo-mission"
    When I run "spec-kitty agent tasks status --mission demo-mission --json"
    Then the command succeeds
    And the mission "demo-mission" is listed

  Scenario: Asking for one Mission does not show another Mission of the same project
    Given a project with a mission "alpha-mission"
    And the project also has a mission "beta-mission"
    When I run "spec-kitty agent tasks status --mission alpha-mission --json"
    Then the command succeeds
    And the mission "alpha-mission" is listed
    And the mission "beta-mission" is not listed

  Scenario: Asking for a Mission that does not exist is refused
    Given a project with a mission "demo-mission"
    And the status of the mission "demo-mission" can be read
    When I run "spec-kitty agent tasks status --mission missing-mission --json"
    Then the command fails
    And the mission "missing-mission" is not listed
