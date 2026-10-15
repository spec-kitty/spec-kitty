# Maintainer notes (not part of the behaviour description):
# - Restates the sparse-checkout preflight of `spec-kitty agent action implement` (#588, FR-007/FR-009):
#   legacy sparse-checkout can break lane worktrees, so implement refuses before it creates any.
# - Mission state is built only through the CLI; sparse-checkout state only through plain git.
# - Absorbs tests/integration/sparse_checkout/test_implement_preflight_blocks.py; see
#   tests/scenarios/absorption-ledger.json.
# - Untagged, so every scenario runs in the gating nightly.

Feature: Refuse to start work while legacy sparse-checkout is on
  As a developer with a repository that still carries Spec Kitty 2.x sparse-checkout state
  I want `spec-kitty agent action implement` to refuse before it creates a worktree
  So that a work package never starts in a worktree that silently hides files

  Scenario: Starting a work package under sparse-checkout is refused and creates no worktree
    Given a project with a mission "demo-mission"
    And sparse-checkout is turned on in the project for "README.md"
    When I run "spec-kitty agent action implement WP01 --mission demo-mission --agent claude"
    Then the command fails
    And the output mentions "legacy sparse-checkout state detected"
    And the output mentions "spec-kitty doctor sparse-checkout --fix"
    And no work package worktree has been created

  Scenario: Forcing the start of a work package does not get around the sparse-checkout refusal
    Given a project with a mission "demo-mission"
    And sparse-checkout is turned on in the project for "README.md"
    When I run "spec-kitty agent action implement WP01 --mission demo-mission --agent claude --force --note testing"
    Then the command fails
    And the output mentions "legacy sparse-checkout state detected"
    And no work package worktree has been created
