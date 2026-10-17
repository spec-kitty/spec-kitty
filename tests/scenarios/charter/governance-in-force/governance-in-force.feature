# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter offering promise "the governance in force is what
#   I chose". Promise-first, authored to the feature-and-scenario-authoring styleguide.
# - Each scenario's Act drives the command that reveals the governance in force, so a red is
#   honest. The team pack is authored (user content) and registered, then the charter is
#   synthesized WITH the pack present, so the overlay/selection actually applies.
# - Evidence (read, never transcribed): a skill is in force only when required/selected, not
#   merely because a pack offers it (ArtifactKind.effective_when_absent == "required" for skill,
#   ADR 2026-09-27-1); an org pack's required selections overlay the charter's chosen set
#   (ArtifactKind.selection_overlayable; apply_org_charter_to_interview); governance an org pack
#   provides and the charter puts in force is resolved from the org roots / org DRG fragments by
#   ActiveCharterService (pack_context.org_roots), so the coherence check confirms it sound the
#   same way it does a built-in artifact (epic #6286 charter-offering catfooding).
# - Promises mapped to FR/ADR in tests/scenarios/charter/PROMISES.md.

Feature: The governance in force is what I chose
  As a developer governing a project with a charter
  I want the governance in force to be the set my charter puts in force
  So that my work is governed by what I chose, not by everything that happens to exist

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview

  @promise:PR-CHARTER-GOVERNANCE-001
  Scenario: Sharing a pack does not silently add its commands to every tool
    Given the team pack offers a skill it does not require
    And the charter has been synthesized
    When the author asks what governs the work
    Then the governance in force is only what the charter puts in force

  @promise:PR-CHARTER-GOVERNANCE-002
  Scenario: A team's org-wide requirement is honoured on top of the project's own choices
    Given the team pack requires a rule the project did not select
    And the charter has been synthesized
    When the author asks what governs the work
    Then the governance in force includes the team's required rule

  @promise:PR-CHARTER-GOVERNANCE-003
  Scenario: A rule the team pack provides is confirmed sound governance, the same as a built-in rule
    Given the team pack requires a rule the project did not select
    And the charter has been synthesized
    When the author checks the shared governance is sound
    Then the shared governance is reported sound
