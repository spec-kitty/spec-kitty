# Maintainer notes (not part of the behaviour description):
# - Spec User Story 2, scenario 8 / FR-019 (#6475, operator ruling 2026-10-20): a folder the user
#   already owns at a command skill's new name is skipped with a warning; init still succeeds.
# - Arranged on a fresh folder: `init --ai codex` on a project set up for other agents refuses
#   ("Requested agents are not configured"), so a re-run cannot add codex.
# - The output assertion names the warning, not just "spec-kitty-plan": the Next Steps panel prints
#   `$spec-kitty-plan` on every codex init, which would make that check vacuous.
# - Every step is bound in acceptance-jvm. @wip until it has run on the JDK 25 runner (it was
#   drafted on a JDK 21 host); the pytest twin is
#   tests/specify_cli/skills/test_command_installer_legacy.py.

Feature: Set up command skills without overwriting my own skills
  As a developer who already keeps my own skills in the project
  I want `spec-kitty init` to leave a skill folder of mine alone when it has a command skill's name
  So that setting up Spec Kitty never destroys my work and still installs every other command skill

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-20
  Scenario: Setting up command skills skips a folder I already own at a command skill's name
    Given the file ".agents/skills/spec-kitty-plan/SKILL.md" has the uncommitted text "my own plan skill"
    When I run "spec-kitty init --non-interactive --ai codex"
    Then the command succeeds
    And the file ".agents/skills/spec-kitty-plan/SKILL.md" mentions "my own plan skill"
    And the file ".agents/skills/spec-kitty-specify/SKILL.md" exists
    And the output mentions "Your own folder blocks command skill .agents/skills/spec-kitty-plan/SKILL.md"
