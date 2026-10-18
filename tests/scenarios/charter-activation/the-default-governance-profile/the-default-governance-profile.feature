# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the MINIMAL / DEFAULT charter activation profile: what a
#   project is governed by when it has answered the interview with its defaults and has not
#   explicitly turned anything on or off. The default is "unrestricted" for every kind of
#   governance except skills, which default to "only what is required" so that provisioning a
#   pack never silently adds commands to every tool.
# - DRAFT. PROMISES.md proposes IDs and BINDINGS.md records witnesses. No ratification or
#   @promise tag is applied, and all scenarios remain @wip (QA #801).
# - Here ordinary governance means unrestricted per-kind artifacts, not the required-only
#   skill set or the separate mission-type ledger. The minimal preset governs directives and
#   tactics, not all governance. Its other kinds remain open; see ADR 2026-10-06-2 and the preset.
# - Grounding evidence (read, never transcribed; for QA to map to FR/ADR/issue, not asserted here):
#   * The default-in-force rule is one enum fact: ArtifactKind.effective_when_absent returns "all"
#     for every kind except SKILL, and "required" for SKILL (src/charter/offering/artifact_kinds.py,
#     FR-005; _REQUIRED_WHEN_ABSENT_KINDS == {SKILL}). An absent activation key is therefore the
#     unrestricted state for directives/tactics/styleguides/toolguides/paradigms/procedures/
#     agent_profiles/mission-step-contracts/glossary-packs/anti-patterns, and the required-only
#     state for skills (ADR 2026-09-27-1 / #5193). Built-in skill defaults are empty at MVP, so the
#     default in-force skill set is exactly the org packs' required_skills.
#   * The two named baselines are activation PRESETS the built-in pack ships (ADR 2026-10-06-2;
#     packs/built-in/presets/{default,minimal}.yaml, applied with `charter activate --preset <name>`):
#     `default` lists no ids and carries no kind gate, so it leans on the "all" rule above — every
#     built-in artifact is effective and all four built-in mission types activate; `minimal` curates
#     a small set of directives and tactics and activates only software-dev, leaving every other kind
#     unrestricted. "Minimal" and "default" in this feature are the consumer readings of those two
#     presets; the scenarios stay true whichever command applies them.
#   * The maintainer/internal org pack is never auto-seeded; it is in force only on explicit opt-in
#     (#3505, ADR-2). A configured org pack's non-skill artifacts join the "all" default once the
#     pack resolves; see provisioning-governance-packs.feature for where packs come from.
#   * The offering suite owns the offered-but-unrequired skill absence assertion
#     (PR-CHARTER-GOVERNANCE-001). This suite instead witnesses adopting one available skill:
#     that skill becomes effective, not its unselected sibling. It does not remint the absence
#     promise. The internal-pack scenario is held for policy/ownership review, not given an ID.

Feature: The default governance a project is held to before it turns anything on
  As a developer who has just set up governance and chosen nothing in particular
  I want a sensible default for what governs my work — everything available, except commands that
    would be forced onto every tool
  So that I am governed from the start without extra setup, yet a shared pack never silently changes
    how my tools behave

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Before choosing anything, ordinary governance follows the unrestricted default
    Given a project whose ordinary governance still follows its unrestricted default
    And an available ordinary rule that has never been individually adopted
    When the project's governance in force is assembled
    Then that ordinary rule is in force
    And the author did not have to activate each ordinary rule for it to apply

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Adopting a shareable command brings it into force without adopting its sibling
    Given a pack offers two shareable commands that the project neither requires nor selects
    And both commands are available but neither is in force
    And neither command has a project-local entry in the configured tool
    When the author adopts one of those commands
    Then the adopted command is in force and appears in the project's configured tool
    And its unselected sibling remains out of force
    And the unselected sibling still has no project-local entry in that tool

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Provisioning ordinary governance extends an unrestricted default
    Given a project whose ordinary governance still follows its unrestricted default
    And a pack offers a new ordinary rule that was not previously available
    When the project is configured to draw governance from that pack
    Then the pack's ordinary rule is available and in force under the default
    And the ordinary rules already in force stay in force

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Maintainer-only governance is never in force unless the project opts in
    Given a consumer project that has not configured the maintainer-only pack
    When the project's governance in force is assembled
    Then that maintainer-only governance is not in force
    And it begins to apply only once the project opts into it deliberately

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A project can start from a small curated baseline instead of everything
    Given a project whose ordinary governance still follows its unrestricted default
    And directives and tactics outside the curated baseline are available and in force
    When the project adopts the minimal ready-made baseline the built-in governance ships
    Then the baseline's chosen directives and tactics are in force
    And other non-required directives and tactics stay outside that chosen baseline
    And the kinds the baseline leaves open stay unrestricted until the project narrows them itself
