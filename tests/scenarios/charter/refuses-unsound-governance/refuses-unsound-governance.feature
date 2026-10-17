# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter offering promise "the system refuses unsound
#   governance with a clear reason". Promise-first, authored to the
#   feature-and-scenario-authoring styleguide: outcomes, not output surfaces; one promise per
#   scenario; the consumer's language only.
# - Each Act drives the command that performs the governed check, so a red is honest:
#   `doctor charter-packs` evaluates pack/charter soundness and exits non-zero (unhealthy) on an
#   invalid profile, an org-DRG error (a dangling edge), or an unhealthy artifact; a broken
#   charter fails `charter synthesize` closed.
# - Evidence (read, never transcribed): a silent step-drop on enhances is rejected (agent-profile
#   validation; AGENTS.md "Profile Load Diagnostics"); a mistyped edge endpoint is named, not
#   dropped — unresolved_edge_endpoint / UnknownRelationError (drg/merge.py, FR-010/FR-003,
#   closing ADR 2026-07-26-3's silent-drop path); a broken charter fails closed
#   (ActiveCharterConfigError; plan_activation never mutates on validation failure, ADR
#   2026-05-16-1, NFR-003).
# - Promises mapped to FR/ADR in tests/scenarios/charter/PROMISES.md.

Feature: The system refuses unsound governance with a clear reason
  As a developer relying on a charter to govern my work
  I want governance that would quietly weaken or break to be refused, and the reason named
  So that I can trust what is in force and know what to fix

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview

  @promise:PR-CHARTER-REFUSAL-001
  Scenario: Governance that would silently weaken a profile is refused, not quietly accepted
    Given the shared governance would silently drop part of a profile
    When the author checks the shared governance is sound
    Then the system refuses with a clear reason

  @promise:PR-CHARTER-REFUSAL-002
  Scenario: A mistyped reference between pieces of governance is named, not dropped
    Given one piece of governance points at another by a name that does not exist
    When the author checks the shared governance is sound
    Then the system refuses with a clear reason

  @promise:PR-CHARTER-REFUSAL-003
  Scenario: A broken charter fails closed instead of running half-applied
    Given the charter has been left in a broken state
    When the author sets up the governance
    Then the system refuses with a clear reason
