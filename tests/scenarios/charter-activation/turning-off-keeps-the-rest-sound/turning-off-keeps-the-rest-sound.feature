# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter-ACTIVATION offering promise that retiring one
#   piece of governance never silently breaks another. The offering suite does not cover this;
#   it is a distinct activation lifecycle guarantee. Authored promise-first to
#   packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml.
# - DRAFT. No @promise: tie-in and no PROMISES.md ledger here — the QA team owns creating and
#   ratifying them (spec-kitty-qa#801). Each scenario carries @wip until QA binds its step
#   vocabulary and decides gating.
# - Grounding evidence (read, never transcribed; for QA to map to FR/ADR, not asserted here):
#   shared-reference-safe deactivation keeps a cascade candidate that is still referenced by a
#   still-active source and names that source, rather than removing it (C-005, Contract C3.4 —
#   src/charter/activation/cascade.py, SharedSkip); retiring a kind that was never put under
#   explicit control has no known baseline, so it is refused with the way forward instead of a
#   fabricated list (plan_deactivation -> NoActivationRestrictionsError, surfaced with upgrade
#   guidance by the CLI — activation_engine.py / pack_manager.py).

Feature: Turning one piece of governance off never breaks another
  As a developer retiring a piece of governance
  I want anything still relied on to be kept and anything I never controlled to be left alone
  So that turning one thing off never silently weakens the rest of my governance

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Governance still relied on by another active choice is kept, and the reason is named
    Given a rule the project has adopted
    And another adopted choice still depends on that rule
    When the author retires the first choice together with what it brought in
    Then the still-relied-on rule stays in force
    And the author is told which active choice still relies on it

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Retiring a kind of governance the project never controlled is refused with the way forward
    Given a kind of governance the project has never narrowed to an explicit set
    When the author tries to retire one of its rules
    Then the request is refused with a clear reason
    And the author is told how to put that kind under explicit control first
