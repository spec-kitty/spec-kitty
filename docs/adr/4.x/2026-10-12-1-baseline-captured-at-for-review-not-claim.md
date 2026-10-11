---
title: 'ADR: the test baseline is captured at for_review, at the lane fork point, not at the claim'
description: 'Test-baseline capture runs capture-if-missing on the in_progress to for_review edge, at the lane merge-base, lock-free and fail-open; the claim never runs the suite.'
status: Accepted
date: '2026-10-12'
related:
- docs/adr/4.x/2026-10-07-3-review-lane-exit-requires-verdict-or-forced-note.md
---

**Status:** Accepted

**Date:** 2026-10-12

**Deciders:** Stijn Dejongh (owner).

**Technical Story:** [#6062](https://github.com/spec-kitty/spec-kitty/issues/6062)
(`agent action implement` hung holding the machine-wide pre-review-gate lock), fixed in
[PR #6068](https://github.com/spec-kitty/spec-kitty/pull/6068). Related: #2493 (the gate lock).

## Context and Problem Statement

`agent action implement` ran the project's configured baseline test suite synchronously before it
returned. That run reused the `for_review` gate's head runner, which wrapped every launch in
`pre-review-gate-run.lock`, the machine-wide lock that serializes concurrent `for_review` head
runs (#2493). A claim therefore acquired, or queued on, a lock scoped to a different transition.
The claim could wedge (exit 124 under a `timeout`, about 0% CPU) and could block another lane's
`for_review` gate.

The baseline is still needed: the pre-review gate diffs head failures against it so that failures
that already existed on the base are not reported as regressions.

## Decision Drivers

* A claim must return promptly after the lane worktree exists and the work package is `doing`.
* The baseline must describe the code the lane started from, not whatever the base is by the time
  the work package reaches review.
* Capture must not couple to a lock that belongs to another transition.
* A capture fault must never refuse a `for_review` move.

## Decision Outcome

**Test-baseline capture runs capture-if-missing on the `in_progress -> for_review` edge, at the
lane's merge-base with its base branch, lock-free and fail-open; the claim never runs the suite.**

* The claim path does not capture. `implement_capture_baseline` became `capture_and_commit_baseline`
  because it is no longer implement-only.
* `move-task --to for_review` captures when no `baseline-tests.json` exists. A rework cycle finds the
  committed artifact and does nothing; an unconfigured `review.test_command` captures nothing.
* The capture ref is `git merge-base <lane HEAD> <base>` (local refs only, no fetch). If it cannot be
  resolved, the base tip is used and a warning is logged.
* Capture runs through `_run_raw_command(serialize=False)` in its own detached worktree, keeping the
  group-safe launch and reap, without the gate lock.
* Any fault in capture preparation or the run degrades to no baseline; the gate then reports
  `UNVERIFIED_BASELINE` as a warning, exactly as for a never-captured baseline.

## Consequences

* The baseline reflects the fork point. The artifact's `base_commit` records the SHA it was taken at,
  so a reader can detect a stale baseline.
* Concurrent captures from different lanes do not serialize on the gate lock.
* The `for_review` head run still serializes on the gate lock (#2493), so a `for_review` move can
  wait on another lane's head run, but never because of a baseline capture.
* The configured suite now runs at the first `for_review` of a work package, where blocking is
  acceptable, instead of at claim time. The first `for_review` move is slower by one suite run.
