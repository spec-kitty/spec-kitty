# Maintainer notes (not part of the behaviour description):
# - Restates `spec-kitty consolidate --help`: it lands an accepted Mission's approved work on the
#   target branch, and never commits or deletes files the user left untracked.
# - Builders run the CLI and plain git only, plus the authored planning files and the work package's
#   code (ADR 2026-10-15-1, decision 6). The Mission targets the topic branch "work".
# - Absorbs tests/integration/test_post_merge_unrelated_untracked.py
#   (test_merge_succeeds_with_untracked_worktrees_and_tmp); see tests/scenarios/absorption-ledger.json.

@lifecycle
Feature: Consolidate an accepted Mission
  As a developer finishing a Mission
  I want `spec-kitty consolidate` to land the approved work on the target branch
  So that the work is delivered, and my own untracked files are neither committed nor removed

  Scenario: Consolidating lands the approved work and leaves my untracked files alone
    Given a mission "demo" planned on a topic branch with the work packages "WP01"
    And the work package "WP01" of mission "demo" has been moved to lane "approved"
    And the mission "demo" has been accepted
    And the file "tmp.txt" has the uncommitted text "stray"
    And the file ".worktrees/scratch/notes.txt" has the uncommitted text "operator scratch"
    And the file "tmp.txt" is present
    And the file ".worktrees/scratch/notes.txt" is present
    When I run "spec-kitty consolidate --mission demo --yes"
    Then the command succeeds
    And the output does not mention "invariant violated"
    And the branch "work" has the file "src/wp01/__init__.py" mentioning "hello from WP01"
    And the work package "WP01" of mission "demo" is in lane "done"
    And the branch "work" tracks no file under "tmp.txt"
    And the branch "work" tracks no file under ".worktrees"
    And the file "tmp.txt" is unchanged
    And the file ".worktrees/scratch/notes.txt" is unchanged
