# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter offering promise "I can share governance across a
#   team or project safely". Promise-first, authored to the feature-and-scenario-authoring
#   styleguide.
# - Each Act drives the command that performs the governed check, so a red is honest:
#   `doctor charter-packs` exits non-zero (not healthy) on an unsound shared pack.
# - Evidence (read, never transcribed): a pack with an invalid profile is not reported healthy
#   even when its graph counts look right (AgentProfileRepository.skipped_profiles → doctor
#   charter-packs, FR-010); a project's own choice wins over an org pack (layered repository +
#   override machinery, ADR 2026-05-16-1); a shared skill must declare a safe namespace, reserved
#   prefixes spk-/spec-kitty-/spec-kitty. are refused (org_charter.py, skill_preparation, ADR
#   2026-09-27-1); an asset that points outside its pack's own folder is refused fail-closed
#   (AssetPathEscapeError, NFR-006 — src/charter/offering/assets/repository.py).
# - PR-CHARTER-SHARING-002 is @wip: witnessing that the project's choice WINS over the org pack's
#   needs the black-box override + layer-provenance fixture tracked by #6137; the promise is
#   captured now, bound-and-green when that fixture lands.
# - PR-CHARTER-SHARING-004 is @wip @defect:6418 (#6369): it landed gating without ever running
#   and was red on the 2026-10-18 nightly; `doctor charter-packs` exits 0 on the escaping asset.
# - Promises mapped to FR/ADR in tests/scenarios/charter/PROMISES.md.

Feature: I can share governance across a team or project safely
  As a team sharing governance through a pack
  I want an unsound shared pack caught and my project's own choices respected
  So that adopting a team pack never quietly breaks or overrides what my project governs

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview

  @promise:PR-CHARTER-SHARING-001
  Scenario: A team pack carrying an unsound profile is not reported healthy
    Given the project shares governance through a team pack
    And the team pack carries a profile that is not sound
    When the author checks the shared governance is sound
    Then the shared governance is not reported healthy

  @promise:PR-CHARTER-SHARING-002 @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A project's own governance wins over the team pack it adopts
    Given the project shares governance through a team pack speaking to a rule
    And the project's own governance speaks to the same rule differently
    When the author asks what governs the work
    Then the project's own choice is the governance in force

  @promise:PR-CHARTER-SHARING-003
  Scenario: A shared skill under a reserved name is not accepted as sound
    Given the team pack shares a skill under a reserved name
    When the author checks the shared governance is sound
    Then the shared governance is not reported healthy

  @promise:PR-CHARTER-SHARING-004 @wip @wip-owner:stijn-dejongh @wip-since:2026-10-18 @defect:6418
  Scenario: A shared asset that reaches outside its pack is not accepted as sound
    Given the team pack ships an asset that points outside its own folder
    When the author checks the shared governance is sound
    Then the shared governance is not reported healthy
