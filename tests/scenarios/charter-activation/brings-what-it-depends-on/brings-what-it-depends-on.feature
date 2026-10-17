# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter-ACTIVATION offering promise that adopting one
#   piece of governance can bring the governance it depends on — or tell the author what was
#   left out. Cascade is an activation-layer behaviour the offering suite deliberately excluded.
#   Authored promise-first to packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml.
# - DRAFT. No @promise: tie-in and no PROMISES.md ledger here — the QA team owns creating and
#   ratifying them (spec-kitty-qa#801). Each scenario carries @wip until QA binds its step
#   vocabulary and decides gating.
# - Grounding evidence (read, never transcribed; for QA to map to FR/ADR, not asserted here):
#   cascade walks the DRG forward along the requires/suggests reference relations and buckets
#   referenced artifacts by kind (cascade_activation_targets, FR-014 —
#   src/charter/activation/cascade.py); an explicit scope activates the kinds it selects and
#   reports the rest as skipped-by-scope (CascadeScope, R-005); activating WITHOUT a cascade
#   still completes but reports the referenced artifacts left out, with a recovery hint
#   (referenced_but_not_cascaded, FR-013); structurally non-activatable kinds (template/asset)
#   are collected and reported, never silently dropped (CHARTER_ACTIVATABLE_KINDS filter,
#   C-001 / FR-005 / #3705).

Feature: Adopting one piece of governance brings the governance it depends on
  As a developer adopting a piece of governance that builds on others
  I want to bring what it depends on in one step, or be told plainly what I left out
  So that I never end up governed by half of what a choice needs

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adopting a choice can bring everything it depends on in one step
    Given a profile that depends on other governance the project has not adopted
    When the author adopts the profile together with everything it depends on
    Then the governance in force includes the profile and the governance it depends on

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: The author can limit how far adoption reaches
    Given a profile that depends on several kinds of governance
    When the author adopts the profile and names only some of those kinds to bring along
    Then the governance in force includes the named kinds
    And the author is told which depended-on kinds were left outside that scope

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adopting a choice on its own tells the author what was left behind
    Given a profile that depends on other governance the project has not adopted
    When the author adopts only the profile
    Then the profile is in force
    And the author is told which depended-on governance was not brought in, and how to bring it

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adoption never offers to turn on something that cannot stand on its own
    Given a profile that reaches a template and an asset it depends on
    When the author adopts the profile together with everything it depends on
    Then the governance in force does not adopt the template or the asset as choices of their own
    And the author can see they were reached but are not independently adoptable
