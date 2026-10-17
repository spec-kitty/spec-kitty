# Maintainer notes (not part of the behaviour description):
# - Consumer-outcome scenarios for the charter PACK-PROVISIONING promise: the offering backend
#   is supplied with a list of governance packs that resolve through its public seams (a
#   filesystem location or a published reference such as a git/GitHub ref), and the activation
#   equivalent — a configured pack's parts are brought into force in a repository and change what
#   the runtime offers (a new mission type to choose, a new agent profile that applies). This is
#   the pack-ecosystem direction ahead of the open-packs / offering extraction; it is authored
#   forward-looking, so every scenario is @wip until QA binds its steps and gating.
# - DRAFT. No @promise: tie-in and no PROMISES.md ledger here — the QA team owns creating and
#   ratifying them (spec-kitty-qa#801). Authored promise-first to
#   packs/internal/styleguides/feature-and-scenario-authoring.styleguide.yaml.
# - Grounding evidence (read, never transcribed; for QA to map to FR/ADR/issue, not asserted here):
#   * Supply + resolve: the offering resolves a pack tier's root through one fail-closed seam
#     (resolve_pack_root(tier, org_root, project_root) -> PackRootNotFound; src/charter/offering/
#     pack_paths.py). An org pack is declared in .kittify/config.yaml under charter_packs.org.packs
#     (legacy doctrine.org.packs) as an OrgPackConfig (src/charter/offering/drg/org_pack_config.py:
#     a local filesystem path with $ENV expansion and optional subdir, or a published reference
#     fetched into a local snapshot — src/specify_cli/charter_packs/snapshot.py + the fetch CLI).
#     load_org_pack(pack_name, pack_root, layer_index) reads <pack_root>/drg/fragment.yaml and
#     raises OrgPackMissingError when the root or fragment is absent (src/charter/offering/drg/
#     org_pack_loader.py). A configured-but-unresolvable pack must fail closed, not fail open
#     (#4984 is the bug where it currently fails open).
#   * Direction/issues: open-packs extraction #3022 (runtime-fetch, ADR-1 Option C) / #3504 (CI
#     re-vendor, ADR 2026-08-16-2 Option B); offering extraction epic #6099; external org-pack
#     install/update/uninstall lifecycle #5243; pack ecosystem #2466; pack skills ADR 2026-09-27-1
#     / #5193; explicit opt-in for the internal pack #3505 (ADR-2).
#   * Activation impact: a resolved pack's artifacts enter the merged DRG (new mission types,
#     agent profiles, directives, …); plan_activation / commit_plan bring selected parts into
#     force (src/charter/activation/activation_engine.py); cascade brings along what a choice
#     depends on (src/charter/activation/cascade.py). A pack may also ship activation PRESETS
#     (presets/<name>.yaml) and enforce activations through required_<kind> lists in its
#     org-charter.yaml (ADR 2026-10-06-2); the default-in-force rules those interact with are the
#     subject of the-default-governance-profile.feature.

Feature: Provisioning governance packs and bringing their parts into force
  As a team sharing governance as packs
  I want to point the system at packs by a filesystem location or a published reference, then
    bring the parts I choose into force in a repository
  So that shared governance reaches a project through a stable, named seam — and never silently,
    and never from a pack the system could not actually resolve

  Background:
    Given a project set up with Spec Kitty whose files are committed
    And the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized

  # --- Offering side: the backend is supplied with packs that resolve through public seams ---

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A pack supplied by a filesystem location is provisioned and its catalogue becomes available
    Given a governance pack published at a filesystem location
    When the project is configured to draw governance from that pack
    Then the pack's governance is available to choose from in the project
    And the author can see which pack each available piece of governance came from

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A pack supplied by a published reference is fetched and provisioned the same way
    Given a governance pack published behind a versioned reference the project can retrieve
    When the project is configured to draw governance from that reference
    Then the retrieved pack's governance is available to choose from in the project
    And the pack that is provisioned is pinned to the exact version that was retrieved

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A pack the system cannot resolve is refused, not treated as empty
    Given the project is configured to draw governance from a pack
    And that pack cannot be resolved at the location or reference it names
    When the project's governance is assembled
    Then the system refuses with a reason that names the pack and where it looked
    And no governance silently goes missing as if the pack had been empty

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Several packs are layered in the order they were supplied
    Given the project is configured to draw governance from more than one pack
    When the project's governance is assembled
    Then every supplied pack's governance is available to choose from
    And where two packs speak to the same thing, the later-supplied pack's governance is the one that stands

  # --- Activation equivalent: configured parts are brought into force and change the runtime ---

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Activating a mission type from a pack makes it a choice the project can run
    Given a provisioned pack that offers a mission type the project did not have
    When the author brings that mission type into force
    Then the project can start a mission of that type
    And the mission runs the steps the pack defined for it

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Activating an agent profile from a pack makes it apply to the work
    Given a provisioned pack that offers an agent profile the project did not have
    When the author brings that profile into force
    Then the governance in force includes that profile
    And work routed to that profile is governed by it

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Provisioning a pack does not by itself change what is in force
    Given a provisioned pack whose parts the author has not chosen to bring into force
    When the project's governance in force is assembled
    Then the pack's parts are available to choose from but are not yet governing the work
    And bringing a part into force is a separate, deliberate step the author takes
