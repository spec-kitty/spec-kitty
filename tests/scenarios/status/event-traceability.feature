# Maintainer notes (not part of the behaviour description):
# - Drafted from a promise, now bound and gating (spec-kitty/spec-kitty#6260,
#   under BDD epic #6133). Its steps are implemented in
#   acceptance-jvm/steps/{Arrange,Act,Assert}Steps.java; the approved-state
#   arrange reuses the shipped MissionLifecycle builders (#6137). The third
#   scenario is the same-fixture positive control: it proves the builders reach
#   an approved, accepted Mission and that consolidate runs, so the refusal
#   scenario cannot pass because the fixture silently did nothing.
# - The reviewer's rejection is a real `spec-kitty agent status emit` call. To
#   model a teammate whose clock runs ahead, the approval row in the status log
#   is restamped a fixed ten minutes into the future and committed, as `git pull`
#   through the status-log union driver would deliver it
#   (MissionLifecycle.plantFutureStampedApproval). That restamp is the one
#   documented exception to the Arrange writes allowance of ADR 2026-10-15-1
#   decision 6: the reducer's ordering of that row is the behaviour under test,
#   and the JVM runner cannot move the emitter's clock.
# - The behaviour is already guarded by the pytest regression
#   tests/consolidation/test_wall_clock_claim_p0_repro.py (spec-kitty#4941); this
#   scenario is the customer-facing promise the same fix satisfies, not a second
#   regression guard, so it carries no clock/skew/defect wording.
# - No @promise tag yet: resolving this behaviour to a promise identifier is a
#   QA-team concern (the id lives in the QA promise registry) and tooling never
#   invents a promise id. QA assigns it from the registry; the scenario gates
#   without it (the contract check validates the shape only when the tag is
#   present).

@lifecycle
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

  Scenario: The approval stands when it is the last decision
    Given a Mission whose work package "WP01" has been approved
    And the mission "demo" has been accepted
    When I consolidate the Mission
    Then the command succeeds
    And the branch "work" has the file "src/wp01/__init__.py" mentioning "hello from WP01"
