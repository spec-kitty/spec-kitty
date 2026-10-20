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
#       the declared-but-not-recorded work (a stranded step is picked up). The
#       project is set up before it has a git repository, so its local git setup
#       cannot be in place yet and must stay pending (#6431). The first upgrade may
#       commit (#6416 still adds a .gitattributes line there); only the re-run must
#       commit nothing, so the repository state is recorded between the two runs.
#     * The "I can ask what ran" / "tells me whether a local-only step is in place
#       here" / drift scenarios restate the operator-visibility and drift promises.
#     * "keeps its already-done work recognized" restates the backfill promise:
#       a pre-ledger project is not force-re-migrated. Its first upgrade commits
#       exactly the adoption (the record of what ran leaves metadata.yaml for the
#       tracked ledger, ADR 2026-10-17-1 §6 hard cutover); the re-run commits
#       nothing (#6369). "lists no done work" is the shape pre-ledger init left
#       (applied: []): adoption settles what the version stamp had settled (#6431).
# - Steps follow Arrange / Assume / Act / Assert; see tests/scenarios/README.md.
#   This folder carries no PROMISES.md and uses the untagged-gating style of
#   upgrade.feature; these scenarios therefore carry no @promise tag (operator
#   ruling, 2026-10-17).
# - Read surface: the operator-facing visibility surface these scenarios drive is
#   `spec-kitty migrate ledger` (#5230 / IC-05). It reports which setup steps ran,
#   in declared order, in which partition, whether a local-only step is in place
#   here or only recorded elsewhere, and whether a step's content changed since it
#   ran. It is read-only (never commits, never writes a file).

Feature: Upgrade runs exactly the setup work a project still needs
  As a developer who already adopted Spec Kitty
  I want `spec-kitty upgrade` to run only the setup work my project has not yet had, in a
  dependable order, and to tell me what ran
  So that re-running is safe, a teammate's fresh clone gains its own local setup, and I can
  see and trust what has been done

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-18 @defect:6416
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

  @wip @wip-owner:stijn-dejongh @wip-since:2026-10-18 @defect:6416
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

  Scenario: An interrupted upgrade finishes the job when re-run
    Given a project already set up with Spec Kitty for the agents "claude"
    And a setup step the project declares but has not recorded as run
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the previously pending setup step has taken effect
    And the repository has at least one commit
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the repository has no new commits

  Scenario: A teammate's clone gets its own local git setup even though the project was already set up elsewhere
    Given a freshly pulled clone whose shared records show its local git setup ran but whose own local git state is missing
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And this clone's own local git setup is in place

  Scenario: Re-running upgrade on a clone that already has its local setup changes nothing further
    Given a freshly pulled clone whose shared records show its local git setup ran but whose own local git state is missing
    When I run "spec-kitty upgrade --yes"
    And I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And this clone's own local git setup is in place
    And the repository has no new commits
    And the working tree has no uncommitted changes

  Scenario: I can ask what setup steps ran and in what order
    Given a project already set up with Spec Kitty for the agents "claude"
    When I run "spec-kitty migrate ledger"
    Then the command succeeds
    And the setup steps that ran are listed in the order they ran

  Scenario: The report tells me a local-only step is not yet in place on this checkout
    Given a freshly pulled clone whose shared records show its local git setup ran but whose own local git state is missing
    When I run "spec-kitty migrate ledger"
    Then the command succeeds
    And the report shows a local-only setup step as not yet in place on this checkout

  Scenario: A project upgraded from before the ledger existed keeps its already-done work recognized
    Given a project set up before Spec Kitty recorded its applied setup steps
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the setup work already done is not done again
    And the upgrade changed only the project's record of its applied setup steps
    And the working tree has no uncommitted changes to tracked files
    And the repository has at least one commit
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the repository has no new commits

  Scenario: A project set up before the ledger existed whose metadata lists no done work is not re-migrated
    Given a project set up before Spec Kitty recorded its applied setup steps, whose metadata lists none of them
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the setup work already done is not done again
    And the upgrade changed only the project's record of its applied setup steps
    And the working tree has no uncommitted changes to tracked files
    And the repository has at least one commit
    When I run "spec-kitty upgrade --yes"
    Then the command succeeds
    And the repository has no new commits

  Scenario: The system tells me when a setup step's content no longer matches what it ran
    Given a project whose recorded setup step no longer matches its current definition
    When I run "spec-kitty migrate ledger"
    Then the command succeeds
    And the report flags a setup step whose content changed since it ran

# - The first two scenarios are @wip @defect:6416 (#6369): they landed gating without ever
#   running and were red on the 2026-10-18 nightly. A just-initialized project's first upgrade
#   commits a .gitattributes merge-driver line init never wrote. "A tracked refresh ..." also
#   never records the repository state before it acts, so "the repository has no new commits"
#   cannot pass as written; fix that Arrange too before dropping @wip.
# The acceptance-jvm steps these scenarios bind (eight gate the nightly; two are @wip, above):
#   Arrange (Given):
#     - "a setup step the project declares but has not recorded as run"
#     - "a freshly pulled clone whose shared records show its local git setup ran
#        but whose own local git state is missing"
#     - "a project set up before Spec Kitty recorded its applied setup steps"
#     - "a project set up before Spec Kitty recorded its applied setup steps, whose
#        metadata lists none of them"
#     - "a project whose recorded setup step no longer matches its current definition"
#   Assert (Then):
#     - "the previously pending setup step has taken effect"
#     - "this clone's own local git setup is in place"
#     - "the setup steps that ran are listed in the order they ran"
#     - "the report shows a local-only setup step as not yet in place on this checkout"
#     - "the setup work already done is not done again"
#     - "the upgrade changed only the project's record of its applied setup steps"
#     - "the report flags a setup step whose content changed since it ran"
# The read surface the last four scenarios drive is `spec-kitty migrate ledger`
# (the read-only applied-work visibility surface, #5230 / IC-05). The clone Given
# seeds a genuine freshly pulled clone: the shared, committed records show the
# project's setup ran, but this checkout has neither the per-clone record (it lives
# only in the git-ignored per-clone ledger, which never travels) nor the clone-local
# git effect — so the report shows that local-only step as not yet in place here, and
# upgrade installs it.
