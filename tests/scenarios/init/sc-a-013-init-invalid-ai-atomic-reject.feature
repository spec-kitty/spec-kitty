# Converted from spec-kitty-qa scenarios/spec-kitty/a-cli/SC-A-013-init-invalid-ai-atomic-reject.md (SC-A-013) by scripts/scenario_md_to_feature.py.
# The steps are the QA page's: bind them in acceptance-jvm, then drop the @wip tags.
# A @promise tag is added by a person, and only for a ratified promise.
# Precondition: The runner's isolated invocation: a fresh throwaway project directory with no ancestor .git or .kittify, an isolated SPEC_KITTY_HOME/HOME, and SPEC_KITTY_* variables scrubbed from the process environment.
# Precondition: Each check runs init in its own empty subdirectory of the throwaway project.
# Precondition: No credentials, SaaS target, network fixture or git repository are required.
# Oracle: `spec-kitty init --yes --ai bogusvalue` exits non-zero with no traceback and leaves no `.kittify/` in its directory (atomic rejection).
# Oracle: Control: `spec-kitty init --yes --ai claude` in a sibling directory exits 0 and creates `.kittify/config.yaml`.

Feature: init rejects an invalid assistant atomically

  @qa:SC-A-013 @wip @wip-owner:Ivan-Melck @wip-since:2026-10-18
  Scenario: init rejects an invalid assistant atomically
    Given two empty subdirectories of the throwaway project
    When running `spec-kitty init --yes --ai bogusvalue` in the first
    Then the exit status is non-zero, no traceback appears and no `.kittify/` is created
    When running `spec-kitty init --yes --ai claude` in the second
    Then the exit status is 0 and `.kittify/config.yaml` exists
