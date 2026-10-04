---
title: 'Red Main and Release Readiness'
description: 'What a red main branch means, why CI status is the authoritative release gate, how P0 bugs carry failing reproduction tests, and how maintainers prioritize recovery.'
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/maintainer.md
type: explanation
related:
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
- docs/development/testing/testing-flakiness.md
- docs/development/how-to/pr-landing.md
- docs/guides/how-to/missions/keep-main-clean.md
---

# Red Main and Release Readiness

This guide states, in operational terms, what a red `main` means and how the team acts on it. The governing decision is [ADR 2026-07-17-1](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md), accepted by consensus (CEO/product owner, QA lead, maintainers).

The one-line stance: **it's broken, we hate it, but it's the truth, so we do not hide it.** An honest red is worth more than a convenient green.

## What a red main means

A red `main` is a **true signal**, not a workflow violation. It means mainline CI has found one or more known release-blocking (**P0**) defects. We do **not** keep `main` green by hiding failures — reverting an honest red or declining to merge a bug's reproduction test would produce a *green-washed* mainline that lies to everyone building on it.

A red `main` should always be **traceable to an accepted P0**: a filed issue, ideally with a failing test that reproduces the defect.

## CI status is the release authority

**Mainline CI status is authoritative for release readiness. Red CI means no release.**

- No release is cut while mainline CI is red — there is no "known-red, ship anyway" path.
- Because CI is the single gate, it must mean one thing. That is exactly why we refuse to green-wash: a CI signal that is sometimes decorative is authoritative for nothing.

See the release process in [CONTRIBUTING](../contributing.md); this guide governs *whether* a release may proceed, which is gated on green mainline CI.

## Filing or accepting a P0: add a failing test

When you file or accept a P0 bug, you are **free and encouraged** to land a test that reproduces it — a red-first reproduction at mainline scope.

- A P0 that carries a failing test is unambiguous, self-documenting, and impossible to lose track of. A P0 described only in prose drifts and gets rediscovered downstream.
- Turning `main` red this way is **honouring the process, not breaking it.** The red is the point: it makes the defect visible until it is fixed.
- This is the mainline-scope extension of the red-first / never-retry-to-green discipline already applied per-PR — see [test-flakiness handling](../testing/testing-flakiness.md) and the red classification bins in the [PR-landing runbook](../how-to/pr-landing.md).

### Where the reproduction runs: the nightly `p0-repro` lane

Mark the reproduction `@pytest.mark.p0_repro(issue=N)`, where `N` is the P0 issue. It runs **only** in the nightly `p0-repro` job (`.github/workflows/ci-nightly.yml`). A pull request never runs it, so pull requests always land on a green per-PR gate, and the nightly stays red until the P0 is fixed.

- **How it is held out.** The plugin `tests/_support/p0_repro.py` deselects every `p0_repro` test unless `SPEC_KITTY_RUN_P0_REPRO=1` is set, and only the `p0-repro` job sets it. A `-m` expression cannot pull it into another lane. `make test-fast` and `make test-full` never run it either.
- **How it fails.** Each failure starts with `[OPEN P0 #N] … expected to fail until that bug is fixed`. The job summary and `::error` annotations name every red reproduction, and the JUnit report records the issue as a `p0_issue` property. The lane opens no generic "Nightly suite red" issue, because each reproduction already has its own P0 issue.
- **Why it still blocks a release.** A release needs a green nightly for the exact release SHA (`scripts/ci/release_nightly_gate.py`), so the red keeps blocking releases.
- **A pin without an issue is rejected.** `p0_repro` without a positive `issue=` number is a collection error in every run, including per-PR runs.
- **When the fix lands.** The fix PR removes the `p0_repro` marker in the same change. The test then runs per PR as an ordinary guard (mark it `regression` only if it is an end-to-end replay of the bug's exact sequence) and must pass there. If a reproduction passes in the nightly before its marker is removed, the run ends with a `[P0 #N REPRO PASSES]` line: either the fix landed without removing the marker, or the reproduction is broken.
- **Run it locally:** `SPEC_KITTY_RUN_P0_REPRO=1 uv run --frozen pytest -m p0_repro -q`.

## Expensive QA and manual testing wait for green

**Expensive QA runs and internal manual testing do not execute on a red mainline build.** There is no value in validating a base that is already known-broken; that effort waits until `main` is green. This protects scarce QA and human-tester time from being spent certifying a base whose result is already known.

## Maintainers prioritize red builds

Green `main` is the goal. A red `main` is **not an acceptable resting state** — it is an alarm that pulls to the front of the maintainer queue.

- Treat mainline recovery as top priority; do not let "red is allowed" erode into "red is tolerated."
- Land the fix through the normal PR flow (no-direct-push is unchanged — see [Keep Main Clean](../../guides/how-to/missions/keep-main-clean.md)); this policy governs what a red CI *means*, not how commits arrive.
- The landing-pass runbook's [red-classification step](../how-to/pr-landing.md#4-classify-every-red-check) tells you how to tell a genuine P0 red from a flake or a pre-existing breakage while you work the queue.

## See also

- [ADR 2026-07-17-1 — Red main is honest signal; CI status is the release authority](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md) — the governing decision.
- [Test-flakiness handling policy](../testing/testing-flakiness.md) — the never-retry-to-green rule and budget-gate tuning.
- [Landing Contributor PRs: The Maintainer Runbook](../how-to/pr-landing.md) — red classification and the merge-ready hand-off.
- [How to Keep Main Clean](../../guides/how-to/missions/keep-main-clean.md) — the branch and no-direct-push discipline.
