# Converted from spec-kitty-qa scenarios/spec-kitty/a-cli/SC-A-004-unknown-command-clean-error.md (SC-A-004) by scripts/scenario_md_to_feature.py.
# The steps are the QA page's: bind them in acceptance-jvm, then drop the @wip tags.
# A @promise tag is added by a person, and only for a ratified promise.
# Precondition: The runner's isolated invocation: a fresh throwaway project directory with no ancestor .git or .kittify, an isolated SPEC_KITTY_HOME/HOME, and SPEC_KITTY_* variables scrubbed from the process environment.
# Precondition: No credentials, SaaS target, network fixture or git repository are required. No project initialisation is needed.
# Oracle: `spec-kitty this-command-does-not-exist` exits non-zero, specifically the Typer/Click usage-error code 2.
# Oracle: Neither stream contains `Traceback (most recent call last)`.

Feature: an unknown top-level command is rejected cleanly

  @qa:SC-A-004 @wip @wip-owner:Ivan-Melck @wip-since:2026-10-18
  Scenario: an unknown top-level command is rejected cleanly
    Given the isolated runtime
    When running `spec-kitty this-command-does-not-exist`
    Then the exit status is 2 (usage error), never 0
    And no Python traceback appears on stdout or stderr
