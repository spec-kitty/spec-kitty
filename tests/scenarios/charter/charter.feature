# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty charter synthesize --help` and `charter status --help` on a fresh project:
#   synthesize seeds the built-in charter packs, and status reports each layer's freshness with the
#   command that fixes it.
# - The charter is built only through the CLI (`charter interview --defaults`, `charter generate`,
#   `charter synthesize`); nothing under .kittify/ is written by the scenario.
# - Absorbs tests/integration/test_charter_synthesize_fresh.py (fresh seed, dry run, re-run, no
#   charter), tests/integration/test_charter_status_freshness.py (the freshness shape, synthesis
#   missing) and tests/integration/test_quickstart_end_to_end.py (steps 1, 3 and 5); see
#   tests/scenarios/absorption-ledger.json.

Feature: Govern a project with a charter
  As a developer setting up governance for a project
  I want `spec-kitty charter` to build the charter from my interview and tell me how fresh each part is
  So that I always know which command brings my governance up to date

  Background:
    Given a project set up with Spec Kitty whose files are committed

  Scenario: Synthesizing a fresh project seeds the built-in charter packs
    Given the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    When I run "spec-kitty charter synthesize --json"
    Then the command succeeds
    And the JSON field "result" of the output is "success"
    And the JSON field "mode" of the output is "fresh_project_seed"
    And the output mentions ".kittify/charter-packs/PROVENANCE.md"
    And the output mentions ".kittify/charter/synthesis-manifest.yaml"
    And the JSON field "kind" of the output is "seed"
    And the output does not mention "PROJECT_000"
    And the file ".kittify/charter-packs/PROVENANCE.md" exists
    And the file ".kittify/charter/synthesis-manifest.yaml" mentions "built_in_only: true"

  Scenario: A dry run of synthesize plans the seed and writes nothing
    Given the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    When I run "spec-kitty charter synthesize --dry-run --json"
    Then the command succeeds
    And the JSON field "result" of the output is "dry_run"
    And the JSON field "mode" of the output is "fresh_project_seed_dry_run"
    And the output mentions ".kittify/charter-packs/PROVENANCE.md"
    And the output mentions ".kittify/charter/synthesis-manifest.yaml"
    And no "charter-packs" folder exists in ".kittify"

  Scenario: Synthesizing again changes nothing
    Given the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized
    And the folder ".kittify/charter-packs" is present
    And the file ".kittify/charter/synthesis-manifest.yaml" is present
    When I run "spec-kitty charter synthesize --json"
    Then the command succeeds
    And the folder ".kittify/charter-packs" is unchanged
    And the file ".kittify/charter/synthesis-manifest.yaml" is unchanged

  Scenario: Synthesizing before a charter is generated is refused with the way forward
    Given the charter interview has been answered with its defaults
    When I run "spec-kitty charter synthesize"
    Then the command fails
    And the output mentions "charter"
    And the output mentions "spec-kitty charter generate"

  Scenario: Charter status reports every layer, with what to run, on a project with no charter yet
    When I run "spec-kitty charter status --json"
    Then the command succeeds
    And the "state" entry of the JSON field "charter_source" of the output is "missing"
    And the "state" entry of the JSON field "synced_bundle" of the output is "missing"
    And the "state" entry of the JSON field "synthesized_drg" of the output is "missing"
    And the output mentions "last_change"
    And the output mentions "remediation"
    And the output mentions "no charter at all"

  Scenario: Charter status names synthesize when only synthesis is missing
    Given the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    When I run "spec-kitty charter status --json"
    Then the command succeeds
    And the "state" entry of the JSON field "charter_source" of the output is "fresh"
    And the "state" entry of the JSON field "synthesized_drg" of the output is "missing"
    And the "remediation" entry of the JSON field "synthesized_drg" of the output is "spec-kitty charter synthesize"

  Scenario: After synthesis a built-in-only charter is reported as such, with nothing left to run
    Given the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized
    When I run "spec-kitty charter status --json"
    Then the command succeeds
    And the "state" entry of the JSON field "synthesized_drg" of the output is "built_in_only"
    And the "remediation" entry of the JSON field "synthesized_drg" of the output is null
    And the output does not mention "shipped"

  Scenario: Preflight and lint run on a built-in-only charter and never label a layer "shipped"
    Given the charter interview has been answered with its defaults
    And a charter has been generated from the interview
    And the charter has been synthesized
    When I run "spec-kitty charter preflight --json"
    Then the command succeeds
    And the output is a JSON object
    And the output does not mention "shipped"
    When I run "spec-kitty charter lint --json"
    Then the output is a JSON object
