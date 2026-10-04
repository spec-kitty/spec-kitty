---
title: 'Red main is honest signal; CI status is the release authority'
description: 'A red mainline is honest signal and P0 reproductions may land red-first, but mainline CI status is the release authority: nothing ships on red, with no exceptions.'
status: Accepted
date: '2026-07-17'
---

# Red main is honest signal; CI status is the release authority

**Status:** Accepted (by consensus) · **Deciders:** Robert Douglass (CEO / product owner), Kent (QA lead), maintainers · **Date:** 2026-07-17 · **Related:** [`docs/development/red-main-and-release-readiness.md`](../../development/reference/red-main-and-release-readiness.md), [`docs/development/testing-flakiness.md`](../../development/testing/testing-flakiness.md), [`docs/development/pr-landing.md`](../../development/how-to/pr-landing.md), the charter's red-first / test-remediation standing order.

## Context and Problem Statement

Our `main` branch runs a large CI suite whose result the team reads as the truth about the product. Two pressures pull against each other:

- **The convenience pull** — a green `main` feels good, so there is a standing temptation to keep it green by reverting anything that goes red, or by declining to merge a test that reproduces a known bug. That produces a *green-washed* mainline: green because the failures are hidden, not because the product works.
- **The honesty pull** — the whole point of CI is to be a trustworthy signal. A P0 defect that exists in the product but is invisible on `main` is a lie the whole team then builds on: releases ship on a false green, expensive QA runs validate a base that is secretly broken, and the same bug gets rediscovered downstream.

The precipitating events: #2752 was merged with known reds (a CI-guard change whose companion arch-gate fix, #2753, landed right after), and #2754 (a pre-existing `setup-plan` error-translation regression) was filed *because* it was surfaced honestly during a landing pass rather than papered over. Both cases raised the same question — **is a red `main` a process failure to be hidden, or a true signal to be honoured?** — and the team needed a single, written answer.

## Decision Drivers

- **Honest signal over convenience.** A false green is worse than an honest red: it moves the cost of a defect downstream and destroys trust in CI.
- **CI must mean one thing.** If CI status is sometimes decorative (kept green by hiding failures) and sometimes authoritative, it is authoritative for nothing.
- **Protect expensive verification.** Manual QA and long/expensive automated runs are wasted if they execute against a base that is already known-broken.
- **Reproduce, don't just assert.** A P0 that carries a failing test is unambiguous, self-documenting, and un-loseable; a P0 described only in prose drifts and gets forgotten.
- **Recovery is the priority.** Red `main` is not acceptable as a resting state; it is an alarm that pulls maintainer attention to the front of the queue.

## Considered Options

- **Option A — Always-green mainline (green-washing).** Keep `main` green at all times: revert anything that reds it, and refuse to merge failing reproduction tests. *Rejected* — it hides P0s, lets releases ship on a false green, wastes QA on a secretly-broken base, and contradicts the transparency value.
- **Option B — Honest mainline; CI is the release authority (chosen).** `main` is allowed to be red when it carries accepted release-blocking (P0) defects; CI status is the single authoritative release gate; failing reproduction tests for P0s are encouraged; expensive QA is gated on green; maintainers prioritize red recovery.
- **Option C — Separate always-green release branch, `main` allowed red.** Maintain a parallel release line that is kept green while `main` may be red. *Rejected* — it splits the source of truth into two CI signals, adds branch-management overhead, and dilutes exactly the "CI means one thing" property Option B is designed to protect.

## Decision Outcome

**Chosen option: "Option B — Honest mainline; CI is the release authority."** The five binding rules:

1. **`main` may be red.** A red `main` is legitimate and expected when it reflects known release-blocking (P0) defects. It is a *true signal*, not a workflow violation. (This is orthogonal to the no-direct-push / Protect-Main policy, which is unchanged — see [Consequences](#consequences).)
2. **Mainline CI status is authoritative for release readiness.** **Red CI means no release.** No release proceeds on a red mainline, full stop. There is no "known-red, ship anyway" path.
3. **P0 filing/acceptance may (and should) add a failing test.** When a P0 bug is filed or accepted, the reporter/accepter is free and **encouraged** to land a test that reproduces the defect — a red-first reproduction at mainline scope. Turning `main` red this way is honouring the process, not breaking it.
4. **Expensive QA and internal manual testing do not run on a red mainline.** There is no value in validating a base that is already known-broken; QA effort waits for green.
5. **Maintainers prioritize red builds.** Green `main` is the goal; a red `main` is not an acceptable resting state and pulls to the front of the maintainer queue. We favour transparency and honest reporting over convenience: *it's broken, we hate it, but it's the truth, so we do not hide it.*

### Consequences

#### Positive

- Release readiness has a single, trustworthy gate — CI — that cannot be green-washed.
- P0 defects are visible on `main` and, when reproduced by a test, self-documenting and un-loseable.
- Expensive QA and manual-test effort is never spent validating a known-broken base.
- The policy reinforces the existing red-first / never-retry-to-green discipline (see [testing-flakiness](../../development/testing/testing-flakiness.md) and the landing-pass bin classification in [pr-landing](../../development/how-to/pr-landing.md)) by extending it from the PR scope to the mainline scope.

#### Negative

- A red `main` is psychologically uncomfortable and can alarm contributors who read it as "the project is broken" rather than "a known P0 is being worked." Mitigation: the accompanying guide states the meaning plainly, and P0s that red `main` carry a filed issue.
- The policy depends on maintainer discipline to actually prioritize recovery; without it, "red is allowed" could erode into "red is tolerated." The "not an acceptable resting state" rule and the QA-gating consequence are the counter-pressures.

#### Neutral

- **No-direct-push is unchanged.** Changes still reach `main` only through pull requests and the Protect-Main workflow; this ADR governs what a red CI *means*, not how commits arrive.
- A P0 reproduction test that reds `main` is expected to be tracked by its P0 issue, so the red is always traceable to an accepted defect.

### Confirmation

The decision is confirmed in practice by two observable invariants: (a) no release is cut while mainline CI is red, and (b) an accepted P0 either carries a failing reproduction test or a filed issue (ideally both). A release cut on red, or an accepted P0 silently reverted to keep `main` green, is a violation of this ADR. The operational runbook lives in [`docs/development/red-main-and-release-readiness.md`](../../development/reference/red-main-and-release-readiness.md).

## Amendment 2026-10-04 — the red lives in the nightly, never in a PR

Rule 3's "red-first reproduction at mainline scope" now has one fixed home. A reproduction of an open P0 carries `@pytest.mark.p0_repro(issue=N)` and runs **only** in the `p0-repro` job of `.github/workflows/ci-nightly.yml`. `tests/_support/p0_repro.py` deselects it from every other run: every per-PR lane, `make test-fast` / `make test-full`, and every other nightly lane. So a pull request always lands on a green per-PR gate, while an open P0 keeps the nightly honestly red, and each failure carries an `[OPEN P0 #N]` banner naming its issue.

Rules 1, 2 and 5 are unchanged in substance. "Mainline CI" includes the nightly, and a release requires a green nightly run for the exact release SHA (`scripts/ci/release_nightly_gate.py`), so an open P0 reproduction still blocks every release. The only bypass is the `skip_nightly` maintainer waiver on a manually dispatched `.github/workflows/release.yml` run (never on a tag push), which skips the nightly gate and says so in the run summary. The `regression` marker no longer carries P0 reproductions. It stays the marker for issue-pinned guards of bugs that are already fixed, and those guards run per PR. The fix PR for a P0 removes the `p0_repro` marker in the same change, which turns the reproduction into such a guard.
