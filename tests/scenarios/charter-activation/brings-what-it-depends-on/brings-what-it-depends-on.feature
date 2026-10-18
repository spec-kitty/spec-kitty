# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter-ACTIVATION offering promise that adopting one
#   piece of governance can bring the governance it depends on — or tell the author what was
#   left out. Cascade is an activation-layer behaviour the offering suite deliberately excluded.
#   Authored promise-first to packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml.
# - DRAFT. PROMISES.md proposes IDs; BINDINGS.md records missing witnesses. No ratification,
#   @promise tags or gating promotion is made (QA #801).
# - Authority: charter-pack-activation-layer spec FR-006/007 and activate contract Behavior
#   6/7/9; cascade-asset-silent-drop spec FR-001/002/003/008. Exact requires/suggests traversal
#   is current implementation evidence in cascade.py, not the unrelated historical FR-014.
#   Its missing historical ADR citation is an explicit ratifier question in RESEARCH.md.

Feature: Adoption can bring referenced governance within the author's chosen scope
  As a developer adopting a piece of governance that refers to others
  I want to bring those references in one step, or be told plainly what I left out
  So that I can deliberately choose the scope rather than mistake a warning for enforcement

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adopting a choice can bring its required and suggested governance in one step
    Given an available profile with both required and suggested governance references
    And the profile and its activatable references are explicitly outside the governance in force
    When the author adopts the profile together with all its referenced governance
    Then the governance in force includes the profile and both kinds of referenced governance

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: The author can limit how far adoption reaches
    Given an available profile that references several kinds of governance
    And the profile and those references are explicitly outside the governance in force
    And unrelated governance of a selected kind is available but explicitly out of force
    When the author adopts the profile and names only some of those kinds to bring along
    Then the profile and the referenced governance of the selected kinds are in force
    And the unrelated governance of the selected kind stays out of force
    And the referenced governance left outside that scope stays out of force
    And the author is told which references were left outside that scope

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adopting a choice on its own tells the author what was left behind
    Given an available profile that references other activatable governance
    And the profile and those references are explicitly outside the governance in force
    When the author adopts only the profile
    Then the profile is in force
    And its referenced governance stays out of force
    And the author is told which referenced governance was not brought in, and how to bring it

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adoption reports templates and assets as not independently activatable
    Given a profile that references a template and an asset as well as an inactive tactic
    When the author adopts the profile together with all its referenced governance
    Then the profile and the tactic are in force
    And the template and asset have not been independently activated
    And the author can see each was reached and excluded because its kind is not independently activatable
