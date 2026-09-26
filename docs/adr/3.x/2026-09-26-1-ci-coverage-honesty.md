---
title: 'ADR: a green main/nightly must mean the tests actually ran'
description: 'CI now enforces coverage honesty — dark-suite enrolment, foreign-coverage and src-reachability guards, a nightly run-all lane, and release gated on a green nightly for that SHA.'
status: Accepted
date: '2026-09-26'
---

## Context and Problem Statement

The per-module CI selector (`scripts/ci/gate_selection.py`, fed by `ci-router.yml`)
keyed which module shards run on a push to **source roots** — a change under
`src/specify_cli/<x>/**` selected the `<x>` module — with **no model of which
source a given test exercises**. Two blind spots followed:

- **Cross-cutting / unenrolled suites were silently skipped on `main` pushes.**
  Whole test directories (`tests/agent`, `tests/specify_cli/live_work`,
  `tests/review`, `tests/upgrade`, and the `execution_context` family) were
  effectively never selected on ordinary `main` pushes, so a regression in code
  they cover could ship to a **green `main`** undetected.
- **`integration_tests_next` was a dead tier** — declared in the registry with
  roots `tests/integration/**` + `tests/next/**` but invoked by no workflow, so
  those suites ran nowhere.

This was root-caused in [#5034](https://github.com/spec-kitty/spec-kitty/issues/5034)
(epic [#4437](https://github.com/spec-kitty/spec-kitty/issues/4437)) after it
repeatedly cost maintainer landing passes: PRs #5029 and #5032 each un-masked a
backlog of pre-existing reds the moment their diff touched a path that finally
selected one of those shards. A green check no longer meant the tests had run.

## Decision

Make "green ⇒ the tests actually ran" an enforced property, in four parts:

1. **Coverage-honesty guards** (`scripts/ci/coverage_guard_lib.py`, enforced by
   `tests/architectural/test_foreign_coverage_guard.py` and
   `test_src_reachability_guard.py`) — shrink-only ratchets over a measured
   baseline (`.github/ci-foreign-coverage-baseline.json`). *foreign-coverage*
   requires every registry row's test dirs to exercise its own `roots:`;
   *src-reachability* pins a `truly-dark` set (a package imported by no test
   anywhere) and an `in-matrix-dark` set (tested only nightly). They fail only
   when coverage **regresses**, never vacuously.
2. **Enrol the dark suites** into `.github/ci-module-registry.yml` (`agent_utils`,
   `live_work`, `config`, `calibration`, `tasks_authoring`, `bootstrap`) with
   re-measured host shard timings, and fix the phantom-mirror authority bug in
   `test_gate_selection_authority` (it validated a non-existent `tests/agent_utils`).
3. **A nightly run-all `integration-next` lane** in `ci-nightly.yml` running
   `pytest tests/integration tests/next` regardless of paths, with
   **red → deduped-P0 escalation** (`scripts/ci/nightly_escalation.py`): one
   `priority:P0` issue per suite key, opened/updated on red and closed on green,
   fail-closed and token-redacted when the token/API is absent. This retires the
   dead `integration_tests_next` tier ([#4729](https://github.com/spec-kitty/spec-kitty/issues/4729)).
4. **Release gated on a green nightly** (`scripts/ci/release_nightly_gate.py`,
   wired in `release.yml`): `build-release`/`publish-pypi` are blocked unless the
   nightly for the **exact release SHA** is green; fail-closed on a missing,
   stale, red, or in-progress nightly.

## Consequences

- A green **nightly** now means the full suite ran; a masked per-push red cannot
  reach a published release, because release gates on that nightly.
- **Operator prerequisite:** `release.yml` dispatches the nightly via
  `workflow_dispatch`, which the default `GITHUB_TOKEN` cannot trigger. A repo
  secret **`RELEASE_NIGHTLY_DISPATCH_TOKEN`** (a PAT or GitHub App token) is
  required; without it the release gate fails closed and nothing publishes. This
  is intentional fail-closed behavior. `release.yml` (`Publish Release`) is the
  live release workflow, so the secret must be provisioned before the next tag
  release — see `RELEASE_CHECKLIST.md`.
- Per-push selection is **still path-filtered** (unchanged); this ADR closes the
  *honesty* gap (nothing is untested-by-construction, and release can't ship a
  masked red), not the *latency* gap. Promoting `tests/integration` to a per-PR
  lane is deferred to [#5037](https://github.com/spec-kitty/spec-kitty/issues/5037).
- The `in-matrix-dark` baseline records remaining nightly-only debt (e.g.
  `diagnostics`, imported only by `tests/e2e`) as an explicit, shrink-only ledger
  rather than a silent gap.

## Alternatives Considered

- **Run every module shard on every push.** Rejected: prohibitively slow/expensive
  for the common case, and it does not address `truly-dark` packages that no test
  exercises at all (the guards do).
- **Leave per-push selection as-is and rely on maintainers noticing.** Rejected —
  that is the status quo #5034 documents as failing: reds accumulated invisibly and
  surfaced only as landing-pass tax on unrelated PRs.
