# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty doctor sparse-checkout --help` (src/specify_cli/cli/commands/_sparse_checkout_doctor.py).
# - Sparse-checkout state is built with plain git only: the `core.sparseCheckout` setting and git's
#   own pattern file, the state Spec Kitty 2.x left behind. Nothing under .kittify/ is written.
# - Absorbs tests/integration/sparse_checkout/test_doctor_finding.py (clean, primary, worktrees) and
#   test_doctor_non_interactive.py (stdin is not a terminal); see tests/scenarios/absorption-ledger.json.
# - Untagged, so every scenario runs in the gating nightly.

Feature: Find and report legacy sparse-checkout state
  As a developer upgrading a project from Spec Kitty 2.x
  I want `spec-kitty doctor sparse-checkout` to tell me whether sparse-checkout is still turned on
  So that I can remove it before it loses work during a merge

  Scenario: A project without sparse-checkout is reported clean
    Given a project set up with Spec Kitty whose files are committed
    When I run "spec-kitty doctor sparse-checkout"
    Then the command succeeds
    And the output mentions "No legacy sparse-checkout state detected"
    And the output does not mention "Legacy sparse-checkout state detected"

  Scenario: Sparse-checkout in the project's own checkout is reported with the way to fix it
    Given a project set up with Spec Kitty whose files are committed
    And sparse-checkout is turned on in the project for "README.md,src/"
    When I run "spec-kitty doctor sparse-checkout"
    Then the command fails
    And the output mentions "Legacy sparse-checkout state detected"
    And the output mentions "core.sparseCheckout = true"
    And the output names the folder "."
    And the output mentions "spec-kitty doctor sparse-checkout --fix"
    And the output does not mention "stale_claim"

  Scenario: Every linked worktree with sparse-checkout is listed next to the project's own checkout
    Given a project set up with Spec Kitty whose files are committed
    And sparse-checkout is turned on in the project for "README.md"
    And the project has a linked worktree ".worktrees/lane-a" with sparse-checkout turned on
    And the project has a linked worktree ".worktrees/lane-b" with sparse-checkout turned on
    When I run "spec-kitty doctor sparse-checkout"
    Then the command fails
    And the output mentions "Lane worktrees"
    And the output names the folder "."
    And the output names the folder ".worktrees/lane-a"
    And the output names the folder ".worktrees/lane-b"

  Scenario: Asking for the fix without a terminal points to the fix and changes nothing
    Given a project set up with Spec Kitty whose files are committed
    And sparse-checkout is turned on in the project for "README.md"
    And the file ".git/info/sparse-checkout" is present
    When I run "spec-kitty doctor sparse-checkout --fix"
    Then the command fails
    And the output mentions "spec-kitty doctor sparse-checkout --fix"
    And the output is a single line
    And the git setting "core.sparseCheckout" is "true"
    And the file ".git/info/sparse-checkout" is unchanged
