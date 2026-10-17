# Maintainer notes (not part of the behaviour description):
# - This feature covers the promises of the explicit applied-work ledger
#   redesign (#5230, epic #2933): upgrade runs exactly the setup work a project
#   has not yet had, in a declared order, and can tell the operator what ran.
#   The operator ruling for #5230 is a FULL ledger redesign with a HARD CUTOVER
#   (no dual-write mirror), a checked-in order MANIFEST, and detect-gated
#   clone-local backfill. These scenarios describe the consumer OUTCOMES of that
#   design, not its mechanism; the words "ledger"/"migration internals" stay out
#   of the scenario text on purpose (consumer language only).
# - Authority each scenario descends from:
#     * "Upgrading a project that is already current changes nothing" and
#       "A tracked refresh ... is not redone" restate the recorded-once-and-skip
#       promise for TRACKED effects (ADR 2026-07-07-1, and its 2026-10-17 #6233
#       amendment: a tracked effect travels with the commit, so the shared record
#       is authoritative for it).
#     * The clone scenarios restate the #6233 core: a clone-local effect that is
#       ABSENT on THIS checkout is (re)applied regardless of a record another
#       clone wrote, and settles once this checkout has it (ADR 2026-07-07-1
#       amendment 2026-10-17; src/specify_cli/upgrade/migrations/base.py
#       `clone_local_effect` / `reselect_when_recorded`).
#     * "finishes the job when re-run" restates selection-correctness: run exactly
#       the declared-but-not-recorded work (a stranded step is picked up).
#     * The "I can ask what ran" / "tells me whether a local-only step is in place
#       here" / drift scenarios restate the operator-visibility and drift promises.
#     * "keeps its already-done work recognized" restates the backfill promise:
#       a pre-ledger project is not force-re-migrated.
# - Steps follow Arrange / Assume / Act / Assert; see tests/scenarios/README.md.
#   This folder carries no PROMISES.md and uses the untagged-gating style of
#   upgrade.feature; these scenarios therefore carry no @promise tag (operator
#   ruling, 2026-10-17).
# - Gating vs @wip: the two scenarios that reuse only already-bound steps gate the
#   nightly today. The rest need new acceptance-jvm steps (and the
#   applied-work read surface, e.g. `spec-kitty upgrade --list-applied` /
#   `spec-kitty doctor migrations`), which the #5230 implementation mission binds;
#   until then they are @wip and run information-only. New steps the mission must
#   bind are listed at the foot of this file.

Feature: Upgrade runs exactly the setup work a project still needs
  As a developer who already adopted Spec Kitty
  I want `spec-kitty upgrade` to run only the setup work my project has not yet had, in a
  dependable order, and to tell me what ran
  So that re-running is safe, a teammate's fresh clone gains its own local setup, and I can
  see and trust what has been done

  Scenario: Upgrading a project that is already current changes nothing
    Given an existing git repository with commit history
    And a project already set up with Spec Kitty for the agents "claude"
    And every change in the project is committed
    And the repository has at least one commit
    When I run "spec-kitty upgrade --yes"
    And I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the repository has no new commits
    And the repository HEAD is unchanged
    And the folder ".claude/skills" is unchanged
    And the folder ".claude/skills" is not empty

  Scenario: A tracked refresh that already arrived with the pull is not redone
    Given an existing git repository with commit history
    And a project already set up with Spec Kitty for the agents "claude"
    And the file ".gitignore" is present
    And every change in the project is committed
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the file ".gitignore" is unchanged
    And the folder ".claude/skills" exists
    And the repository has no new commits

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: An interrupted upgrade finishes the job when re-run
    Given a project already set up with Spec Kitty for the agents "claude"
    And a setup step the project declares but has not recorded as run
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the previously pending setup step has taken effect
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the repository has no new commits

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A teammate's clone gets its own local git setup even though the project was already set up elsewhere
    Given a freshly pulled clone whose shared records show its local git setup ran but whose own local git state is missing
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And this clone's own local git setup is in place

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: Re-running upgrade on a clone that already has its local setup changes nothing further
    Given a freshly pulled clone whose shared records show its local git setup ran but whose own local git state is missing
    When I run "spec-kitty upgrade --yes"
    And I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And this clone's own local git setup is in place
    And the repository has no new commits
    And the working tree has no uncommitted changes

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: I can ask what setup steps ran and in what order
    Given a project already set up with Spec Kitty for the agents "claude"
    When I run "spec-kitty upgrade --list-applied"
    Then the command succeeds
    And the setup steps that ran are listed in the order they ran

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: The report tells me whether a local-only step is actually in place here, not just recorded
    Given a freshly pulled clone whose shared records show its local git setup ran but whose own local git state is missing
    When I run "spec-kitty doctor migrations"
    Then the command succeeds
    And the report shows a local-only setup as recorded elsewhere but not yet in place here

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: A project upgraded from before the ledger existed keeps its already-done work recognized
    Given a project set up before Spec Kitty recorded its applied setup steps
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the setup work already done is not done again
    And the repository has no new commits

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-17
  Scenario: The system tells me when a setup step's content no longer matches what it ran
    Given a project whose recorded setup step no longer matches its current definition
    When I run "spec-kitty doctor migrations"
    Then the command succeeds
    And the report flags a setup step whose content changed since it ran

# New acceptance-jvm steps the #5230 implementation mission must bind
# (every @wip scenario above stays information-only until these exist):
#   Arrange (Given):
#     - "a setup step the project declares but has not recorded as run"
#     - "a freshly pulled clone whose shared records show its local git setup ran
#        but whose own local git state is missing"
#     - "a project set up before Spec Kitty recorded its applied setup steps"
#     - "a project whose recorded setup step no longer matches its current definition"
#   Assert (Then):
#     - "the previously pending setup step has taken effect"
#     - "this clone's own local git setup is in place"
#     - "the setup steps that ran are listed in the order they ran"
#     - "the report shows a local-only setup as recorded elsewhere but not yet in place here"
#     - "the setup work already done is not done again"
#     - "the report flags a setup step whose content changed since it ran"
# The read surface the last four scenarios drive (`spec-kitty upgrade --list-applied`
# and/or `spec-kitty doctor migrations`) is also part of the #5230 mission; the exact
# command name is the mission's to settle. The clone Given needs a fixture that seeds a
# recorded-but-locally-absent state (a pushed record without the clone-local effect).
