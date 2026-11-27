---
title: 'Migration: Planning Lane Writes to the Mission Branch'
description: 'Before a default Mission lands, its planning work packages are worked, reviewed and evidenced on the Mission branch; how to recover planning work already committed on the target.'
doc_status: active
kind: How-To
audience:
- profile: external/project-owner
  guidance_text: Written for the operator of a Mission in flight when Spec Kitty is upgraded.
updated: '2026-11-27T00:00:00Z'
related:
- adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize
- adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim
- context/topology
- changelog/CHANGELOG
---

# Planning lane writes to the Mission branch

Use this page when a Mission created without `--topology` (a default Mission) has a
planning-artifact work package, and you upgrade to a release that carries #7860. It matters most
when that Mission is already in flight.

## What changed

A default Mission mints one Mission branch. When `finalize-tasks` settles it `lanes_with_coord`,
that branch becomes its coordination branch and is checked out in the coordination worktree
(`.worktrees/<slug>-coord`), while the repository root checkout returns to the target branch.

Before this change, three surfaces disagreed about where a planning work package's work belongs:

- `implement` sent the agent to the repository root checkout, on the target branch;
- the implementation-evidence check (move into review, `accept`, `consolidate`, the orchestrator
  API) ended the planning window at the target branch;
- the review range read the Mission branch.

So work committed next to the Mission's other planning artifacts, on the Mission branch, was
refused with `IMPLEMENTATION_MISSING`, and operators forced the move into review by hand.

Now, until the Mission lands, the Mission branch is the one place a planning work package is
written, reviewed and evidenced (operator ruling A', recorded on #7860):

- `agent action implement`, native `implement` and `orchestrator-api start-implementation` name
  the coordination worktree as the workspace and say the work is committed on the Mission branch.
- The claim base is recorded from that checkout, so the move-into-review gate counts the work
  package's own commits.
- The evidence window runs from the commit on the Mission branch that introduced the work
  package's claim to the Mission branch tip. Content written before the claim (for example a
  `research/` draft from planning) is never evidence.
