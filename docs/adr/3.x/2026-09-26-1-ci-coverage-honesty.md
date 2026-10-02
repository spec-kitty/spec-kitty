---
title: 'ADR: a green main/nightly must mean the tests actually ran'
description: 'CI now enforces coverage honesty — dark-suite enrolment, foreign-coverage and src-reachability guards, a nightly run-all lane, and release gated on a green nightly for that SHA.'
status: Accepted
date: '2026-09-26'
updated: '2026-10-01'
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

## Amendment (2026-10-01) — nightly architectural backstop, sharded battery, CI worker policy (mission ci-runtime-stabilisation, #5510)

This amendment appends to the accepted text above and does not edit it. It corrects one
Consequences claim, records what the mission `ci-runtime-stabilisation` shipped, and links
the contracts that hold the details:
[router two-authority amendment](../../../kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md),
[battery partition](../../../kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/battery-partition.md).

### Context

This amends the first Consequences bullet, "A green **nightly** now means the full suite
ran". That statement did not hold for `tests/architectural`. Before this amendment the
nightly reached the battery only through the interpreter shard that runs the
`fast or unit` selection, which is **18.6%** of the battery (the SC-003 baseline measured by
the mission). A red architectural gate outside that selection could therefore sit behind a
green nightly. Two open issues name the gap: [#4708](https://github.com/spec-kitty/spec-kitty/issues/4708)
("CI must actually execute the whole test suite") and
[#3265](https://github.com/spec-kitty/spec-kitty/issues/3265) (no unfiltered `main` backstop,
folded into this mission). The per-PR battery was also a single slow job that every code PR
waited on.

### Decision

1. **A nightly architectural backstop.** `ci-nightly.yml` gains the job
   `architectural-backstop`. It runs the full per-PR battery base command
   (`tests/architectural`, the base marker expression and the same deselects) with no
   partition plugin, on Python 3.12, with a 40-minute timeout, so it does not depend on the
   partition or gate-selection code being correct. It is listed in `nightly-summary.needs`.
   A red run fails the nightly conclusion, which `scripts/ci/release_nightly_gate.py` already
   reads for the release SHA, and it escalates through `scripts/ci/nightly_escalation.py`
   under the suite key `architectural`: one deduplicated `priority:P0` issue per key,
   triaged on file (type Bug, labels `priority:P0` and `from:ci`, milestone, and a native
   sub-issue link under [#5106](https://github.com/spec-kitty/spec-kitty/issues/5106)).
2. **A sharded per-PR battery with an always-on fast gate.** The battery is an always-on
   `architectural-fast` job plus `architectural-heavy` as one job key with a two-leg
   `include:` matrix (`--battery-part 1/2` and `2/2`). The registry
   `.github/ci-module-registry.yml` (`special_tiers.architectural`) is the single declaration
   of the fast roster, the shard count, the worker count and the base selection. The workflows
   carry literal copies of the worker count, the base marker expression and the deselects, and
   pin tests (`tests/ci/test_xdist_worker_policy.py` and the partition proof) keep those
   copies equal to the registry. Per-file timings in `.github/ci-shard-timings.json`
   feed the shared selector `scripts/ci/shard_select.py`. A static partition proof requires
   fast, leg 1 and leg 2 to be pairwise disjoint and to cover the base selection exactly.
3. **A CI worker policy.** Battery legs, the fast gate, the backstop and the Packs corpus job
   pass a literal `-n 4` and no `-q`, so xdist prints `created: 4/4 workers`.
   `tests/ci/test_xdist_worker_policy.py` fails on `-n auto` in those jobs. Local
   `make test-*` targets keep `-n auto`.
4. **A `ci_config` path group.** CI-configuration paths (workflows, composite actions,
   `scripts/ci/**`, `pytest.ini`, `pyproject.toml`, `Makefile`, the registry and the timings
   file) select the heavy battery and nothing else. This is amendment A1 of the linked
   contract. It reverses, for the battery only, the earlier rulings that CI-config changes
   gate no router job.

### Consequences

- The corrected guarantee holds for the architectural battery: a green nightly now means the
  full battery ran, because the backstop executes the whole per-PR base selection in one
  plain pytest invocation. Interpreter diversity stays with the interpreter matrix shards.
- The backstop is judged on its own job conclusion. The overall nightly conclusion also
  reflects unrelated suites, so it cannot show the backstop's health by itself.
- The per-PR battery stays a non-required check, as ADR 2026-09-23-1 requires. Both the
  `architectural-fast` job and the `architectural-heavy` legs are in the `needs` of
  `router-gate`, so a red in either turns the required `router gate` red. None of these jobs
  is itself a required context (a path-scoped job is never required, per ADR 2026-09-23-1).
- Measurements for the mission's non-functional requirements are recorded in the mission
  evidence file `kitty-specs/ci-runtime-stabilisation-01M3TZH6/evidence/ci-measurements.md`.
