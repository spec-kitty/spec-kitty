# Maintainer notes (not part of the behaviour description):
# - Restates the sparse-checkout preflight of `spec-kitty consolidate` (#588, FR-006/FR-009): legacy
#   sparse-checkout can lose files during a merge, so consolidate refuses before anything moves.
# - Mission state is built only through the CLI; sparse-checkout state only through plain git.
# - Absorbs tests/integration/sparse_checkout/test_merge_preflight_blocks.py; see
#   tests/scenarios/absorption-ledger.json.
# - Untagged, so every scenario runs in the gating nightly.

Feature: Refuse to consolidate while legacy sparse-checkout is on
  As a developer with a repository that still carries Spec Kitty 2.x sparse-checkout state
  I want `spec-kitty consolidate` to refuse before it touches any branch
  So that a merge never runs in a checkout that silently hides files

  Scenario: Consolidating under sparse-checkout is refused and moves no branch
    Given a project with a mission "demo-mission"
    And sparse-checkout is turned on in the project for "README.md"
    And the repository has at least one commit
    And the repository's branches are recorded
    When I run "spec-kitty consolidate --mission demo-mission"
    Then the command fails
    And the output mentions "legacy sparse-checkout state detected"
    And the output mentions "--allow-sparse-checkout"
    And the repository HEAD is unchanged
    And the repository has no new commits
    And the repository's branches are unchanged

  Scenario: Consolidate offers no --force that could get around the refusal
    Given a project with a mission "demo-mission"
    And sparse-checkout is turned on in the project for "README.md"
    And the repository's branches are recorded
    When I run "spec-kitty consolidate --mission demo-mission --force"
    Then the command exits with code 2
    And the output mentions "No such option: --force"
    And the repository's branches are unchanged
