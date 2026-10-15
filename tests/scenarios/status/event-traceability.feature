# Maintainer notes (not part of the behaviour description):
# - Drafted from a promise and landed @wip: its steps are not bound yet, so it
#   runs only in the non-gating @wip pass and never fails the leg. Binding needs
#   the black-box "build a work package to a Mission state" fixtures
#   (spec-kitty/spec-kitty#6137, under BDD epic #6133) plus new Arrange/Act/Assert
#   step definitions in acceptance-jvm/. Tracked by spec-kitty/spec-kitty#6260.
# - The behaviour is already guarded by the pytest regression
#   tests/consolidation/test_wall_clock_claim_p0_repro.py (spec-kitty#4941); this
#   scenario is the customer-facing promise the same fix satisfies, not a second
#   regression guard, so it carries no clock/skew/defect wording.
# - No @promise tag yet: resolving this behaviour to a promise identifier is a
#   QA-team concern (the id lives in the QA promise registry), added when the
#   steps are bound and @wip is removed. Tooling never invents a promise id.

@wip @wip-owner:stijn-dejongh @wip-since:2026-10-15
Feature: Recorded work-package decisions are honoured in the order they happen
  As a developer running a Mission with reviewers
  I want the latest decision I record on a work package to be the one that counts
  So that a rejection is never quietly overridden by an earlier approval

  Scenario: A rejection recorded after an approval sends the work package back
    Given a Mission whose work package "WP01" has been approved
    When a reviewer records a rejection of "WP01" after that approval
    Then the work package "WP01" is sent back for rework
    And "WP01" is not reported as approved

  Scenario: A Mission whose work package was rejected after approval is refused at consolidation
    Given a Mission whose work package "WP01" has been approved
    And a reviewer has recorded a rejection of "WP01" after that approval
    When I consolidate the Mission
    Then consolidation is refused because "WP01" is not approved
