# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter-ACTIVATION offering: the lifecycle verbs
#   (activate / deactivate) the charter-OFFERING suite under tests/scenarios/charter/
#   deliberately excluded ("the activation layer extracts later" — see that suite's RESEARCH.md).
#   Authored promise-first to packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml:
#   outcomes, not output surfaces; one promise per scenario; the consumer's language only.
# - DRAFT. PROMISES.md proposes identifiers and authority; BINDINGS.md records each witness.
#   Nothing is ratified and no @promise tag is applied before human approval (QA #801).
#   All scenarios remain @wip; no passing acceptance execution is claimed.
# - Grounding evidence (read, never transcribed; for QA to map to FR/ADR, not asserted here):
#   activate/deactivate change what the activation-aware resolver puts in force
#   (src/charter/activation/activation_engine.py, pack_manager.py); adopting from the
#   unrestricted state materializes what is already effective before appending, so nothing in
#   force is silently dropped (#4253; unify-charter-activation-surfaces spec's first-run edge
#   case). Unknown-id refusal is charter-activate-cli.md Behavior 2, not the overlay ADR.
#   RESEARCH.md distinguishes historical requirements from current implementation evidence.

Feature: Turning a piece of governance on or off takes effect
  As a developer governing a project with a charter
  I want adopting or retiring a rule to change what is actually in force
  So that the governance I choose is the governance that applies to my work

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adopting a rule puts it in force
    Given a rule the project has explicitly left outside its chosen governance
    And the rule is available but is not in force
    And no team requirement independently puts that rule in force
    When the author adopts that rule
    Then the governance in force includes that rule

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Retiring a rule takes it out of force
    Given a rule in the project's explicitly chosen governance
    And the rule is in force before retirement
    And no team requirement independently keeps that rule in force
    When the author retires that rule
    Then the governance in force no longer includes that rule

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Explicitly adopting a rule preserves the unrestricted rules already in force
    Given a project governed by every available rule without an explicit rule selection
    And at least two different rules are in force
    When the author explicitly adopts one of those rules
    Then the governance in force still includes every rule that was in force before

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Naming governance that does not exist changes nothing
    Given the project's governance and saved choices have been recorded
    When the author tries to adopt an unknown rule in a valid kind
    Then the request is refused with a clear reason
    And the governance in force is left exactly as it was
    And the project's saved governance choices are unchanged
