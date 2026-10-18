# Converted from spec-kitty-qa scenarios/spec-kitty/a-cli/SC-A-006-init-idempotent.md (SC-A-006) by scripts/scenario_md_to_feature.py.
# The steps are the QA page's: bind them in acceptance-jvm, then drop the @wip tags.
# A @promise tag is added by a person, and only for a ratified promise.
# Precondition: The runner's isolated invocation: a fresh throwaway project directory with no ancestor .git or .kittify, an isolated SPEC_KITTY_HOME/HOME, and SPEC_KITTY_* variables scrubbed from the process environment.
# Precondition: No credentials, SaaS target, network fixture or git repository are required.
# Oracle: A second `spec-kitty init --yes --ai claude` in an already-initialised project exits 0.
# Oracle: After an operator edit (`agents.auto_commit: false`) to `.kittify/config.yaml`, re-running init leaves the file present and its parsed YAML mapping identical to the edited one.

Feature: init is idempotent and preserves operator configuration

  @qa:SC-A-006 @wip @wip-owner:Ivan-Melck @wip-since:2026-10-18
  Scenario: init is idempotent and preserves operator configuration
    Given a project initialised by `spec-kitty init --yes --ai claude`
    When the operator sets `agents.auto_commit: false` in `.kittify/config.yaml`
    And `spec-kitty init --yes --ai claude` runs again
    Then the second run exits 0
    And `.kittify/config.yaml` still exists and parses to the same mapping, operator setting included
