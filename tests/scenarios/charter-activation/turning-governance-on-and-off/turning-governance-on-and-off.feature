# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter-ACTIVATION offering: the lifecycle verbs
#   (activate / deactivate) the charter-OFFERING suite under tests/scenarios/charter/
#   deliberately excluded ("the activation layer extracts later" — see that suite's RESEARCH.md).
#   Authored promise-first to packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml:
#   outcomes, not output surfaces; one promise per scenario; the consumer's language only.
# - DRAFT. The @promise: tie-in and a PROMISES.md promise->contract ledger are intentionally
#   NOT provided here: the QA team owns creating and ratifying them (spec-kitty-qa#801). Each
#   scenario carries @wip until QA binds its step vocabulary and decides its gating status; the
#   Act drives the governed outcome, not a command's output, so a later binding stays honest.
# - Grounding evidence (read, never transcribed; for QA to map to FR/ADR, not asserted here):
#   activate/deactivate change what the activation-aware resolver puts in force
#   (src/charter/activation/activation_engine.py, pack_manager.py); adopting from the
#   unrestricted state materializes what is already effective before appending, so nothing in
#   force is silently dropped (plan_activation, #4253); an unknown id is refused BEFORE any
#   post-state is computed and nothing is written (plan_activation / commit_plan, NFR-003 —
#   ADR 2026-05-16-1).

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
    Given a rule the project has not yet adopted
    When the author adopts that rule
    Then the governance in force includes that rule

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Retiring a rule takes it out of force
    Given a rule the project has adopted
    When the author retires that rule
    Then the governance in force no longer includes that rule

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adopting one more rule never drops the rules already in force
    Given a project governed by every rule its packs provide
    When the author adopts one more rule
    Then the governance in force still includes every rule that was in force before

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Naming governance that does not exist changes nothing
    Given the project's governance is settled
    When the author tries to adopt a rule that does not exist
    Then the request is refused with a clear reason
    And the governance in force is left exactly as it was
