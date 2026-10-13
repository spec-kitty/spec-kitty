Feature: Valid WIP scenario with an unbound step
  @wip @wip-owner:pedro @wip-since:2026-10-01
  Scenario: Still being drafted
    Given a thing named "a"
    When a step that does not exist yet
