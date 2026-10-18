# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for shared-reference safety during cascade retirement, not a
#   universal ban on explicitly retiring referenced governance. The offering suite excludes
#   this activation lifecycle guarantee. Authored promise-first to
#   packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml.
# - DRAFT. PROMISES.md and BINDINGS.md propose contracts and witnesses for human review.
#   No @promise tag or ratification is applied; all scenarios remain @wip (QA #801).
# - Grounding evidence (read, never transcribed; for QA to map to FR/ADR, not asserted here):
#   shared-reference-safe deactivation keeps a cascade candidate that is still referenced by a
#   still-active source and names that source (activation-layer FR-008 and deactivate contract
#   Behavior 6). An absent activation key is not an explicit empty set: deactivate contract
#   Behavior 3 refuses it. Current recovery establishes explicit control, not an assumed
#   upgrade-to-list behavior; see RESEARCH.md for the historical contract's superseded wording.

Feature: Cascaded retirement keeps governance shared by other active choices
  As a developer retiring a piece of governance with its references
  I want shared governance to be kept and an unrestricted kind to be left alone
  So that a cascade does not silently retire another active choice's shared governance

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Governance still relied on by another active choice is kept, and the reason is named
    Given two different active choices both reference the same rule in force
    When the author retires one choice together with the governance it references
    Then the retired choice is no longer in force
    And the other choice and the shared rule stay in force
    And the author is told which remaining active choice still relies on the rule

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Retiring a kind of governance the project never controlled is refused with the way forward
    Given a kind of governance the project has never narrowed to an explicit set
    And that kind still follows its unrestricted default
    When the author tries to retire one of its rules
    Then the request is refused with a clear reason
    And the author is told how to put that kind under explicit control first
    And the governance in force and the saved choices are unchanged
