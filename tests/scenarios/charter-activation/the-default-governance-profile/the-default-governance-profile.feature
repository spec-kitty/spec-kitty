# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the MINIMAL / DEFAULT charter activation profile: what a
#   project is governed by when it has answered the interview with its defaults and has not
#   explicitly turned anything on or off. The default is "unrestricted" for every kind of
#   governance except skills, which default to "only what is required" so that provisioning a
#   pack never silently adds commands to every tool.
# - DRAFT. No @promise: tie-in and no PROMISES.md ledger here — the QA team owns creating and
#   ratifying them (spec-kitty-qa#801). Authored promise-first to
#   packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml.
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
#   * This is the activation-layer reading of the same fact the offering suite already asserts for
#     the skill exception (tests/scenarios/charter/, PR-CHARTER-GOVERNANCE-001). The overlap is
#     deliberate: the offering suite owns "what I chose is in force"; this suite owns the lifecycle
#     reading — "what is in force before I choose anything", and how provisioning changes it.

Feature: The default governance a project is held to before it turns anything on
  As a developer who has just set up governance and chosen nothing in particular
  I want a sensible default for what governs my work — everything available, except commands that
    would be forced onto every tool
  So that I am governed from the start without ceremony, yet a shared pack never silently changes
    how my tools behave

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Before choosing anything, a project is governed by all the governance available to it
    Given a project that has turned nothing on or off beyond the interview defaults
    When the project's governance in force is assembled
    Then every kind of governance available to the project is in force
    And the author did not have to activate each piece for it to apply

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Shareable commands are the exception — they apply only when the charter asks for them
    Given governance available to the project that includes a shareable command
    And the project has not been set to require or select that command
    When the project's governance in force is assembled
    Then the shareable command is available to the project but is not in force
    And it does not appear as a command in the project's tools

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Provisioning a pack extends the default without forcing its commands on every tool
    Given a provisioned pack that offers both ordinary governance and a shareable command
    When the project's governance in force is assembled with the pack in place
    Then the pack's ordinary governance is in force under the default
    And the pack's shareable command stays out of force until the project requires or selects it

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Maintainer-only governance is never in force unless the project opts in
    Given maintainer-only governance that the project has not opted into
    When the project's governance in force is assembled
    Then that maintainer-only governance is not in force
    And it begins to apply only once the project opts into it deliberately

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A project can start from a small curated baseline instead of everything
    Given a project that wants a small curated starting baseline rather than all available governance
    When the project adopts the minimal ready-made baseline the built-in governance ships
    Then only that curated baseline of governance is in force
    And the kinds the baseline leaves open stay unrestricted until the project narrows them itself