- `consolidate` lands the planning work on the target with the rest of the Mission. Its
  reconciliation claim reads the planning lane's authorship from the Mission branch (the planning
  commit to the Mission branch tip). Each approved work package is credited only for its own
  `owned_files` and only inside its own window, from the commit that introduced its claim to the
  Mission branch tip (the same start as the evidence window), so an owned-path change made before
  that claim is never its work. Only commits made on top of the claim commit count: when the
  Mission branch brings the claim in through a merge (for example a `git pull` in a second clone),
  a commit on the other side of that merge is not in the window. No merge commit is credited at
  all, by SHA, patch-id, file content or deletion: a merge that resolved a conflict lists the
  resolved file, and its content can carry a change made before the claim. A file's final content
  (or its deletion) is credited only when every commit on the Mission branch's first-parent
  history from the planning commit that changed the file is credited for it: a file's content
  holds every earlier change to it, so a file that a merge, a commit made before the claim, or any
  other uncredited commit changed is refused as un-attributable, even when a credited commit
  changed it later, and is never credited to an older commit. A file that a credited commit
  renamed or copied from another file also carries every uncredited change to that other file,
  so a file made before the claim and then moved or copied by the work package is refused under
  its new name too (git's default copy detection: a copy whose source the same commit left
  unchanged reads as a new file, whose whole content the review diff shows). A commit counts by SHA or patch-id only when every path it changes
  is credited that way or is Mission bookkeeping; a commit that also changes another path
  contributes only its credited files, so its other change (and any cherry-picked copy) is refused
  as un-attributable at the gate. The planning lane authors nothing, so the gate refuses its
  content, in these cases:
  - any work package of the planning lane is not approved or done (canceled, still in flight, or
    with no status). The claim admits a commit by its paths, not by who made it, so another work
    package's commit into an approved path would otherwise count as approved work, whatever that
    work package's own `owned_files` say;
  - a work package's `owned_files` cannot be read;
  - any pattern is too broad. A pattern must be led by at least two literal path segments (the
    segments before the first one holding `*`, `?` or `[`, after `\` is read as `/` and a leading
    `./` and a trailing `/` are dropped), or name one top-level file with an extension such as
    `README.md`. So `src/specify_cli/**`, `docs/context/topology.md` and
    `kitty-specs/<slug>/notes.md` are usable, while `*`, `**`, `*.py`, the inferred fallback
    `src/**` and every pattern as broad as it (`src`, `src/`, `src/*`, `src/**/*`, `src/*/**`,
    `src/**/*.py`), and also `docs/*.md`, `docs/**`, `.github` or `.gitignore`, are not. An
    absolute path, an empty segment or a `..` segment is refused outright;
  - every work package's `owned_files` is empty;
  - the commit that introduced a work package's claim on the Mission branch cannot be found.

  The refusal names the planning lane, the reason and the work packages, and prints the remedy
  with the work package ids and `--mission <slug>` filled in. It is printed only when the
  un-attributable content is the planning lane's: a file inside the lane's `write_scope` or its
  work packages' `owned_files`, or a commit of the lane's Mission-branch walk that changes one. A
  code lane's stray content does not print it. No attestation lifts the planning-lane credit rule
  (operator ruling R1), `--attest-canceled-superseded` included. The remedies, each driven end to
  end through the CLI:
  - a work package still in flight: finish its review and approval;
  - a canceled work package that was claimed before it was canceled and owes no work:
    `spec-kitty agent tasks move-task <WP> --to approved --force --agent <reviewer> --mission <slug>`, then
    `spec-kitty consolidate --mission <slug> --attest-no-implementation <WP> --attest-reason "<why>"`;
  - a canceled work package that was never claimed (a dropped work package) and owes no work:
    record its claim first with `spec-kitty agent tasks move-task <WP> --to claimed --force --agent <implementer> --mission <slug>`
    (that status commit on the Mission branch starts its window; without it the evidence check
    refuses `EVIDENCE_WINDOW_UNCOMPUTABLE` and the attestation does not lift that), then the two
    commands above. `canceled` cannot go back to `planned`, even with `--force`;
  - a canceled work package that owes work: move it with `--to claimed --force`, claim it with
    `spec-kitty agent action implement <WP> --agent <agent> --mission <slug>`, commit its change, move it to
    `for_review`, and have it reviewed and approved;
  - a too-broad `owned_files`: narrow it to two literal leading segments;
  - a claim commit that cannot be found (for example an approved work package with no recorded
    claim, or one whose claim event more than one commit introduced). The evidence check refuses
    it first with `EVIDENCE_WINDOW_UNCOMPUTABLE`. `implement` refuses an approved work package
    (#7754), and a move back to `planned` out of review keeps the old claim as the window start,
    so start a new window, at the cost of a second review:
    1. `spec-kitty agent tasks move-task <WP> --to planned --review-feedback-file <file> --mission <slug>`
       (reopen; skip this and the next step when the work package is already `claimed` or
       `in_progress`);
    2. `spec-kitty agent action implement <WP> --agent <agent> --mission <slug>`. When the refusal
       says no window-opening (claim) status event is recorded, this first claim starts the window:
       go to step 5;
    3. `spec-kitty agent tasks move-task <WP> --to planned --review-feedback-file <file> --mission <slug>`
       again (a claim event is recorded but no single commit introduced it, so the move out of
       review kept that old claim; a move to `planned` from `claimed` or `in_progress` starts a new
       window);
    4. `spec-kitty agent action implement <WP> --agent <agent> --mission <slug>`, whose claim's status commit on the
       Mission branch starts the new window;
    5. commit the change to each of its `owned_files` again in the coordination worktree (a commit
       made before the new claim does not count), move it to `for_review`, and have it reviewed and
       approved.

    The planning-lane note prints only the steps that apply to each work package.

  The forced moves are operator transitions recorded in the status log, and the attestation
  records why the work package owes no work. The attestation answers only the owned-file evidence
  check (`IMPLEMENTATION_MISSING`); the planning-lane credit rule is met by the forced approval.
  Record the forced approval as an identity other than the one that claimed the work package
  (`--agent <reviewer>`, not the `<implementer>`), or the independence check refuses
  `REVIEW_NOT_INDEPENDENT`.

  Then run `consolidate` again.

Nothing changes for an explicit-topology Mission (`--topology ...`), a Mission whose landing is
recorded, a `single_branch` Mission or a code lane: their planning work is still worked in the
repository root checkout and judged against the target branch.

No migration runs, and no second evidence rule is kept for in-flight Missions (operator ruling
"guidance only").

## Who is affected

A default Mission that settled `lanes_with_coord`, has not landed, and whose planning work package
was committed in the repository root checkout on the target branch, as the old `implement`
guidance said.

## Symptom

`move-task --to for_review`, `accept` or `consolidate` refuses the work package with
`IMPLEMENTATION_MISSING`, names a window that ends at the Mission branch, and adds:

```text
Changes to its owned_files were found on the target branch only: <sha> ...
```

That addendum appears only when a commit on the target changed one of the work package's
`owned_files`. A work package with no owned change anywhere is refused without it.

## Recover

Pick one remedy per work package.

**The work is the work package's own.** Cherry-pick the named commits onto the Mission branch, in
the coordination worktree, then retry:

```bash
cd .worktrees/<slug>-coord
git cherry-pick <sha> [<sha> ...]
cd -
spec-kitty agent tasks move-task <WP> --to for_review --mission <slug>
```

The commits stay on the target as well. If they should not have landed there, revert them on the
target through your usual review route.

**The work package owes no implementation.** Record that on `accept` or `consolidate`:

```bash
spec-kitty accept --mission <slug> --attest-no-implementation <WP> --attest-reason "<why>"
spec-kitty consolidate --mission <slug> --attest-no-implementation <WP> --attest-reason "<why>"
```

The attestation lifts only `IMPLEMENTATION_MISSING`. It is not a review.

## `PLANNING_CHECKOUT_MISSING`

`implement` refuses with `PLANNING_CHECKOUT_MISSING` when the planning work package must be worked
on the Mission branch but no checkout holds it (the coordination worktree was removed, or the
branch exists only on a remote). It never falls back to the repository root checkout. Restore
the coordination worktree, then retry:

```bash
spec-kitty doctor coordination --mission <slug> --fix
```

When the branch exists only as a remote-tracking ref, create the local branch first
(`git branch <mission-branch> <remote>/<mission-branch>`); the refusal prints that command.
The orchestrator API reports it as
`LANE_ALLOCATION_FAILED` with `data.workspace_error_code = "PLANNING_CHECKOUT_MISSING"`.

## Known residuals

- **The Mission lookup refuses first when the coordination worktree is gone (8a).** The Mission
  directory and `lanes.json` exist only on the Mission branch, so `orchestrator-api
  start-implementation` refuses with a lookup code (`WP_NOT_FOUND`, or `MISSION_NOT_FOUND` when
  no Mission directory is found at all), and `agent action implement` refuses
  with "Error locating work package: ... has no tasks directory", before the workspace resolver can say `PLANNING_CHECKOUT_MISSING`. Both fail closed
  (no claim is recorded, nothing falls back), but the refusal does not name the remedy above. Run
  `spec-kitty doctor coordination --mission <slug> --fix` in that case too.
- **`move-task --to done` asks for `--done-override-reason` (#7877)** for a `code_change` work
  package that a Mission finalized before #7816 placed in `lane-planning`, when it is moved to
  `done` before the Mission lands. The check fails safe: it asks for an override instead of
  passing.
- **The planning lane has no approval-stamp bound.** Code lanes are bounded by each work
  package's approval stamp; the planning lane is not stamped. A change to an approved planning
  work package's owned path made after its approval, by any commit on the Mission branch, still
  counts as approved authorship in the reconciliation claim.
- **The planning scope is read from the live working tree.** The reconciliation claim reads the
  planning work packages' `owned_files` from the task files in the working tree (the placement
  seam's `tasks/` directory), not at the coordination base the rest of the claim is pinned to,
  and `consolidate --resume` does not freeze it. An `owned_files` edit made between runs, even an
  uncommitted one, changes the scope.
- **The review range lists owned files only.** The review range of a planning work package is
  limited to its `owned_files` pathspecs, so a change the work package made outside its ownership
  map is not shown in the review commands. The review range keeps its own reading of the write
  branch until #5604 lands; a test pins that it agrees with the evidence window.
